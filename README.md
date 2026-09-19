# roboparty_dexhand_teleop

RP_Hand 的 ROS 2 遥操作映射包，运行在操作端电脑。接收 `roboparty_teleop`
发布的 XR 手柄或手骨骼数据，转换为左右手六轴目标。

```text
roboparty_teleop → /pico/* → roboparty_dexhand_teleop
                            → /dexhand_left/cmd、/dexhand_right/cmd
                            → 板端 roboparty_dexhand_ros → CAN-FD → RP_Hand
```

支持两种输入模式：

- `controller`：将手柄 trigger/grip 映射为张开、抓握、捏合预设。
- `skeleton`：通过 DexPilot 将 26 点手骨骼映射到 RP_Hand 关节。

本包不连接 PICO SDK 或 CAN，输入发布与硬件驱动需分别启动。

## 安装与构建

环境：**Ubuntu 22.04 x86_64、ROS 2 Humble、系统 Python 3.10、uv**。
以下命令使用 Bash，在本仓库根目录执行；zsh 请将 `setup.bash` 换为 `setup.zsh`。

已安装 ROS 2 Humble 和 uv 后，首次安装构建工具并创建环境：

```bash
sudo apt install python3-colcon-common-extensions python3-pytest \
  python3-setuptools python3-yaml

source /opt/ros/humble/setup.bash
export PYTHONNOUSERSITE=1
uv venv --python /usr/bin/python3 --system-site-packages .venv
touch .venv/COLCON_IGNORE
uv sync --locked --python /usr/bin/python3
source .venv/bin/activate

.venv/bin/python /usr/bin/colcon build --symlink-install \
  --base-paths . --packages-select roboparty_dexhand_teleop
source install/setup.bash
```

必须使用系统 Python 并继承系统包，以使用 ROS 的二进制扩展和构建工具。
**uv 管理 Python 依赖，colcon 构建 ROS 包**；依赖版本由 `uv.lock` 固定。
已有按上述方式创建的 `.venv` 时跳过创建步骤，更新依赖后重新构建即可。

## 快速运行

每个新终端先在仓库根目录加载环境：

```bash
source /opt/ros/humble/setup.bash
export PYTHONNOUSERSITE=1
source .venv/bin/activate
source install/setup.bash
```

先启动 `roboparty_teleop`，确认 `/pico/*` 正常发布，再启动双手手柄映射：

```bash
ros2 launch roboparty_dexhand_teleop dual_dexhand_teleop.launch.py \
  input_mode:=controller grasp_scale:=0.2
```

运行中切换骨骼或手柄模式：

```bash
ros2 topic pub --once /teleop/hand_mode std_msgs/msg/String '{data: skeleton}'
# 切回手柄模式时执行：
ros2 topic pub --once /teleop/hand_mode std_msgs/msg/String '{data: controller}'
```

也可在启动命令中直接指定 `input_mode:=skeleton`。
默认输出为 `/dexhand_left/cmd` 和 `/dexhand_right/cmd`，消息类型是
`std_msgs/msg/Int32MultiArray`，内容为六轴整数目标（默认 0–10000）。

在另一个已加载环境的终端检查输出：

```bash
ros2 topic echo /dexhand_left/cmd --once
ros2 topic hz /dexhand_left/cmd
```

有效输入持续更新时，默认输出接近 50 Hz；没有有效输入时不会发布命令。
跨机器运行时，两端 `ROS_DOMAIN_ID` 必须一致，`ROS_LOCALHOST_ONLY=0`。

## 常用配置

| launch 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `input_mode` | `controller` | 初始模式：`controller` / `skeleton` |
| `left` / `right` | `true` / `true` | 是否启动对应侧节点 |
| `grasp_scale` | `1.0` | 手柄映射幅度，范围 `(0, 1]` |
| `config_file` | 包内默认 YAML | 自定义配置文件路径 |

例如，只启动左手：

```bash
ros2 launch roboparty_dexhand_teleop dual_dexhand_teleop.launch.py \
  left:=true right:=false input_mode:=controller grasp_scale:=0.2
```

预设姿态、话题和超时等配置见 [dexhand_teleop.yaml](config/dexhand_teleop.yaml)。
完整参数与运行时调节方法见 [接口说明](docs/INTERFACES.md)。

运行时注意：

- `grasp_scale` **仅影响手柄模式**；默认第一轴保持 8000，设为 `0.2` 不代表
  所有轴都限制到 2000。骨骼模式按 URDF 关节范围映射。
- 默认输入超时 250 ms 后停止发布旧目标；这不等于硬件停止或回零。
- `Ctrl+C` 退出映射节点。完整系统停止顺序见对应 SOP。

## 详细文档

- [话题与参数](docs/INTERFACES.md)：输入约定、模式切换、QoS、自定义配置。
- [验证、排错与开发](docs/DEVELOPMENT.md)：启动检查、测试、模型检查和依赖维护。
- [全身与双手 SOP](docs/HAND_TELEOP_SOP.md)：整机安装、骨骼遥操作与数据采集边界。
- [全身与手柄 SOP](docs/FULL_BODY_CONTROLLER_SOP.md)：全身 GMR、手柄遥操作和键盘控制。
