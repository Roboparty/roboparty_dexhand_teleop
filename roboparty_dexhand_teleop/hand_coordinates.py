"""Convert canonical PICO hand poses into RP_Hand retargeting landmarks."""

from __future__ import annotations

import numpy as np


CANONICAL_HAND_JOINT_COUNT = 26
RP_HAND_LANDMARK_COUNT = 25
WRIST_INDEX = 0
PALM_INDEX = 1
DEXPILOT_JOINT_INDICES = (WRIST_INDEX, *range(2, CANONICAL_HAND_JOINT_COUNT))

# GR00T's default openxr_arm_frame path applies three fixed rotations:
# COORD_ROT_<side> @ T_TO_UNITREE_HAND @ T_ROBOT_OPENXR.  These are the
# algebraically equivalent products, applied once after removing wrist pose.
RP_HAND_BASIS = {
    "left": np.diag([1.0, -1.0, -1.0]).astype(np.float32),
    "right": np.diag([-1.0, 1.0, -1.0]).astype(np.float32),
}


def quaternion_xyzw_to_matrix(quaternion) -> np.ndarray:
    """Return a 3x3 rotation matrix for an ``[x, y, z, w]`` quaternion."""
    q = np.asarray(quaternion, dtype=np.float64).reshape(4)
    norm = float(np.linalg.norm(q))
    if not np.isfinite(norm) or norm < 1e-8:
        raise ValueError("wrist quaternion must be finite and non-zero")
    x, y, z, w = q / norm
    return np.asarray(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=np.float32,
    )


def canonical_hand_to_rp_landmarks(hand_tracking_state, side: str) -> np.ndarray:
    """Convert one canonical 26-joint pose array to 25 RP_Hand landmarks.

    Input rows are ``[x, y, z, qx, qy, qz, qw]`` in
    ``xrobot_right_handed``. Canonical index 0 is the wrist and index 1 is the
    palm. DexPilot consumes the wrist plus 24 finger landmarks, expressed in a
    wrist-local hand frame; the palm entry is intentionally omitted.
    """
    if side not in RP_HAND_BASIS:
        raise ValueError(f"side must be 'left' or 'right', got {side!r}")

    state = np.asarray(hand_tracking_state, dtype=np.float32)
    expected_shape = (CANONICAL_HAND_JOINT_COUNT, 7)
    if state.shape != expected_shape:
        raise ValueError(
            f"hand tracking state must have shape {expected_shape}, got {state.shape}"
        )
    if not np.all(np.isfinite(state)):
        raise ValueError("hand tracking state contains non-finite values")

    wrist_position = state[WRIST_INDEX, :3]
    wrist_rotation = quaternion_xyzw_to_matrix(state[WRIST_INDEX, 3:7])
    dexpilot_positions = state[DEXPILOT_JOINT_INDICES, :3]
    wrist_local = (dexpilot_positions - wrist_position) @ wrist_rotation
    return (wrist_local @ RP_HAND_BASIS[side].T).astype(np.float32)
