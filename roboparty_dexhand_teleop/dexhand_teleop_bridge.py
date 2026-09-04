#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
"""Consume canonical PICO topics and publish RP_Hand position commands."""

from __future__ import annotations

import time

import rclpy
from geometry_msgs.msg import PoseArray
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import Joy
from std_msgs.msg import Bool, Int32MultiArray, String

from .hand_command import HandCommandSelector, controller_to_counts, validate_preset
from .hand_retargeting import RPHandRetargeter
from .pico_contract import (
    canonical_hand_state,
    controller_trigger_grip,
    require_frame_id,
    source_stamp_ns,
)


class DexHandTeleopBridge(Node):
    def __init__(self):
        super().__init__("dexhand_teleop_bridge")
        self._declare_parameters()

        self.side = str(self.get_parameter("side").value).strip().lower()
        if self.side not in {"left", "right"}:
            raise ValueError(f"side must be left or right, got {self.side!r}")
        self.controller_topic = str(self.get_parameter("controller_topic").value)
        self.hand_pose_topic = str(self.get_parameter("hand_pose_topic").value)
        self.hand_active_topic = str(self.get_parameter("hand_active_topic").value)
        self.mode_topic = str(self.get_parameter("mode_topic").value)
        cmd_topic = str(self.get_parameter("cmd_topic").value)
        self.expected_frame_id = str(self.get_parameter("expected_frame_id").value)

        self.deadzone = float(self.get_parameter("deadzone").value)
        self.enable_grip_gesture = bool(self.get_parameter("enable_grip_gesture").value)
        self.preset_open = validate_preset(
            "preset_open", self.get_parameter("preset_open").value
        )
        self.preset_grasp = validate_preset(
            "preset_grasp", self.get_parameter("preset_grasp").value
        )
        self.preset_pinch = validate_preset(
            "preset_pinch", self.get_parameter("preset_pinch").value
        )
        self.counts_min = float(self.get_parameter("counts_min").value)
        self.counts_max = float(self.get_parameter("counts_max").value)
        self.input_timeout_ns = int(
            float(self.get_parameter("input_timeout_ms").value) * 1e6
        )
        publish_hz = float(self.get_parameter("publish_hz").value)
        if publish_hz <= 0.0 or self.input_timeout_ns < 0:
            raise ValueError("publish_hz must be positive and input_timeout_ms non-negative")

        initial_mode = str(self.get_parameter("input_mode").value).strip().lower()
        self.parameter_mode_seen = initial_mode
        self.selector = HandCommandSelector(
            initial_mode=initial_mode,
            transition_ms=float(self.get_parameter("transition_ms").value),
        )
        self.controller_target = None
        self.controller_update_ns = 0
        self.controller_source_stamp_ns = None
        self.skeleton_target = None
        self.skeleton_update_ns = 0
        self.skeleton_source_stamp_ns = None
        self.hand_tracking_active = False

        self.retargeter = None
        if bool(self.get_parameter("enable_skeleton").value):
            asset_root = str(self.get_parameter("asset_root").value).strip() or None
            try:
                self.retargeter = RPHandRetargeter(self.side, asset_root)
            except Exception as exc:
                self.get_logger().error(
                    f"skeleton mode unavailable for {self.side} hand: {exc}"
                )

        best_effort = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(
            Joy, self.controller_topic, self._on_controller_input, best_effort
        )
        self.create_subscription(
            PoseArray, self.hand_pose_topic, self._on_hand_poses, best_effort
        )
        self.create_subscription(
            Bool, self.hand_active_topic, self._on_hand_active, best_effort
        )
        self.create_subscription(String, self.mode_topic, self._on_mode, 10)
        command_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.command_publisher = self.create_publisher(
            Int32MultiArray, cmd_topic, command_qos
        )
        self.create_timer(1.0 / publish_hz, self._publish_command)

        self.get_logger().info(
            f"{self.side} hand bridge: controller={self.controller_topic}, "
            f"skeleton={self.hand_pose_topic}, mode={initial_mode} -> {cmd_topic}"
        )

    def _declare_parameters(self) -> None:
        self.declare_parameter("side", "right")
        self.declare_parameter("controller_topic", "/pico/controller/right/joy")
        self.declare_parameter("hand_pose_topic", "/pico/hand/right/poses")
        self.declare_parameter("hand_active_topic", "/pico/hand/right/active")
        self.declare_parameter("expected_frame_id", "xrobot_right_handed")
        self.declare_parameter("mode_topic", "/teleop/hand_mode")
        self.declare_parameter("cmd_topic", "/dexhand_left/cmd")
        self.declare_parameter("input_mode", "controller")
        self.declare_parameter("enable_skeleton", True)
        self.declare_parameter("asset_root", "")
        self.declare_parameter("transition_ms", 300.0)
        self.declare_parameter("publish_hz", 50.0)
        self.declare_parameter("input_timeout_ms", 250.0)
        self.declare_parameter("enable_grip_gesture", True)
        self.declare_parameter("deadzone", 0.05)
        self.declare_parameter("grasp_scale", 1.0)
        self.declare_parameter("preset_open", [0.0] * 6)
        self.declare_parameter("preset_grasp", [1.0] * 6)
        self.declare_parameter("preset_pinch", [1.0] * 6)
        self.declare_parameter("counts_min", 0.0)
        self.declare_parameter("counts_max", 10000.0)

    def _valid_frame(self, msg, stream: str) -> bool:
        try:
            require_frame_id(msg, self.expected_frame_id)
            return True
        except ValueError as exc:
            detail = str(exc)
        self.get_logger().warning(
            f"ignored {stream}: {detail}",
            throttle_duration_sec=2.0,
        )
        return False

    def _on_controller_input(self, msg: Joy) -> None:
        if not self._valid_frame(msg, "controller"):
            return
        try:
            trigger, grip = controller_trigger_grip(msg)
        except (TypeError, ValueError) as exc:
            self.get_logger().warning(
                f"invalid controller hand input: {exc}",
                throttle_duration_sec=2.0,
            )
            return
        stamp_ns = source_stamp_ns(msg)
        if stamp_ns > 0 and stamp_ns == self.controller_source_stamp_ns:
            return
        try:
            scale = float(self.get_parameter("grasp_scale").value)
            self.controller_target = controller_to_counts(
                trigger,
                grip,
                self.preset_open,
                self.preset_grasp,
                self.preset_pinch,
                deadzone=self.deadzone,
                scale=scale,
                enable_grip=self.enable_grip_gesture,
                counts_min=self.counts_min,
                counts_max=self.counts_max,
            )
            self.controller_update_ns = time.monotonic_ns()
            self.controller_source_stamp_ns = stamp_ns or None
        except (TypeError, ValueError) as exc:
            self.get_logger().warning(
                f"invalid controller hand input: {exc}", throttle_duration_sec=2.0
            )

    def _clear_skeleton(self) -> None:
        self.hand_tracking_active = False
        self.skeleton_target = None
        self.skeleton_update_ns = 0

    def _on_hand_active(self, msg: Bool) -> None:
        self.hand_tracking_active = bool(msg.data)
        if not self.hand_tracking_active:
            self._clear_skeleton()

    def _on_hand_poses(self, msg: PoseArray) -> None:
        if not self._valid_frame(msg, "hand skeleton"):
            self._clear_skeleton()
            return
        stamp_ns = source_stamp_ns(msg)
        if stamp_ns > 0 and stamp_ns == self.skeleton_source_stamp_ns:
            return
        if self.retargeter is None:
            return
        try:
            state = canonical_hand_state(msg)
            if state is None:
                self.skeleton_source_stamp_ns = stamp_ns or None
                self._clear_skeleton()
                return
            self.skeleton_target = self.retargeter.retarget_counts(state)
            self.skeleton_update_ns = time.monotonic_ns()
            self.skeleton_source_stamp_ns = stamp_ns or None
            self.hand_tracking_active = True
        except Exception as exc:
            self._clear_skeleton()
            self.get_logger().warning(
                f"{self.side} hand retarget failed: {exc}",
                throttle_duration_sec=2.0,
            )

    def _on_mode(self, msg: String) -> None:
        try:
            self.selector.request(msg.data)
            self.get_logger().info(f"requested hand mode: {self.selector.requested_mode}")
        except ValueError as exc:
            self.get_logger().warning(str(exc))

    def _fresh(self, target, updated_ns: int, now_ns: int):
        if target is None:
            return None
        if self.input_timeout_ns > 0 and now_ns - updated_ns > self.input_timeout_ns:
            return None
        return target

    def _publish_command(self) -> None:
        parameter_mode = str(self.get_parameter("input_mode").value).strip().lower()
        if parameter_mode != self.parameter_mode_seen:
            self.parameter_mode_seen = parameter_mode
            try:
                self.selector.request(parameter_mode)
            except ValueError as exc:
                self.get_logger().warning(str(exc), throttle_duration_sec=2.0)

        now_ns = time.monotonic_ns()
        previous_mode = self.selector.active_mode
        command = self.selector.select(
            now_ns,
            {
                "controller": self._fresh(
                    self.controller_target, self.controller_update_ns, now_ns
                ),
                "skeleton": self._fresh(
                    self.skeleton_target, self.skeleton_update_ns, now_ns
                ),
            },
        )
        if command is None:
            return
        message = Int32MultiArray()
        message.data = [int(value) for value in command]
        self.command_publisher.publish(message)
        if previous_mode != self.selector.active_mode:
            self.get_logger().info(f"active hand mode: {self.selector.active_mode}")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = DexHandTeleopBridge()
        rclpy.spin(node)
    except (ExternalShutdownException, KeyboardInterrupt):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
