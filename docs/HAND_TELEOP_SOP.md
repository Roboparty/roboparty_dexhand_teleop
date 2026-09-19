# RP1 全身与 RP_Hand 遥操作 SOP

本文档适用于 Ubuntu 22.04 操作端、ROS 2 Humble 机器人板和左右两只
RP_Hand。当前机器人映射为左手 `can0`、右手 `can3`，两只手的 CAN Node ID
均为 `1`。

> 如果终端是 `zsh`，将下面的 `setup.bash` 替换为 `setup.zsh`；项目中的
> `.sh` 启动脚本会自行使用 Bash。

## 1. 软件版本

以下版本组成首个可复现组合：

| 组件 | 最低版本 | 运行位置 | 职责 |
| --- | --- | --- | --- |
| `roboparty_teleop` | `0.1.0` | 操作端 | PICO 接入、全身 GMR、发布 `/pico/*` |
| `roboparty_dexhand_teleop` | `0.1.1` | 操作端 | 手柄/骨骼到 RP_Hand 六轴目标 |
| `roboparty_dexhand_ros` | `0.1.0` | 机器人板 | ROS 设备节点和双手生命周期 |
| `roboparty_dexhand` | `0.4.2` | 机器人板 | C++/Python CAN-FD 驱动和真实回零确认 |

不要使用 `roboparty_dexhand 0.4.1` 判断回零是否完成；该版本只能确认厂商
命令已返回，不能确认真机已经回零。

## 2. 首次安装

### 2.1 操作端

操作端的两个项目分别准备环境：

- `roboparty_teleop`：按其仓库说明安装 PICO、XRoboToolkit PC Service、厂商
  Python binding 和全身 GMR 依赖。
- `roboparty_dexhand_teleop`：按 [README 的安装步骤](../README.md#安装与构建)
  使用独立 uv 环境，并在仓库根目录构建。

以下假设仓库分别位于 `~/roboparty_teleop` 和 `~/roboparty_dexhand_teleop`，
请按实际位置调整。手部桥接无需复用全身 GMR 环境。

### 2.2 机器人板

安装与板子架构匹配的驱动包，再构建设备节点：

```bash
sudo apt install ./roboparty-dexhand_0.4.2-1_arm64.deb

mkdir -p ~/roboparty_dexhand_ws/src
cd ~/roboparty_dexhand_ws/src
git clone https://github.com/Roboparty/roboparty_dexhand_ros.git

cd ~/roboparty_dexhand_ws
source /opt/ros/humble/setup.bash
source /opt/roboparty/setup.bash
colcon build --symlink-install --packages-select roboparty_dexhand_ros
```

## 3. 上电前检查

1. 确认左右手、机械臂末端和 CAN 终端电阻连接可靠。
2. 确认两只手周围没有人员或障碍物，回零会产生真实运动。
3. 确认板端存在 `can0` 和 `can3`；本项目不负责修改板子的开机 CAN 配置。
4. 确认操作端和机器人板的 `ROS_DOMAIN_ID` 一致，默认均为 `0`。

```bash
ip -details link show can0
ip -details link show can3
dpkg-query -W roboparty-dexhand
```

两路 CAN 应为 `UP`、CAN-FD、仲裁域 `1 Mbps`、数据域 `5 Mbps`。如果接口连
`ip link` 中都不存在，应先恢复 USB CAN 硬件枚举，不能继续启动手部节点。

## 4. 正式启动：全身与双手

### 4.1 机器人板：设备层与回零

```bash
source /opt/ros/humble/setup.bash
source /opt/roboparty/setup.bash
source ~/roboparty_dexhand_ws/install/setup.bash

ros2 launch roboparty_dexhand_ros dual_dexhand.launch.py \
  left_interface:=can0 \
  right_interface:=can3 \
  node_id:=1 \
  velocity:=3000 \
  home_on_start:=true
```

只有左右节点均打印以下日志，才表示驱动收到了新的真实反馈，并确认六轴停止、
无报警且位于零点 `±400` 以内：

```text
hand detected and initialized: initialized (enable=True, home=True)
```

### 4.2 操作端：PICO 与全身 GMR

启动 XRoboToolkit PC Service，在 PICO 中开启 Full Body 和 Hand Tracking，然后：

```bash
cd ~/roboparty_teleop
source .venv/bin/activate
./scripts/rp1_deploy/run_local.sh
```

该进程是唯一的 PICO SDK owner，同时发布：

```text
/tracking/current_reference
/pico/hand/left/poses
/pico/hand/right/poses
/pico/hand/left/active
/pico/hand/right/active
/pico/controller/*
```

正式全身模式下不要同时运行 `run_pico_topics.sh --hands-only`。

### 4.3 操作端：双手骨骼映射

打开第二个终端：

```bash
cd ~/roboparty_dexhand_teleop
source /opt/ros/humble/setup.bash
export PYTHONNOUSERSITE=1
source .venv/bin/activate
source install/setup.bash
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0

ros2 launch roboparty_dexhand_teleop dual_dexhand_teleop.launch.py \
  input_mode:=skeleton
```

`grasp_scale` 不影响骨骼模式，骨骼目标按 URDF 关节范围映射到 0–10000。

如需切换为手柄模式：

```bash
ros2 topic pub --once /teleop/hand_mode std_msgs/msg/String \
  '{data: controller}'
```

切回骨骼模式：

```bash
ros2 topic pub --once /teleop/hand_mode std_msgs/msg/String \
  '{data: skeleton}'
```

## 5. 启动验收

在机器人板检查节点和命令频率：

```bash
ros2 node list | grep -E 'dexhand_(left|right)'
ros2 topic hz /dexhand_left/cmd
ros2 topic hz /dexhand_right/cmd
```

在操作端检查 PICO 和全身参考：

```bash
ros2 topic hz /pico/hand/left/poses
ros2 topic hz /pico/hand/right/poses
ros2 topic hz /tracking/current_reference
```

期望手部 pose 和双手 cmd 在追踪有效时接近 `50 Hz`。短时丢失手骨骼时 bridge
停止发送旧目标，PICO 数据恢复后会自动恢复，不需要重新 init 或重新回零。

## 6. 仅调试手部

不运行全身 GMR 时，可用轻量 PICO 输入进程：

```bash
cd ~/roboparty_teleop
source .venv/bin/activate
./scripts/run_pico_topics.sh --hands-only
```

然后按 4.3 启动 `roboparty_dexhand_teleop`。该模式和 4.2 的完整全身进程只能
二选一。

## 7. 停止顺序

1. 停止 `roboparty_dexhand_teleop`，不再产生新的双手目标。
2. 停止 `roboparty_teleop`，关闭 PICO/GMR 输入。
3. 最后停止板端 `roboparty_dexhand_ros`；驱动退出时会停止并禁用双手。

## 8. 当前数据落盘边界

可以使用 `ros2 bag record` 同时记录 PICO 输入、全身参考和手部目标：

```bash
ros2 bag record \
  /pico/hand/left/poses /pico/hand/right/poses \
  /pico/hand/left/active /pico/hand/right/active \
  /pico/controller/left/joy /pico/controller/right/joy \
  /dexhand_left/cmd /dexhand_right/cmd \
  /tracking/current_reference
```

当前 `roboparty_dexhand_ros 0.1.0` 尚未发布带时间戳的真实位置和设备状态话题，
因此上述 rosbag 只能证明输入和目标已经生成，不能证明真机每个关节实际到达。
正式数据采集前需要先补齐板端状态消息。

可复现的整机数据集还应包含板端六轴实际位置与设备状态，以及全身的
`/action`、`/joint_states`、`/imu` 等策略输出和实际状态；按设备实际提供的话题
补充录制列表。
