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

from openbot.agents.core import OpenBotAgent
from openbot.common.config import ConfigManager
from openbot.common.datamodel import Question, AnswerFuture


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
                "tool": "dim white",
                "bot": "bright_green",
            }
        )
        self.console = Console(theme=custom_theme)
        self.agent: OpenBotAgent | None = None
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
        self._current_response_started = False

    def print_banner(self):
        """打印启动横幅"""
        OPENBOT_ASCII = """
 ██████╗ ██████╗  ██████╗  █████╗ ████████╗
██╔════╝ ██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝
██║      ██████╔╝██║   ██║███████║   ██║   
██║      ██╔══██╗██║   ██║██╔══██║   ██║   
╚██████╗ ██████╔╝╚██████╔╝██║  ██║   ██║   
 ╚═════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝   ╚═╝   

  OPENBOT AGENTS
"""
        self.console.print(
            Panel(
                f"[bold bright_blue]{OPENBOT_ASCII}[/bold bright_blue]\n"
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
        table.add_row("/model", "选择模型 (/model [模型名称])")
        table.add_row("/status", "显示系统状态")

        self.console.print(table)
        self.console.print("\n[dim]直接输入消息与 Agent 对话[/dim]\n")

    def print_models(self):
        """打印模型信息"""
        if not self.agent:
            self.console.print("[error]Agent 未初始化[/error]")
            return

        try:
            models = self.agent.list_models()
            if models:
                table = Table(
                    title="[bold bright_blue]已加载模型[/bold bright_blue]",
                    border_style="bright_blue",
                    padding=(0, 1),
                )
                table.add_column("名称", style="bright_cyan")

                for model in models:
                    table.add_row(model)

                self.console.print(table)
            else:
                self.console.print("[dim]没有可用模型[/dim]")
        except Exception as e:
            self.console.print(f"[error]获取模型失败: {e}[/error]")

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
        workspace = self.agent._agent_config.workspace if self.agent else "N/A"

        table.add_row("Agent", agent_status)
        table.add_row("CLI", cli_status)
        table.add_row("Workspace", workspace)

        self.console.print(table)

    async def stream_agent_response(self, user_input: str):
        """流式处理 Agent 响应"""
        has_responded = False

        # 开始显示加载状态
        status = self.console.status(
            "[bold bright_blue]思考中...[/bold bright_blue]", spinner="dots"
        )
        status.start()
        spinner_active = True

        # 创建 Question 对象
        question = Question(content=user_input)

        try:
            # 从 agent 获取回答 future
            answer_future: AnswerFuture = await self.agent.ask(question)

            # 处理详细响应
            async for answer_detail in answer_future.more_details():
                # 当有实际内容时停止加载状态
                if spinner_active:
                    status.stop()
                    spinner_active = False

                # 在第一次响应时打印前缀
                if not has_responded:
                    self._current_response_started = True
                    self.console.print()  # 空行
                    has_responded = True

                # 根据步骤打印详情
                if answer_detail.step == "model":
                    # 使用 markdown 格式渲染模型输出
                    try:
                        markdown = Markdown(
                            answer_detail.content, style="bold bright_blue"
                        )
                        self.console.print("[bot]openbot[/bot] > ", end="")
                        self.console.print(markdown)
                    except Exception:
                        self.console.print(
                            f"[bot]openbot[/bot] > {answer_detail.content}"
                        )
                elif answer_detail.step == "tools":
                    # 使用 markdown 格式渲染工具调用内容
                    self.console.print(f"[tool]🛠️  {answer_detail.method}:[/tool]")
                    try:
                        md_content = Markdown(answer_detail.content)
                        self.console.print(md_content)
                    except Exception:
                        self.console.print(f"[tool]  {answer_detail.content}[/tool]")
                else:
                    # 打印其他步骤，包括思考过程
                    try:
                        markdown = Markdown(answer_detail.content, style="dim white")
                        self.console.print(f"[dim]🤔 {answer_detail.step}:[/dim]")
                        self.console.print(markdown)
                    except Exception:
                        self.console.print(
                            f"[dim]🤔 {answer_detail.step}: {answer_detail.content}[/dim]"
                        )

            # 获取最终答案
            try:
                final_answer = answer_future.result()
                if final_answer.content and not has_responded:
                    if spinner_active:
                        status.stop()
                    self._current_response_started = True
                    self.console.print("[bot]openbot[/bot] > ", end="")
                    # 使用 markdown 格式渲染最终答案
                    try:
                        md_content = Markdown(final_answer.content, style="dim white")
                        self.console.print(md_content)
                    except Exception:
                        self.console.print(final_answer.content)
            except Exception as e:
                self.console.print(f"[error]获取最终答案失败: {e}[/error]")

        except Exception as e:
            self.console.print(f"[error]对话出错: {e}[/error]")
            logging.error(f"Chat error: {e}", exc_info=True)
        finally:
            # 确保加载状态已停止
            if spinner_active:
                status.stop()

        if has_responded:
            self.console.print()  # 空行

    async def chat(self, user_input: str):
        """与 Agent 对话"""
        # 重置响应状态
        self._current_response_started = False

        # 显示用户输入
        self.console.print(f"[bright_blue]用户[/bright_blue] > {user_input}")

        # 流式处理 Agent 响应
        await self.stream_agent_response(user_input)

    async def run(self):
        """运行 CLI 主循环"""
        self.running = True
        self.print_banner()

        # 创建并启动 Agent
        try:
            config_path = os.environ.get("OPENBOT_CONFIG_PATH", "config/config.json")
            # 尝试找到配置文件
            if not Path(config_path).exists():
                possible_paths = [
                    "config.json",
                    "src/openbot/config.json",
                    "examples/config.json",
                ]
                for path in possible_paths:
                    if Path(path).exists():
                        config_path = path
                        break

            config_manager = ConfigManager(config_path)
            config = config_manager.config

            # 创建 OpenBotAgent
            self.agent = OpenBotAgent(config.agent_config)

            # 启动 Agent
            with self.console.status("[info]正在启动 Agent...[/info]", spinner="dots"):
                await self.agent.start()

            self.console.print("[success]✓ Agent 启动成功[/success]\n")
            self.console.print(
                "... Ready to assist! What can I help you with today?",
                style="bright_green",
            )
            self.console.print()
            self.console.print(
                "  Tip: Alt-Enter for newline, Enter to submit", style="dim"
            )

        except Exception as e:
            self.console.print(f"[error]Agent 启动失败: {e}[/error]")
            logging.error(f"Agent startup failed: {e}", exc_info=True)
            return

        # 主循环
        while self.running:
            try:
                # 创建输入面板

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

                    elif cmd == "/model":
                        parts = command.split()
                        if len(parts) == 1:
                            # 列出可用模型
                            self.print_models()
                        elif len(parts) == 2:
                            # 切换到指定模型
                            model_name = parts[1]
                            success = self.agent.switch_model(model_name)
                            if success:
                                self.console.print(
                                    f"[success]已切换到模型: {model_name}[/success]"
                                )
                            else:
                                self.console.print(
                                    f"[error]切换模型失败: {model_name}[/error]"
                                )
                        else:
                            self.console.print("[dim]用法: /model [模型名称][/dim]")
                        self.console.print()

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

        # 停止 Agent
        if self.agent:
            with self.console.status("[info]正在停止 Agent...[/info]", spinner="dots"):
                await self.agent.stop()

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

    # 运行 CLI
    cli = AgentCLI()
    try:
        asyncio.run(cli.run())
    except Exception as e:
        logging.error(f"CLI 运行错误: {e}", exc_info=True)
        sys.exit(1)


async def test_mode():
    """测试模式，用于验证思考过程的显示"""
    cli = AgentCLI()
    cli.running = True
    cli.print_banner()

    try:
        # 加载配置
        config_path = os.environ.get("OPENBOT_CONFIG_PATH", "config/config.json")
        if not Path(config_path).exists():
            possible_paths = [
                "config.json",
                "src/openbot/config.json",
                "examples/config.json",
            ]
            for path in possible_paths:
                if Path(path).exists():
                    config_path = path
                    break

        config_manager = ConfigManager(config_path)
        config = config_manager.config

        # 创建并启动 Agent
        cli.agent = OpenBotAgent(config.agent_config)
        with cli.console.status("[info]正在启动 Agent...[/info]", spinner="dots"):
            await cli.agent.start()

        cli.console.print("[success]✓ Agent 启动成功[/success]\n")
        cli.console.print("... 测试模式: 发送测试消息...", style="bright_green")
        cli.console.print()

        # 发送测试消息
        test_message = "你好，今天天气怎么样？"
        cli.console.print(f"[bright_blue]用户[/bright_blue] > {test_message}")
        await cli.stream_agent_response(test_message)

        # 等待几秒钟，确保所有输出都显示
        await asyncio.sleep(5)

    except Exception as e:
        cli.console.print(f"[error]测试失败: {e}[/error]")
        logging.error(f"Test failed: {e}", exc_info=True)
    finally:
        # 停止 Agent
        if cli.agent:
            with cli.console.status("[info]正在停止 Agent...[/info]", spinner="dots"):
                await cli.agent.stop()
        cli.console.print("[bold bright_blue]测试完成！[/bold bright_blue]")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        asyncio.run(test_mode())
    else:
        main()
