"""OpenBot Agent CLI - 控制台入口

通过运行 `python -m openbot.agents.cli` 启动交互式控制台
"""

import os
import sys
import logging
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from openbot.agents.core import OpenBotExecutor
from openbot.config import ConfigManager
from openbot.botflow.database import ChatMessage, ContentType


def setup_logging():
    """配置日志记录到文件，不在控制台输出"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"openbot_{datetime.now().strftime('%Y%m%d')}.log"

    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # 设置格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    # 添加空处理器到控制台，避免日志输出到控制台
    console_handler = logging.StreamHandler(open(os.devnull, "w"))
    console_handler.setLevel(logging.CRITICAL)
    root_logger.addHandler(console_handler)

    return log_file


class AgentCLI:
    """Agent 控制台界面"""

    def __init__(self):
        # 自定义主题配色 - 使用更优雅的配色方案
        custom_theme = Theme(
            {
                "info": "cyan",
                "warning": "yellow",
                "error": "red",
                "success": "green",
                "prompt": "bright_blue",
                "command": "bright_magenta",
                "dim": "dim white",
                "tool": "bright_cyan",
                "bot": "bright_green",
            }
        )
        self.console = Console(theme=custom_theme)
        self.agent: OpenBotExecutor | None = None
        self.running = False
        self.history_file = os.path.expanduser("~/.openbot_agent_history")
        self.session = PromptSession(
            history=FileHistory(self.history_file),
            auto_suggest=AutoSuggestFromHistory(),
        )
        # 使用更优雅的配色方案
        self.style = Style.from_dict(
            {
                "prompt": "#5f87ff bold",  # 柔和的蓝色
                "input": "#e4e4e4",  # 浅灰色输入
            }
        )
        self.prompt = "openbot> "
        self.channel_id = "cli_console"
        self._current_response_started = False

    def print_banner(self):
        """打印启动横幅"""
        self.console.print(
            Panel(
                "[bold bright_blue]OpenBot Agent CLI[/bold bright_blue]\n"
                "[dim]交互式智能代理控制台[/dim]\n\n"
                "[bright_magenta]命令:[/bright_magenta] [dim]/help[/dim] 显示帮助, [dim]/exit[/dim] 退出",
                border_style="bright_blue",
                padding=(1, 2),
            )
        )

    def print_help(self):
        """打印帮助信息"""
        table = Table(
            title="[bold bright_blue]可用命令[/bold bright_blue]",
            border_style="bright_blue",
            padding=(0, 1),
        )
        table.add_column("命令", style="bright_magenta", width=15)
        table.add_column("说明", style="white")

        table.add_row("/help", "显示此帮助信息")
        table.add_row("/exit, /quit", "退出程序")
        table.add_row("/clear", "清屏")
        table.add_row("/models", "显示已加载的模型")
        table.add_row("/tools", "显示可用工具")
        table.add_row("/status", "显示系统状态")

        self.console.print(table)
        self.console.print("\n[dim]直接输入消息与 Agent 对话[/dim]\n")

    def print_models(self):
        """打印模型信息"""
        if not self.agent:
            self.console.print("[error]Agent 未初始化[/error]")
            return

        table = Table(
            title="[bold bright_blue]已加载模型[/bold bright_blue]",
            border_style="bright_blue",
            padding=(0, 1),
        )
        table.add_column("名称", style="bright_cyan")
        table.add_column("模型对象", style="white")

        for name, model in self.agent.model_manager.list_models().items():
            model_info = getattr(model, "model_name", str(model.__class__.__name__))
            table.add_row(name, model_info)

        self.console.print(table)

    async def print_tools(self):
        """打印工具信息"""
        if not self.agent:
            self.console.print("[error]Agent 未初始化[/error]")
            return

        try:
            tools = await self.agent._tools_manager.get_tools()
            table = Table(
                title=f"[bold bright_blue]可用工具 ({len(tools)})[/bold bright_blue]",
                border_style="bright_blue",
                padding=(0, 1),
            )
            table.add_column("名称", style="bright_cyan")
            table.add_column("描述", style="white")

            for tool in tools:
                desc = getattr(tool, "description", "无描述")[:50]
                table.add_row(tool.name, desc)

            self.console.print(table)
        except Exception as e:
            self.console.print(f"[error]获取工具失败: {e}[/error]")

    def print_status(self):
        """打印系统状态"""
        table = Table(
            title="[bold bright_blue]系统状态[/bold bright_blue]",
            border_style="bright_blue",
            padding=(0, 1),
        )
        table.add_column("组件", style="bright_cyan", width=20)
        table.add_column("状态", style="white")

        agent_status = (
            "[success]运行中[/success]" if self.agent else "[warning]未初始化[/warning]"
        )
        cli_status = (
            "[success]运行中[/success]" if self.running else "[dim]已停止[/dim]"
        )
        # workspace 现在已经是绝对路径
        workspace = self.agent._agent_config.workspace if self.agent else "N/A"

        table.add_row("Agent", agent_status)
        table.add_row("CLI", cli_status)
        table.add_row("Workspace", workspace)

        self.console.print(table)

    def handle_streaming_message(self, message: ChatMessage) -> ChatMessage:
        """处理流式消息回调 - 优化输出格式"""
        step = message.metadata.get("step", "")
        content = message.content.strip() if message.content else ""

        if step == "model":
            # 模型回复 - 显示 bot 标识
            if not self._current_response_started:
                self._current_response_started = True
                self.console.print()  # 空行
            try:
                markdown = Markdown(content)
                self.console.print("[bot]openbot[/bot] > ", end="")
                self.console.print(markdown)
            except Exception:
                self.console.print(f"[bot]openbot[/bot] > {content}")
        elif step == "tools":
            # 工具调用 - 解析 CallTools [result] 格式，限制显示长度
            if content.startswith("CallTools [") and content.endswith("]"):
                tool_result = content[11:-1]  # 提取方括号内的内容
                # 限制显示长度，保持在一行内
                display_result = (
                    tool_result[:60] + "..." if len(tool_result) > 60 else tool_result
                )
                self.console.print(f"[tool]🛠️  CallTools [{display_result}][/tool]")
            elif content:
                # 限制显示长度
                display_content = content[:60] + "..." if len(content) > 60 else content
                self.console.print(f"[tool]🛠️  调用工具: {display_content}[/tool]")
        elif step.endswith(".before_agent") or step.endswith(".after_model"):
            # 中间件处理步骤 - 简化显示，跳过不重要的
            middleware_name = step.replace(".before_agent", "").replace(
                ".after_model", ""
            )
            if any(
                skip in step
                for skip in [
                    "TodoList",
                    "PatchToolCalls",
                    "Filesystem",
                    "Summarization",
                    "Skills",
                    "Memory",
                ]
            ):
                # 跳过这些中间件的显示
                pass
            else:
                self.console.print(f"[dim]⚙️  {middleware_name} 处理中...[/dim]")
        else:
            # 其他步骤 - 简化显示
            pass  # 不显示其他中间步骤

        return message

    async def _background_init(self):
        """后台初始化 Agent"""
        try:
            await self.agent.init_agent()
            self.console.print("[dim]✓ Agent 初始化完成[/dim]")
        except Exception as e:
            self.console.print(f"[error]Agent 后台初始化失败: {e}[/error]")
            logging.error(f"Background init failed: {e}", exc_info=True)

    async def _ensure_agent_ready(self):
        """确保 Agent 已准备好"""
        if not self.agent:
            self.console.print("[error]Agent 未创建[/error]")
            return False

        # 如果正在初始化，等待完成
        if self.agent.is_initializing:
            self.console.print("[info]Agent 正在初始化，请稍候...[/info]")
            while self.agent.is_initializing:
                await asyncio.sleep(0.1)

        # 如果未初始化，自动初始化
        if not self.agent.is_initialized:
            with self.console.status(
                "[info]正在初始化 Agent...[/info]", spinner="dots"
            ):
                try:
                    await self.agent.init_agent()
                except Exception as e:
                    self.console.print(f"[error]Agent 初始化失败: {e}[/error]")
                    return False

        return True

    async def chat(self, user_input: str):
        """与 Agent 对话"""
        # 确保 Agent 已准备好
        if not await self._ensure_agent_ready():
            return

        # 重置响应状态
        self._current_response_started = False

        # 显示用户输入
        self.console.print(f"[bright_blue]用户[/bright_blue] > {user_input}")

        chat_message = ChatMessage(
            channel_id=self.channel_id,
            content=user_input,
            role="user",
            content_type=ContentType.TEXT,
        )

        with self.console.status("[info]思考中...[/info]", spinner="dots"):
            try:
                reply_messages = await self.agent.achat(
                    chat_message,
                    streaming_callback=self.handle_streaming_message,
                )

                # 确保最后有空行
                if self._current_response_started:
                    self.console.print()

            except Exception as e:
                self.console.print(f"[error]对话出错: {e}[/error]")
                logging.error(f"Chat error: {e}", exc_info=True)

    async def run(self):
        """运行 CLI 主循环 - 快速启动，后台初始化"""
        self.running = True
        self.print_banner()

        # 快速创建 Agent（不执行耗时初始化）
        try:
            config_path = os.environ.get("OPENBOT_CONFIG_PATH", "config/config.json")
            config_manager = ConfigManager(config_path)
            config = config_manager.config

            self.agent = OpenBotExecutor(config.model_configs, config.agent_config)
            self.console.print("[success]✓ CLI 已启动[/success]\n")

            # 后台异步初始化
            asyncio.create_task(self._background_init())

        except Exception as e:
            self.console.print(f"[error]Agent 创建失败: {e}[/error]")
            logging.error(f"Agent creation failed: {e}", exc_info=True)
            return

        # 主循环
        while self.running:
            try:
                with patch_stdout(raw=True):
                    user_input = await self.session.prompt_async(
                        self.prompt,
                        style=self.style,
                        enable_history_search=True,
                    )

                command = user_input.strip()

                if not command:
                    continue

                # 处理命令
                if command.startswith("/"):
                    cmd = command.lower()

                    if cmd in ["/exit", "/quit", "/q"]:
                        self.running = False
                        break

                    elif cmd == "/help":
                        self.print_help()

                    elif cmd == "/clear":
                        self.console.clear()
                        self.print_banner()

                    elif cmd == "/models":
                        self.print_models()

                    elif cmd == "/tools":
                        await self.print_tools()

                    elif cmd == "/status":
                        self.print_status()

                    else:
                        self.console.print(f"[warning]未知命令: {command}[/warning]")

                else:
                    # 普通对话
                    await self.chat(command)

            except KeyboardInterrupt:
                self.console.print("\n[warning]使用 /exit 退出程序[/warning]")

            except EOFError:
                self.running = False
                break

        self.console.print("[bold bright_blue]再见！[/bold bright_blue]")


def main():
    """主入口函数"""
    # 配置日志到文件，不在控制台输出
    log_file = setup_logging()

    # 创建临时 console 用于启动消息
    temp_console = Console(
        theme=Theme(
            {
                "warning": "yellow",
                "dim": "dim white",
            }
        )
    )

    # 检查配置
    config_path = os.environ.get("OPENBOT_CONFIG_PATH", "config/config.json")
    if not os.path.exists(config_path):
        temp_console.print(f"[warning]配置文件不存在: {config_path}")
        temp_console.print("[dim]将使用默认配置运行[/dim]")

    # 运行 CLI
    cli = AgentCLI()
    try:
        asyncio.run(cli.run())
    except Exception as e:
        logging.error(f"CLI 运行错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
