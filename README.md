# roboparty_dexhand_teleop

`roboparty_dexhand_teleop` 是操作端的 RP_Hand 遥操作映射包。它订阅
`roboparty_teleop` 发布的标准化 XR 手柄与手骨骼数据，将其转换为左右手六轴
目标。它不初始化 PICO SDK、不打开 CAN，也不依赖 `dexhand_py`。

Ubuntu 22.04 上从安装到“全身 + 双手”验收的完整步骤见
[`docs/HAND_TELEOP_SOP.md`](docs/HAND_TELEOP_SOP.md)。

## 系统边界

```text
操作端电脑
  roboparty_teleop（唯一 PICO SDK owner）
    -> /pico/controller/* + /pico/hand/*
    -> roboparty_dexhand_teleop
    -> /dexhand_left/cmd + /dexhand_right/cmd

机器人板子
  roboparty_dexhand_ros
    -> dexhand_py
    -> roboparty_dexhand
    -> CAN-FD
```

全身 GMR 路径和手部路径共享标准化 XR 输入，但不共享 retarget 或硬件执行
进程。手部映射失败不会修改 `/tracking/current_reference`。

## 控制模式

- `controller`：将每侧手柄的 trigger/grip 映射为六轴 open、grasp、pinch
  预设。
- `skeleton`：将每侧 26 点 canonical 手骨骼经 DexPilot、RP_Hand URDF 和
  关节范围映射为六轴位置。

模式切换默认使用 300 ms 插值。输入超过 `input_timeout_ms` 后不再发布旧目标。

## 构建

操作端需要 ROS 2 Humble、Pinocchio、NLopt 和 NumPy：

```bash
sudo apt install ros-humble-pinocchio python3-nlopt python3-numpy

# Bash 终端使用 setup.bash；如果当前终端是 zsh，请使用 setup.zsh。
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select roboparty_dexhand_teleop
source install/setup.bash
```

## 运行

先启动新版 `roboparty_teleop`，确保 `/pico/*` 正常发布；然后在操作端启动
左右手映射：

```bash
ros2 launch roboparty_dexhand_teleop dual_dexhand_teleop.launch.py \
  input_mode:=controller grasp_scale:=0.2
```

切换骨骼模式：

```bash
ros2 topic pub --once /teleop/hand_mode std_msgs/msg/String \
  '{data: skeleton}'
```

默认输出：

```text
左手 -> /dexhand_left/cmd
右手 -> /dexhand_right/cmd
```

CAN 接口与 node ID 不属于本包配置；它们由机器人板上的
`roboparty_dexhand_ros` 决定。

## 数据采集边界

本包输出的是目标，不是真实硬件反馈。可复现数据集应同时记录：

- `/pico/controller/*`、`/pico/hand/*`：标准化 XR 输入；
- `/dexhand_left/cmd`、`/dexhand_right/cmd`：六轴手部目标；
- 板端 dexhand 状态话题：六轴实际位置与设备状态；
- `/tracking/current_reference`、`/action`、`/joint_states`、`/imu`：全身参考、
  policy 输出和机器人实际状态。

板端 dexhand 状态话题将在 `roboparty_dexhand_ros` 的接口阶段补齐。
