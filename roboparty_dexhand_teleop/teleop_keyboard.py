"""Control full-body deploy services from a dedicated Linux terminal."""

import os
import select
import sys
import termios
import time
import tty

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_srvs.srv import Trigger


class TeleopKeyboard(Node):
    """Send asynchronous requests without blocking keyboard input."""

    def __init__(self):
        super().__init__("teleop_keyboard")
        self.declare_parameter("start_service", "/start_teleop")
        self.declare_parameter("stop_service", "/stop_teleop")
        self.service_clients = {
            "a": self.create_client(Trigger, self.get_parameter("start_service").value),
            "x": self.create_client(Trigger, self.get_parameter("stop_service").value),
        }
        self.pending = {}
        self.last_key_at = {}

    def handle_key(self, key):
        key = key.lower()
        if key not in self.service_clients:
            return
        now = time.monotonic()
        previous = self.last_key_at.get(key)
        self.last_key_at[key] = now
        # Suppress terminal auto-repeat even after a quick service response.
        if previous is not None and now - previous < 0.5:
            return
        if key in self.pending:
            print("该请求仍在等待回复，请勿重复发送。", flush=True)
            return
        # Keep return-to-stand available while a start request is pending.
        if key == "a" and "x" in self.pending:
            print("返回站姿请求仍在等待回复，请稍后再开启。", flush=True)
            return
        client = self.service_clients[key]
        if not client.service_is_ready():
            print(f"服务未就绪：{client.srv_name}；请检查 teleop 和 ROS 环境。", flush=True)
            return
        try:
            future = client.call_async(Trigger.Request())
        except Exception as exc:
            print(f"请求发送失败：{exc}", flush=True)
            return
        self.pending[key] = (future, now)
        print(f"已发送：{client.srv_name}，等待回复……", flush=True)

    def poll_requests(self):
        for key, (future, sent_at) in list(self.pending.items()):
            if future.done():
                del self.pending[key]
                try:
                    response = future.result()
                    if response.success:
                        print(f"已接受过渡请求（不代表机器人已到位）：{response.message}", flush=True)
                    else:
                        print(f"请求失败：{response.message}", flush=True)
                except Exception as exc:
                    print(f"服务调用失败：{exc}", flush=True)
            elif time.monotonic() - sent_at >= 5.0:
                del self.pending[key]
                future.cancel()
                print("等待服务回复超时；请求可能已执行，请确认实际状态。", flush=True)


def main(args=None):
    if not sys.stdin.isatty():
        print("键盘控制需要交互终端，请在独立终端中运行 ros2 run。", file=sys.stderr)
        return 1
    terminal_fd = sys.stdin.fileno()
    original_settings = termios.tcgetattr(terminal_fd)
    node = None
    try:
        rclpy.init(args=args)
        node = TeleopKeyboard()
        print(
            "全身遥操控制\n"
            "[a] 开启跟随  [x] 返回默认站姿参考  [q / Ctrl+C] 退出键盘程序\n"
            "无需回车。退出不会停止跟随；需要回站姿时先按 x。\n"
            "这些按键不控制灵巧手启停。",
            flush=True,
        )
        tty.setcbreak(terminal_fd)
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.0)
            node.poll_requests()
            readable, _, _ = select.select([sys.stdin], [], [], 0.05)
            if readable:
                key = os.read(terminal_fd, 1).decode("ascii", errors="ignore")
                if not key or key.lower() == "q":
                    break
                node.handle_key(key)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        termios.tcsetattr(terminal_fd, termios.TCSADRAIN, original_settings)
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0
