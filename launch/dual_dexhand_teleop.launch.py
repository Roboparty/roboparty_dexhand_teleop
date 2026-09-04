# SPDX-License-Identifier: GPL-3.0

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config_file = LaunchConfiguration("config_file")
    left_enabled = LaunchConfiguration("left")
    right_enabled = LaunchConfiguration("right")
    grasp_scale = LaunchConfiguration("grasp_scale")
    input_mode = LaunchConfiguration("input_mode")

    # ROS binary extensions such as Pinocchio are built against the system
    # NumPy.  Keep user-site packages (which may contain an incompatible
    # NumPy 2.x) out of the bridge process without changing the operator's
    # main teleop/GMR environment.
    ros_python_env = {"PYTHONNOUSERSITE": "1"}

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config_file",
                default_value=PathJoinSubstitution(
                    [
                        FindPackageShare("roboparty_dexhand_teleop"),
                        "config",
                        "dexhand_teleop.yaml",
                    ]
                ),
                description="Preset poses and slot mapping for the hand bridges.",
            ),
            DeclareLaunchArgument(
                "left", default_value="true", description="Launch the left-hand bridge."
            ),
            DeclareLaunchArgument(
                "right", default_value="true", description="Launch the right-hand bridge."
            ),
            DeclareLaunchArgument(
                "grasp_scale",
                default_value="1.0",
                description="Travel scale for axes 2-6 (0.4=4000, 0.6=6000, 0.8=8000).",
            ),
            DeclareLaunchArgument(
                "input_mode",
                default_value="controller",
                choices=["controller", "skeleton"],
                description="Initial RP_Hand input mode.",
            ),
            Node(
                package="roboparty_dexhand_teleop",
                executable="dexhand_teleop_bridge",
                name="dexhand_teleop_left",
                parameters=[
                    config_file,
                    {"grasp_scale": grasp_scale, "input_mode": input_mode},
                ],
                additional_env=ros_python_env,
                output="screen",
                condition=IfCondition(left_enabled),
            ),
            Node(
                package="roboparty_dexhand_teleop",
                executable="dexhand_teleop_bridge",
                name="dexhand_teleop_right",
                parameters=[
                    config_file,
                    {"grasp_scale": grasp_scale, "input_mode": input_mode},
                ],
                additional_env=ros_python_env,
                output="screen",
                condition=IfCondition(right_enabled),
            ),
        ]
    )
