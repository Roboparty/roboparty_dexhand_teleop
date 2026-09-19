# 验证、排错与开发

先按 [README](../README.md) 安装并构建，在仓库根目录加载 ROS 和项目环境。
仅构建、运行单元测试或验证模型加载不需要 PICO 和灵巧手。

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
| 缺少 `pinocchio` / `nlopt` 或出现 NumPy ABI 错误 | 执行 `uv sync --locked --python /usr/bin/python3` 同步依赖、设置 `PYTHONNOUSERSITE=1`，避免混用其他项目环境 |
| `Package ... not found` | source 本次构建的 `install/setup.bash` |
| 虚拟环境中能导入依赖，但 ROS 节点不能 | 检查生成节点脚本首行是否指向 `.venv/bin/python`，按本文指定解释器重新构建 |
| `skeleton mode unavailable` | 运行下文的模型初始化检查；确认依赖、URDF 与 YAML 资源存在 |
| 有输入话题但无命令 | 检查当前模式、frame_id、26 点骨骼及四元数、时间戳是否更新、超时设置和日志 |
| 本机正常，机器人板收不到 | 检查两端 domain、localhost 限制、网络发现及 QoS；用 `topic info --verbose` 查看端点 |

## 测试与模型检查

```bash
.venv/bin/python /usr/bin/colcon test --base-paths . \
  --packages-select roboparty_dexhand_teleop --event-handlers console_direct+
.venv/bin/python /usr/bin/colcon test-result --verbose
.venv/bin/python -c 'from roboparty_dexhand_teleop.hand_retargeting import RPHandRetargeter; [RPHandRetargeter(s) for s in ("left", "right")]'
```

单元测试不覆盖真实 PICO 输入或硬件运动，完整链路需按
[手部 SOP](HAND_TELEOP_SOP.md) 验收。节点启动时若出现
`skeleton mode unavailable`，即使进程仍在运行，也不能视为骨骼模式可用。

## 依赖维护

`pyproject.toml` 声明 Python 依赖，`uv.lock` 固定解析版本。
PyPI 上机器人学 Pinocchio 的包名是 `pin`，导入名是 `pinocchio`。
ROS、colcon、PyYAML 和 pytest 由 apt 管理，不包含在 uv 锁定文件中。
当前配置限定 Python 3.10、Linux x86_64，其他平台尚未验证。

`tool.uv.package = false` 表示 uv 只安装依赖；ROS 包仍通过
`setup.py` / `setup.cfg` / `package.xml` 和 colcon 构建、注册。
首次创建 `.venv` 必须继承系统包，才能使用系统 ROS 和构建工具。
移动仓库或重建虚拟环境后需重新构建，以更新节点脚本中的解释器路径。

修改 `pyproject.toml` 后更新锁定文件，并将两者一起提交：

```bash
uv lock --python /usr/bin/python3
uv sync --locked --python /usr/bin/python3
uv pip check --python .venv/bin/python
```

依赖变更后重新构建，运行测试和模型初始化检查。NumPy、Pinocchio、NLopt
含有二进制兼容约束，需要一起验证。
