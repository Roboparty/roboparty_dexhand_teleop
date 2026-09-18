# roboparty_dexhand_teleop

`roboparty_dexhand_teleop` 是操作端的 RP_Hand 遥操作映射包。它订阅
`roboparty_teleop` 发布的标准化 XR 手柄与手骨骼数据，将其转换为左右手六轴
目标。它不初始化 PICO SDK、不打开 CAN，也不依赖 `dexhand_py`。

Ubuntu 22.04 上从安装到“全身 + 双手”验收的完整步骤见
[`docs/HAND_TELEOP_SOP.md`](docs/HAND_TELEOP_SOP.md)。

只运行全身 GMR 与手柄遥操作时，可直接参考
[`docs/FULL_BODY_CONTROLLER_SOP.md`](docs/FULL_BODY_CONTROLLER_SOP.md)。

本 README 的命令使用仓库根目录作为构建目录；SOP 中的 `~/roboparty_ws`
是另一种工作空间布局，使用时请对应替换路径。手部桥接使用自己的虚拟环境，
无需复用 `roboparty_teleop` 的 GMR 环境。

## 环境要求

| 项目 | 本机已验证配置 / 说明 |
| --- | --- |
| 操作系统 | Ubuntu 22.04，x86_64 |
| ROS | ROS 2 Humble，安装在 `/opt/ros/humble` |
| Python | `/usr/bin/python3`，3.10.12 |
| 环境与构建工具 | uv 0.12.2、colcon、ament_python |
| 骨骼计算依赖 | Pinocchio 2.7.0、NLopt 2.7.1、NumPy 1.26.4 |
| 真实输入 | `roboparty_teleop` 发布符合下文约定的 `/pico/*` 话题 |
| 真机执行 | 板端 `roboparty_dexhand_ros` 与 CAN-FD 驱动，单独部署 |

仅构建、运行单元测试或验证模型加载不需要 PICO 和灵巧手。以下 uv 固定依赖
在上述平台验证过，其他架构和 ROS 发行版尚未验证。

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

模式切换默认使用 300 ms 插值；首次收到目标时直接输出，不执行启动插值。
切换到没有有效输入的模式时停止发布，不会自动回退到另一模式。
输入超过 `input_timeout_ms` 后不再发布旧目标；这不等同于向硬件发送停止或回零指令。

## 构建

### uv + ROS 2 Humble（Ubuntu 22.04）

以下命令在**本仓库根目录**执行，构建产物为本目录下的 `build/`、`install/`
和 `log/`。需要已安装 ROS 2 Humble 和 `uv`。首次安装系统构建工具：

```bash
sudo apt install python3-colcon-common-extensions python3-pytest \
  python3-setuptools python3-yaml
```

安装前可检查 `uv --version`、`/usr/bin/python3 --version`，以及
`test -f /opt/ros/humble/setup.bash`。若 ROS 或 uv 尚未安装，先完成其安装，
再执行下面的环境创建步骤。

使用 `/usr/bin/python3`（Ubuntu 22.04 的 Python 3.10），不要使用默认的
Python 3.12、Conda 或 uv 下载的独立 Python；ROS 的二进制扩展需要兼容的
系统解释器。虚拟环境继承系统包，以使用 apt 安装的 ROS、colcon 和测试工具。
Pinocchio、NLopt 和 NumPy 安装在项目虚拟环境中。

下面三个步骤在**同一个终端**按顺序执行，每条命令成功后再执行下一条。
复制代码块时保留换行，不要把多条命令拼成一行。下划线 `_` 和参数前的
`--` 无需添加反斜杠；只有行末的 `\` 表示当前命令在下一行继续。

**1. 首次创建并激活项目环境**

```bash
# 加载 ROS 2 Humble，让当前终端能够找到 ROS 命令和 Python 包。
# 以下使用 Bash；zsh 终端请改为 source /opt/ros/humble/setup.zsh。
source /opt/ros/humble/setup.bash

# 禁用用户级 Python 包目录，避免 ~/.local 中的包干扰项目依赖。
export PYTHONNOUSERSITE=1

# 用系统 Python 3.10 创建 .venv，并允许使用系统安装的 ROS、colcon 等包。
# 已有按此方式创建的 .venv 时，跳过这条创建命令。
uv venv --python /usr/bin/python3 --system-site-packages .venv

# 创建忽略标记，防止 colcon 构建时扫描虚拟环境目录。
touch .venv/COLCON_IGNORE

# 按 uv.lock 的固定版本安装依赖到 .venv；此命令不会构建 ROS 包。
uv sync --locked --python /usr/bin/python3

# 激活虚拟环境，使当前终端的 python 等命令优先使用 .venv。
source .venv/bin/activate
```

**2. 构建 ROS 包**

```bash
# 显式指定解释器，保证生成的节点使用 .venv，而非 /usr/bin/colcon 的系统 Python。
# 下面两行是一条完整的构建命令，第一行末尾的反斜杠用于续行。
.venv/bin/python /usr/bin/colcon build --symlink-install \
  --base-paths . --packages-select roboparty_dexhand_teleop
```

**3. 构建成功后加载本项目环境**

```bash
# 单独执行，让 ROS 能找到刚构建的包；不要拼接到上面的构建命令后面。
# zsh 终端请改为 source install/setup.zsh。
source install/setup.bash
```

`pyproject.toml` 声明 Python 侧依赖，`uv.lock` 固定完整依赖版本，已在 x86_64、Python 3.10.12、
ROS 2 Humble 下验证 NumPy 1.26.4 / Pinocchio 2.7.0 / NLopt 2.7.1。
PyPI 上机器人学 Pinocchio 的包名是 `pin`，导入名才是 `pinocchio`。
系统 ROS/colcon/PyYAML/pytest 的版本由 apt 管理，不包含在此锁定文件中。
本包保留 ROS `setup.py` / `setup.cfg` / `package.xml` 构建方式。
`pyproject.toml` 设置 `tool.uv.package = false`，因此 `uv sync` 只安装依赖，
ROS 包仍通过 `colcon build` 构建与注册。Python 限定为 3.10，依赖解析限定 Linux x86_64。
首次安装必须先执行上面的 `uv venv --system-site-packages`，再执行 `uv sync`，
否则自动创建的环境无法继承系统 ROS 和构建工具。
移动仓库或重建虚拟环境后需重新构建，以更新节点脚本中的解释器路径。

环境创建命令参考 [uv 环境管理文档](https://docs.astral.sh/uv/pip/environments/)，
依赖同步参考 [uv 锁定与同步文档](https://docs.astral.sh/uv/concepts/projects/sync/)。

已有按上述步骤创建的 `.venv` 时无需重复创建，同步仓库锁定的依赖只需重新执行
`uv sync --locked --python /usr/bin/python3`。同步后重新执行构建命令。
维护依赖时修改 `pyproject.toml`，再更新锁定文件并验证；将这两个文件一起提交：

```bash
uv lock --python /usr/bin/python3
uv sync --locked --python /usr/bin/python3
uv pip check --python .venv/bin/python
```

更改版本后应重新构建、运行测试并检查骨骼模型初始化。不要只升级 NumPy，
而忽略 Pinocchio、NLopt 等二进制扩展的兼容性。

构建后运行测试，并确认左右手骨骼模型可以初始化：

```bash
.venv/bin/python /usr/bin/colcon test --base-paths . \
  --packages-select roboparty_dexhand_teleop --event-handlers console_direct+
.venv/bin/python /usr/bin/colcon test-result --verbose
.venv/bin/python -c 'from roboparty_dexhand_teleop.hand_retargeting import RPHandRetargeter; [RPHandRetargeter(s) for s in ("left", "right")]'
```

现有单元测试不覆盖真实 PICO 输入或硬件运动。节点启动时若出现
`skeleton mode unavailable`，即使进程仍在运行，也不能视为骨骼模式可用。

### 仅使用系统 apt 环境（替代方案）

如果不用 uv，可以将依赖全部交给 apt；请在未激活虚拟环境的新终端使用该方案：

```bash
sudo apt install python3-colcon-common-extensions python3-pytest \
  ros-humble-pinocchio python3-nlopt python3-numpy python3-yaml

source /opt/ros/humble/setup.bash
export PYTHONNOUSERSITE=1
# 使用独立产物目录，避免复用 uv 环境生成的脚本。
colcon --log-base log-system build --build-base build-system \
  --install-base install-system --symlink-install --base-paths . \
  --packages-select roboparty_dexhand_teleop
source install-system/setup.bash
```

apt 方案的 Pinocchio 版本由 ROS 软件源决定，不等同于上述 uv 固定版本。

## 运行

使用 uv 方案时，每个新终端先在仓库根目录执行：

```bash
source /opt/ros/humble/setup.bash
export PYTHONNOUSERSITE=1
source .venv/bin/activate
source install/setup.bash
```

apt 替代方案使用 `source install-system/setup.bash`，省略 `.venv` 激活步骤。
跨机器通信时，操作端与机器人板的 `ROS_DOMAIN_ID` 必须一致，
`ROS_LOCALHOST_ONLY` 应为 `0`；仅本机测试可使用独立 domain 与
`ROS_LOCALHOST_ONLY=1`。

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

切回手柄模式：

```bash
ros2 topic pub --once /teleop/hand_mode std_msgs/msg/String \
  '{data: controller}'
```

也可直接以骨骼模式启动，或只启动左手：

```bash
ros2 launch roboparty_dexhand_teleop dual_dexhand_teleop.launch.py input_mode:=skeleton
```

```bash
ros2 launch roboparty_dexhand_teleop dual_dexhand_teleop.launch.py \
  left:=true right:=false input_mode:=controller grasp_scale:=0.2
```

以上启动命令选择其一，不要重复启动相同名称的节点。

`grasp_scale` 当前只作用于 **controller** 模式的 trigger/grip 映射，
不会缩放 skeleton 输出。默认预设中第一轴保持 8000，因此 `grasp_scale:=0.2`
也不代表所有轴均限制到 2000；骨骼模式按 URDF 关节范围映射到 0–10000。

输入必须符合 `roboparty_teleop` 的标准化消息约定：手柄使用 `sensor_msgs/Joy`
的 `axes[0:2]` 表示 trigger/grip，骨骼使用包含 26 个有效姿态的
`geometry_msgs/PoseArray`；两者的 `header.frame_id` 默认必须为
`xrobot_right_handed`。错误坐标系、无效四元数或重复的非零时间戳可能导致输入
被拒绝或不刷新。没有新鲜有效输入时，不发布命令属于正常行为。

默认输出：

```text
左手 -> /dexhand_left/cmd
右手 -> /dexhand_right/cmd
```

CAN 接口与 node ID 不属于本包配置；它们由机器人板上的
`roboparty_dexhand_ros` 决定。

## 话题与参数

下表中的 `<side>` 为 `left` 或 `right`。

| 方向 | 默认话题 | ROS 消息类型 | 含义 |
| --- | --- | --- | --- |
| 订阅 | `/pico/controller/<side>/joy` | `sensor_msgs/msg/Joy` | `axes[0]` 为 trigger，`axes[1]` 为 grip，按 0–1 映射 |
| 订阅 | `/pico/hand/<side>/poses` | `geometry_msgs/msg/PoseArray` | canonical 26 点骨骼，位置单位为米，四元数为 xyzw |
| 订阅 | `/pico/hand/<side>/active` | `std_msgs/msg/Bool` | `false` 清除当前骨骼目标；新的有效 pose 可恢复目标 |
| 订阅 | `/teleop/hand_mode` | `std_msgs/msg/String` | 同时请求左右手切换到 `controller` 或 `skeleton` |
| 发布 | `/dexhand_<side>/cmd` | `std_msgs/msg/Int32MultiArray` | 六轴整数目标，默认范围 0–10000，不是角度或真实反馈 |

骨骼索引顺序不能任意替换；转换与校验定义见
[`hand_coordinates.py`](roboparty_dexhand_teleop/hand_coordinates.py) 和
[`pico_contract.py`](roboparty_dexhand_teleop/pico_contract.py)。骨骼输出关节顺序为
`finger11, finger12, finger21, finger31, finger41, finger51`。
XR 输入订阅使用 best-effort、depth 1；命令输出使用 reliable、depth 1。

默认配置见 [`config/dexhand_teleop.yaml`](config/dexhand_teleop.yaml)。

| 参数 | 默认值 | 设置方式与说明 |
| --- | --- | --- |
| `left` / `right` | `true` / `true` | launch 参数，决定启动哪侧节点 |
| `input_mode` | `controller` | launch 参数或节点参数，也可通过模式话题切换 |
| `grasp_scale` | `1.0` | launch 参数或动态节点参数，范围 `(0, 1]`，仅影响手柄输入 |
| `config_file` | 包内默认 YAML | launch 参数，指定自定义配置文件 |
| `publish_hz` | `50.0` | YAML 节点参数，有效目标发布频率上限 |
| `input_timeout_ms` | `250.0` | YAML 节点参数，按本地输入更新时间判断；`0` 禁用超时 |
| `transition_ms` | `300.0` | YAML 节点参数，模式切换插值时长 |
| `enable_skeleton` | `true` | YAML 节点参数，启动时是否初始化骨骼求解器 |
| `expected_frame_id` | `xrobot_right_handed` | YAML 节点参数，输入消息坐标系检查 |

除 `input_mode`、`grasp_scale` 外，上表中的节点参数均在初始化时读取，
修改 YAML 后需重启。`enable_skeleton` 不是 launch 参数；仅使用手柄且希望跳过
骨骼初始化时，在自定义 YAML 的两侧节点中将它设为 `false`。
自定义 YAML 保留 `dexhand_teleop_left` / `dexhand_teleop_right` 节点名；
launch 会用其 `input_mode`、`grasp_scale` 参数（包括默认值）覆盖 YAML 中的同名值，
这两项应在 launch 命令中显式设置。

```bash
ros2 launch roboparty_dexhand_teleop dual_dexhand_teleop.launch.py \
  config_file:=/absolute/path/to/dexhand_teleop.yaml
```

运行时调整左右手柄映射幅度：

```bash
ros2 param set /dexhand_teleop_left grasp_scale 0.2
ros2 param set /dexhand_teleop_right grasp_scale 0.2
```

## 启动验收与排错

在另一个已加载相同 ROS 环境的终端检查：

```bash
ros2 node list
ros2 topic info /pico/controller/left/joy --verbose
ros2 topic echo /pico/controller/left/joy --once --qos-reliability best_effort
ros2 topic echo /dexhand_left/cmd --once
ros2 topic hz /dexhand_left/cmd
```

双手启动时应出现 `/dexhand_teleop_left` 和 `/dexhand_teleop_right`。
追踪有效且输入持续更新时，默认目标输出接近 50 Hz；没有输入时 `echo --once`
会等待消息，`hz` 不会显示频率。骨骼模式将输入检查话题换为
`/pico/hand/left/poses`，右手将路径中的 `left` 换为 `right`。

| 现象 | 检查与处理 |
| --- | --- |
| `No module named rclpy` 或 Python 扩展导入失败 | 确认 `.venv/bin/python --version` 为 3.10、环境继承系统包，并已 source Humble |
| 缺少 `pinocchio` / `nlopt` 或出现 NumPy ABI 错误 | 用 `.venv/bin/python` 安装固定依赖、设置 `PYTHONNOUSERSITE=1`，避免混用其他项目环境 |
| `Package ... not found` | source 本次构建的 `install/setup.bash`；apt 方案为 `install-system/setup.bash` |
| 虚拟环境中能导入依赖，但 ROS 节点不能 | 检查生成节点脚本首行是否指向 `.venv/bin/python`，按本文指定解释器重新构建 |
| `skeleton mode unavailable` | 运行上面的模型初始化检查；确认依赖、URDF 与 YAML 资源存在 |
| 有输入话题但无命令 | 检查当前模式、frame_id、26 点骨骼及四元数、时间戳是否更新、超时设置和日志 |
| 本机正常，机器人板收不到 | 检查两端 domain、localhost 限制、网络发现及 QoS；用 `topic info --verbose` 查看端点 |

本次环境验收通过 15 项单元测试，以及双节点两种模式启动/退出、模拟手柄
目标输出、超时停发和左右手骨骼求解。真实 PICO 链路与硬件运动仍需按 SOP 验收。
退出映射节点使用 `Ctrl+C`；完整系统的停止顺序见手部 SOP。

## 独立终端键盘控制全身跟随

键盘节点运行在**操作端电脑**，调用 `roboparty_teleop` 的全身跟随服务。
新增入口需要先按上文步骤重新构建本包。随后打开独立交互终端，在本仓库根目录运行：

```bash
source /opt/ros/humble/setup.bash
export PYTHONNOUSERSITE=1
source .venv/bin/activate
source install/setup.bash
ros2 run roboparty_dexhand_teleop teleop_keyboard
```

使用系统 apt 构建方案时，省略 `.venv` 激活，并改为加载
`install-system/setup.bash`。

- `a`：调用 `/start_teleop`，请求开启全身跟随。
- `x`：调用 `/stop_teleop`，请求返回默认站姿参考。
- `q` 或 `Ctrl+C`：只退出键盘程序；需要回站姿时先按 `x`。

按键无需回车，操作时让键盘控制终端获得焦点。原有手部 launch 保持运行；
键盘节点不放入 launch，也不切换手部模式或控制灵巧手启停。

先在 `roboparty_teleop` 仓库中运行 `./scripts/rp1_deploy/run_local.sh`
（详见 [全身运行说明](docs/FULL_BODY_CONTROLLER_SOP.md)），并确认对应
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

## 数据采集边界

本包输出的是目标，不是真实硬件反馈。可复现数据集应同时记录：

- `/pico/controller/*`、`/pico/hand/*`：标准化 XR 输入；
- `/dexhand_left/cmd`、`/dexhand_right/cmd`：六轴手部目标；
- 板端 dexhand 状态话题：六轴实际位置与设备状态；
- `/tracking/current_reference`、`/action`、`/joint_states`、`/imu`：全身参考、
  policy 输出和机器人实际状态。

板端 dexhand 状态话题将在 `roboparty_dexhand_ros` 的接口阶段补齐。
