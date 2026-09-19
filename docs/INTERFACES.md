# 话题与参数

构建与启动见 [README](../README.md)。本包只发布六轴目标，CAN 接口与 Node ID
由机器人板上的 `roboparty_dexhand_ros` 配置。

## 输入与模式行为

手柄模式将 trigger/grip 映射为 open、grasp、pinch 预设；骨骼模式通过
DexPilot、RP_Hand URDF 和关节范围将 canonical 26 点骨骼映射为六轴位置。
输入的 `header.frame_id` 默认必须为 `xrobot_right_handed`。错误坐标系、
无效四元数或重复的非零时间戳可能导致输入被拒绝或不刷新。

模式切换默认使用 300 ms 插值；首次收到目标时直接输出。
切换到没有有效输入的模式时停止发布，不会自动回退到另一模式。
输入超过 `input_timeout_ms` 后不再发布旧目标；这不等同于向硬件发送停止或回零指令。
手部映射失败不会修改全身参考 `/tracking/current_reference`。

## 话题与配置

下表中的 `<side>` 为 `left` 或 `right`。

| 方向 | 默认话题 | ROS 消息类型 | 含义 |
| --- | --- | --- | --- |
| 订阅 | `/pico/controller/<side>/joy` | `sensor_msgs/msg/Joy` | `axes[0]` 为 trigger，`axes[1]` 为 grip，按 0–1 映射 |
| 订阅 | `/pico/hand/<side>/poses` | `geometry_msgs/msg/PoseArray` | canonical 26 点骨骼，位置单位为米，四元数为 xyzw |
| 订阅 | `/pico/hand/<side>/active` | `std_msgs/msg/Bool` | `false` 清除当前骨骼目标；新的有效 pose 可恢复目标 |
| 订阅 | `/teleop/hand_mode` | `std_msgs/msg/String` | 同时请求左右手切换到 `controller` 或 `skeleton` |
| 发布 | `/dexhand_<side>/cmd` | `std_msgs/msg/Int32MultiArray` | 六轴整数目标，默认范围 0–10000，不是角度或真实反馈 |

骨骼索引顺序不能任意替换；转换与校验定义见
[`hand_coordinates.py`](../roboparty_dexhand_teleop/hand_coordinates.py) 和
[`pico_contract.py`](../roboparty_dexhand_teleop/pico_contract.py)。骨骼输出关节顺序为
`finger11, finger12, finger21, finger31, finger41, finger51`。
XR 输入订阅使用 best-effort、depth 1；命令输出使用 reliable、depth 1。

默认配置见 [`config/dexhand_teleop.yaml`](../config/dexhand_teleop.yaml)。

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
