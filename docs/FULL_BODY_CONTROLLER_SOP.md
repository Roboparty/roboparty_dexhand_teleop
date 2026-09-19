# 全身 GMR + 双灵巧手手柄遥操作 SOP

本文档用于在操作端电脑上运行新版 `roboparty_teleop`，同时控制机器人全身和左右两只 `RP_Hand`。

首次使用先按 [README](../README.md#安装与构建) 构建手部映射包。本文假设两个
仓库分别位于 `~/roboparty_teleop` 和 `~/roboparty_dexhand_teleop`，请按实际位置调整。

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

在操作端电脑上：

1. 启动 XRoboToolkit PC Service。
2. 连接 PICO。
3. 开启 Full Body。
4. 确认左右手柄已经连接。

手柄模式只使用手柄的 trigger/grip 数据，不要求开启手部骨骼追踪。

## 3. 启动全身 GMR 和 PICO 话题

在操作端第一个终端执行：

```bash
cd ~/roboparty_teleop
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

在操作端第二个终端执行：

```bash
cd ~/roboparty_dexhand_teleop
source /opt/ros/humble/setup.bash
export PYTHONNOUSERSITE=1
source .venv/bin/activate
source install/setup.bash

export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0

ros2 launch roboparty_dexhand_teleop dual_dexhand_teleop.launch.py \
  input_mode:=controller \
  grasp_scale:=0.2
```

`grasp_scale:=0.2` 只缩放手柄模式的预设变化量，默认第一轴仍保持 8000，
不会缩放骨骼模式输出。确认方向和动作正确后，
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

## 6. 独立终端键盘控制全身跟随

键盘节点运行在**操作端电脑**，调用 `roboparty_teleop` 的全身跟随服务。
先按 [README](../README.md) 构建本包。随后打开独立交互终端，在本仓库根目录运行：

```bash
source /opt/ros/humble/setup.bash
export PYTHONNOUSERSITE=1
source .venv/bin/activate
source install/setup.bash
ros2 run roboparty_dexhand_teleop teleop_keyboard
```

- `a`：调用 `/start_teleop`，请求开启全身跟随。
- `x`：调用 `/stop_teleop`，请求返回默认站姿参考。
- `q` 或 `Ctrl+C`：只退出键盘程序；需要回站姿时先按 `x`。

按键无需回车，操作时让键盘控制终端获得焦点。原有手部 launch 保持运行；
键盘节点不放入 launch，也不切换手部模式或控制灵巧手启停。

先在 `roboparty_teleop` 仓库中运行 `./scripts/rp1_deploy/run_local.sh`
（见第 3 节），并确认对应
`rp1_deploy` 配置启用了 `deploy.services: true`。
普通 PICO 数据发布配置本身不提供这两个服务。两个进程须使用兼容的 ROS
通信环境（包括相同的 `ROS_DOMAIN_ID`）。服务未就绪时不会缓存按键请求。
可用 `ros2 service list -t` 确认 `/start_teleop` 和 `/stop_teleop` 均为
`std_srvs/srv/Trigger`。跨机器运行时还需网络互通，且 `ROS_LOCALHOST_ONLY=0`。

开启服务要求有新鲜 XR/GMR 参考；成功回复只表示接受过渡请求，不代表机器人
已到位。`x` 是返回站姿参考，不是急停或电机断电。调用 5 秒未回复时
显示超时，不自动重试，且请求可能已经执行。等待开启回复期间仍可按 `x`。

如服务使用了命名空间，可通过参数指定：

```bash
ros2 run roboparty_dexhand_teleop teleop_keyboard --ros-args \
  -p start_service:=/my_robot/start_teleop \
  -p stop_service:=/my_robot/stop_teleop
```

## 7. 停止顺序

1. 在第二个终端按 `Ctrl+C`，停止 `roboparty_dexhand_teleop`。
2. 在第一个终端按 `Ctrl+C`，停止全身 GMR 和 PICO 数据发布。
3. 最后停止机器人板端 `roboparty_dexhand_ros`。

停止前不要直接拔除 CAN 或手部电源。
