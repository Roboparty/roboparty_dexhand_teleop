"""Validation helpers for the canonical ``roboparty_teleop`` ROS topics."""

from __future__ import annotations

import math

import numpy as np


FRAME_ID = "xrobot_right_handed"
HAND_JOINT_COUNT = 26


def source_stamp_ns(message) -> int:
    stamp = message.header.stamp
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def require_frame_id(message, expected: str = FRAME_ID) -> None:
    actual = str(message.header.frame_id)
    if actual != expected:
        raise ValueError(f"frame_id={actual!r}; expected {expected!r}")


def controller_trigger_grip(message) -> tuple[float, float]:
    axes = tuple(float(value) for value in message.axes)
    if len(axes) < 2:
        raise ValueError(
            f"controller Joy must carry trigger and grip in axes[0:2], "
            f"got {len(axes)} axes"
        )
    trigger, grip = axes[:2]
    if not math.isfinite(trigger) or not math.isfinite(grip):
        raise ValueError("controller trigger/grip must be finite")
    return trigger, grip


def canonical_hand_state(message) -> np.ndarray | None:
    if not message.poses:
        return None
    if len(message.poses) != HAND_JOINT_COUNT:
        raise ValueError(
            f"canonical hand skeleton must contain {HAND_JOINT_COUNT} poses, "
            f"got {len(message.poses)}"
        )
    state = np.asarray(
        [
            [
                pose.position.x,
                pose.position.y,
                pose.position.z,
                pose.orientation.x,
                pose.orientation.y,
                pose.orientation.z,
                pose.orientation.w,
            ]
            for pose in message.poses
        ],
        dtype=np.float32,
    )
    if not np.all(np.isfinite(state)):
        raise ValueError("canonical hand skeleton contains non-finite values")
    quaternion_norms = np.linalg.norm(state[:, 3:7], axis=1)
    if np.any(quaternion_norms < 1e-8):
        raise ValueError("canonical hand skeleton contains a zero quaternion")
    return state
