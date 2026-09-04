# 全身 GMR + 双灵巧手手柄遥操作 SOP

本文档用于在操作端电脑 `zyq` 上运行新版 `roboparty_teleop`，同时控制机器人全身和左右两只 `RP_Hand`。

## 系统分工

```text
PICO
  -> roboparty_teleop
       -> /tracking/current_reference   全身参考
       -> /pico/controller/*            手柄数据
       -> /pico/hand/*                  手部数据
  -> roboparty_dexhand_teleop
       -> /dexhand_left/cmd
       -> /dexhand_right/cmd
  -> 机器人板 roboparty_dexhand_ros
       -> roboparty_dexhand / dexhand_py
       -> CAN-FD
       -> 左右 RP_Hand
```

`roboparty_teleop` 只运行在操作端并且是唯一的 PICO SDK owner。底层
`roboparty_dexhand`、`dexhand_py` 和 `roboparty_dexhand_ros` 只运行在机器人板。

如果终端是 `zsh`，将本文档中的 `setup.bash` 替换为 `setup.zsh`；项目中的
`.sh` 启动脚本会自行使用 Bash。

## 1. 启动机器人板端设备层

在机器人板上执行。以下示例使用左手 `can0`、右手 `can3`，两只手的 Node ID
均为 `1`：

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

回零会产生真实运动。执行前确认双手周围安全，并等待左右节点都出现：

```text
hand detected and initialized: initialized (enable=True, home=True)
```

## 2. 准备 PICO

在 `zyq` 操作端电脑上：

1. 启动 XRoboToolkit PC Service。
2. 连接 PICO。
3. 开启 Full Body。
4. 确认左右手柄已经连接。

手柄模式只使用手柄的 trigger/grip 数据，不要求开启手部骨骼追踪。

## 3. 启动全身 GMR 和 PICO 话题

在 `zyq` 的第一个终端执行：

```bash
cd /home/zyq/rp/roboparty_teleop
source .venv/bin/activate

./scripts/rp1_deploy/run_local.sh
```

该进程同时发布：

```text
/tracking/current_reference
/pico/controller/left/joy
/pico/controller/right/joy
/pico/hand/left/poses
/pico/hand/right/poses
/pico/hand/left/active
/pico/hand/right/active
```

正式全身模式下不要再运行 `run_pico_topics.sh --hands-only`，避免启动第二个
PICO SDK owner。

## 4. 启动双手手柄桥接

在 `zyq` 的第二个终端执行：

```bash
source /opt/ros/humble/setup.zsh
source /home/zyq/roboparty_ws/install/setup.zsh

export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0

ros2 launch roboparty_dexhand_teleop dual_dexhand_teleop.launch.py \
  input_mode:=controller \
  grasp_scale:=0.2
```

初次运行建议使用 `grasp_scale:=0.2` 的小行程。确认方向和动作正确后，
可在第二个终端提高到 `0.6`：

```bash
ros2 param set /dexhand_teleop_left grasp_scale 0.6
ros2 param set /dexhand_teleop_right grasp_scale 0.6
```

数据映射关系：

```text
左手柄 -> /pico/controller/left/joy  -> /dexhand_left/cmd  -> can0
右手柄 -> /pico/controller/right/joy -> /dexhand_right/cmd -> can3
```

## 5. 启动检查

在操作端执行：

```bash
ros2 topic hz /tracking/current_reference
ros2 topic hz /pico/controller/left/joy
ros2 topic hz /pico/controller/right/joy
ros2 topic hz /dexhand_left/cmd
ros2 topic hz /dexhand_right/cmd
```

正常情况下有效数据频率接近 `50 Hz`。查看单帧手柄数据：

```bash
ros2 topic echo --once /pico/controller/left/joy
```

桥接节点日志应包含：

```text
active hand mode: controller
```

## 6. 停止顺序

1. 在第二个终端按 `Ctrl+C`，停止 `roboparty_dexhand_teleop`。
2. 在第一个终端按 `Ctrl+C`，停止全身 GMR 和 PICO 数据发布。
3. 最后停止机器人板端 `roboparty_dexhand_ros`。

停止前不要直接拔除 CAN 或手部电源。
