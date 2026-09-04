"""DexPilot adapter for mapping PICO skeletons to RP_Hand motor targets."""

from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import yaml

from .hand_coordinates import canonical_hand_to_rp_landmarks


TARGET_JOINT_NAMES = (
    "finger11",
    "finger12",
    "finger21",
    "finger31",
    "finger41",
    "finger51",
)
COUNTS_MIN = 0
COUNTS_MAX = 10000


def _source_asset_root() -> Path:
    return Path(__file__).resolve().parent / "assets"


def resolve_asset_root(override: str | os.PathLike[str] | None = None) -> Path:
    """Locate retargeting assets in a source tree or installed ROS package."""
    if override:
        root = Path(override).expanduser().resolve()
    else:
        root = _source_asset_root()
    if not root.is_dir():
        raise FileNotFoundError(
            f"RP_Hand retargeting asset directory does not exist: {root}; set asset_root"
        )
    return root


def read_joint_limits(
    urdf_path: str | os.PathLike[str], joint_names=TARGET_JOINT_NAMES
) -> np.ndarray:
    """Read the six active joint limits directly from the retargeting URDF."""
    root = ET.parse(urdf_path).getroot()
    joints = {joint.get("name"): joint for joint in root.findall("joint")}
    limits = []
    for name in joint_names:
        joint = joints.get(name)
        limit = None if joint is None else joint.find("limit")
        if limit is None or limit.get("lower") is None or limit.get("upper") is None:
            raise ValueError(f"URDF joint {name!r} has no finite lower/upper limit")
        lower = float(limit.get("lower"))
        upper = float(limit.get("upper"))
        if not np.isfinite(lower) or not np.isfinite(upper) or lower >= upper:
            raise ValueError(f"URDF joint {name!r} has invalid limits [{lower}, {upper}]")
        limits.append((lower, upper))
    return np.asarray(limits, dtype=np.float32)


def radians_to_counts(joint_radians, joint_limits: np.ndarray) -> np.ndarray:
    """Map URDF joint radians into the RP_Hand encoder range."""
    values = np.asarray(joint_radians, dtype=np.float32).reshape(6)
    limits = np.asarray(joint_limits, dtype=np.float32).reshape(6, 2)
    clipped = np.clip(values, limits[:, 0], limits[:, 1])
    ratio = (clipped - limits[:, 0]) / (limits[:, 1] - limits[:, 0])
    return np.rint(COUNTS_MIN + ratio * (COUNTS_MAX - COUNTS_MIN)).astype(np.int32)


class RPHandRetargeter:
    """One-hand DexPilot instance using the RP_Hand URDF and joint order."""

    def __init__(self, side: str, asset_root: str | os.PathLike[str] | None = None):
        if side not in {"left", "right"}:
            raise ValueError(f"side must be 'left' or 'right', got {side!r}")
        self.side = side
        self.asset_root = resolve_asset_root(asset_root)
        config_path = self.asset_root / "rp_hand" / "rp_hand.yml"
        if not config_path.is_file():
            raise FileNotFoundError(f"RP_Hand retargeting config does not exist: {config_path}")

        from .dex_retargeting import RetargetingConfig

        RetargetingConfig.set_default_urdf_dir(self.asset_root)
        with config_path.open("r", encoding="utf-8") as stream:
            document = yaml.safe_load(stream)
        config_data = deepcopy(document[side])
        config = RetargetingConfig.from_dict(config_data)
        self._retargeting = config.build()
        self._human_indices = self._retargeting.optimizer.target_link_human_indices
        self._hardware_indices = [
            self._retargeting.joint_names.index(name) for name in TARGET_JOINT_NAMES
        ]
        self.joint_limits = read_joint_limits(config.urdf_path)

    def retarget_radians(self, hand_tracking_state) -> np.ndarray:
        landmarks = canonical_hand_to_rp_landmarks(hand_tracking_state, self.side)
        references = landmarks[self._human_indices[1, :]] - landmarks[self._human_indices[0, :]]
        all_joints = self._retargeting.retarget(references)
        target = np.asarray(all_joints[self._hardware_indices], dtype=np.float32)
        return np.clip(target, self.joint_limits[:, 0], self.joint_limits[:, 1])

    def retarget_counts(self, hand_tracking_state) -> np.ndarray:
        return radians_to_counts(self.retarget_radians(hand_tracking_state), self.joint_limits)
