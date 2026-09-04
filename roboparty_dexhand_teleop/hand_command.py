"""Pure command mapping and mode selection for RP_Hand teleoperation."""

from __future__ import annotations

import numpy as np


HAND_MODES = {"controller", "skeleton"}
COUNTS_MIN = 0
COUNTS_MAX = 10000


def validate_preset(name: str, values) -> np.ndarray:
    preset = np.asarray(values, dtype=np.float32).reshape(-1)
    if preset.shape != (6,):
        raise ValueError(f"{name} must contain exactly 6 values, got {preset.size}")
    if not np.all(np.isfinite(preset)) or np.any(preset < 0.0) or np.any(preset > 1.0):
        raise ValueError(f"{name} values must be finite and within [0, 1]")
    return preset


def controller_to_counts(
    trigger: float,
    grip: float,
    preset_open,
    preset_grasp,
    preset_pinch,
    *,
    deadzone: float = 0.05,
    scale: float = 1.0,
    enable_grip: bool = True,
    counts_min: float = COUNTS_MIN,
    counts_max: float = COUNTS_MAX,
) -> np.ndarray:
    """Map PICO trigger/grip values to six RP_Hand encoder targets."""
    if not 0.0 <= deadzone < 0.5:
        raise ValueError(f"deadzone must be within [0, 0.5), got {deadzone}")
    if not 0.0 < scale <= 1.0:
        raise ValueError(f"scale must be within (0, 1], got {scale}")
    if counts_min < COUNTS_MIN or counts_max > COUNTS_MAX or counts_min >= counts_max:
        raise ValueError(f"counts range invalid: [{counts_min}, {counts_max}]")

    open_pose = validate_preset("preset_open", preset_open)
    grasp_pose = validate_preset("preset_grasp", preset_grasp)
    pinch_pose = validate_preset("preset_pinch", preset_pinch)
    trigger_value = float(np.clip(trigger, 0.0, 1.0))
    grip_value = float(np.clip(grip, 0.0, 1.0))
    if trigger_value < deadzone:
        trigger_value = 0.0
    if grip_value < deadzone:
        grip_value = 0.0
    trigger_value *= scale
    grip_value *= scale

    normalized = open_pose + trigger_value * (grasp_pose - open_pose)
    if enable_grip:
        pinch = open_pose + grip_value * (pinch_pose - open_pose)
        normalized = np.maximum(normalized, pinch)
    return np.rint(counts_min + normalized * (counts_max - counts_min)).astype(np.int32)


class HandCommandSelector:
    """Select one live command source and blend when the requested mode changes."""

    def __init__(self, initial_mode: str = "controller", transition_ms: float = 300.0):
        if initial_mode not in HAND_MODES:
            raise ValueError(f"unsupported hand mode: {initial_mode}")
        if transition_ms < 0.0:
            raise ValueError("transition_ms must be non-negative")
        self.requested_mode = initial_mode
        self.active_mode = None
        self.transition_mode = None
        self.transition_ns = int(transition_ms * 1e6)
        self.transition_start_ns = 0
        self.transition_from = None
        self.last_output = None

    def request(self, mode: str) -> None:
        normalized = str(mode).strip().lower()
        if normalized not in HAND_MODES:
            raise ValueError(f"unsupported hand mode: {mode!r}")
        self.requested_mode = normalized

    def select(self, now_ns: int, candidates: dict[str, np.ndarray | None]) -> np.ndarray | None:
        target = candidates.get(self.requested_mode)
        if target is None:
            return None
        target = np.asarray(target, dtype=np.float32).reshape(6)

        if self.active_mode is None:
            self.active_mode = self.requested_mode
            self.last_output = target.copy()
            return np.rint(target).astype(np.int32)

        switching = self.requested_mode != self.active_mode
        switching_back = (
            self.transition_mode is not None
            and self.transition_mode != self.requested_mode
        )
        if (switching and self.transition_mode != self.requested_mode) or switching_back:
            self.transition_mode = self.requested_mode
            self.transition_start_ns = int(now_ns)
            self.transition_from = (
                target.copy() if self.last_output is None else self.last_output.copy()
            )

        if self.transition_mode is not None:
            if self.transition_ns == 0:
                alpha = 1.0
            else:
                alpha = float(
                    np.clip(
                        (int(now_ns) - self.transition_start_ns) / self.transition_ns,
                        0.0,
                        1.0,
                    )
                )
            output = self.transition_from * (1.0 - alpha) + target * alpha
            if alpha >= 1.0:
                self.active_mode = self.transition_mode
                self.transition_mode = None
                self.transition_from = None
        else:
            output = target

        self.last_output = np.asarray(output, dtype=np.float32)
        return np.rint(output).astype(np.int32)
