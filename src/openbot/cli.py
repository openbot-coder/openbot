"""
OpenBot CLI - 交互式控制台界面
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("agentscope").setLevel(logging.WARNING)

from rich.console import Console
from rich.prompt import Prompt
from rich.theme import Theme
from rich.markdown import Markdown

custom_theme = Theme(
    {
        "info": "dim cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "tool": "magenta",
    }
)

console = Console(theme=custom_theme)
from agentscope.pipeline import stream_printing_messages
from openbot.gateway.botflow import BotFlow
from openbot.agents.tool_manger import ToolKitManager
from openbot.config import BotFlowConfig


def print_banner():
    """打印欢迎横幅"""
    console.print()
    console.print(
        "╔══════════════════════════════════════════════════════════╗",
        style="bold cyan",
    )
    console.print(
        "║         🤖 OpenBot CLI - 多智能体交互式会话              ║",
        style="bold cyan",
    )
    console.print(
        "╚══════════════════════════════════════════════════════════╝",
        style="bold cyan",
    )
    console.print()


def print_help():
    """打印帮助信息"""
    console.print("\n[bold yellow]可用命令:[/bold yellow]")
    console.print("  [green]/help[/green]      - 显示帮助信息")
    console.print("  [green]/clear[/green]     - 清除会话历史")
    console.print("  [green]/history[/green]   - 显示当前会话消息数")
    console.print("  [green]/stats[/green]     - 显示会话统计信息")
    console.print("  [green]/models[/green]    - 显示可用模型列表")
    console.print("  [green]/tools[/green]     - 显示可用工具列表")
    console.print("  [green]/model[/green]     - 切换当前使用的模型")
    console.print("  [green]/exit[/green]      - 退出程序")
    console.print()


def print_session_info(bot_flow: BotFlow, message_count: int, session_start: datetime):
    """打印会话信息"""
    available_models = list(bot_flow.config.model_configs.keys())

    console.print(
        "┌──────────────────────────────────────────────────────────┐", style="dim"
    )
    console.print(
        "│                           会话信息                         │", style="dim"
    )
    console.print(
        "├──────────────────────────────────────────────────────────┤", style="dim"
    )
    console.print(f"│  可用模型: {', '.join(available_models):<30} │")
    console.print(f"│  消息历史: {message_count} 条消息{' ' * 25}│")
    console.print(f"│  会话时长: {datetime.now() - session_start}{' ' * 20}│")
    console.print(
        "└──────────────────────────────────────────────────────────┘", style="dim"
    )
    console.print()
    console.print("[dim]输入 /help 获取帮助, /exit 退出[/dim]")
    console.print()


def print_stats(message_count: int, session_start: datetime):
    """打印会话统计"""
    duration = datetime.now() - session_start
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    console.print("\n[bold cyan]会话统计:[/bold cyan]")
    console.print(f"  会话时长: {hours:02d}:{minutes:02d}:{seconds:02d}")
    console.print(f"  消息总数: {message_count}\n")


def print_models(bot_flow: BotFlow):
    """打印可用模型列表"""
    console.print("\n[bold cyan]可用模型:[/bold cyan]")

    for i, (name, config) in enumerate(bot_flow.config.model_configs.items(), 1):
        model_type = config.get("model_type", "unknown")
        model_name = config.get("model_name", name)
        console.print(f"  {i}. [white]{name}[/white]")
        console.print(f"      类型: {model_type}, 模型: {model_name}")
    console.print()


def print_tools(bot_flow: BotFlow):
    """打印可用工具列表"""
    tools = bot_flow.toolkit_manager.list_tools()

    console.print(f"\n[bold cyan]可用工具 ({len(tools)}):[/bold cyan]")

    for i, tool in enumerate(tools[:20], 1):
        console.print(f"  {i}. [white]{tool}[/white]")

    if len(tools) > 20:
        console.print(f"  [dim]... 还有 {len(tools) - 20} 个工具[/dim]")
    console.print()


class OpenBotCLI:
    def __init__(self, homespace: str = None):
        if homespace:
            self.homespace = homespace
        elif os.getenv("OPENBOT_HOMESPACE"):
            self.homespace = os.getenv("OPENBOT_HOMESPACE")
        else:
            default_path = Path(__file__).parent.parent.parent / ".openbot"
            if default_path.exists():
                self.homespace = str(default_path)
            else:
                self.homespace = str(Path.home() / ".openbot")

        os.environ["OPENBOT_HOMESPACE"] = self.homespace

        self.bot_flow = None
        self.session_start = datetime.now()
        self.message_count = 0
        self.current_model = "doubao_auto"
        self.running = True

    async def initialize(self):
        """初始化 BotFlow"""
        console.print("[cyan]初始化 OpenBot...[/cyan]")
        console.print(f"[dim]工作目录: {self.homespace}[/dim]")

        self.bot_flow = BotFlow(homespace=self.homespace)
        await self.bot_flow.initialize()

        available_models = list(self.bot_flow.config.model_configs.keys())
        if available_models:
            self.current_model = available_models[0]

        console.print("[success]✅ OpenBot 初始化完成[/success]")
        console.print(f"[dim]可用模型: {', '.join(available_models)}[/dim]")
        console.print()

    def _clean_response_content(self, content):
        """清理响应内容，去除包装格式"""
        if not isinstance(content, str):
            content = str(content)

        content = content.strip()

        if content.startswith("[{'type': 'text'") or content.startswith("[{"):
            try:
                import ast

                parsed = ast.literal_eval(content)
                if isinstance(parsed, list) and len(parsed) > 0:
                    first_item = parsed[0]
                    if isinstance(first_item, dict):
                        content = first_item.get("text", content)
            except:
                pass

        return content

    async def chat(self, message: str):
        """处理聊天消息"""
        if not message.strip():
            return

        try:
            agent = self.bot_flow.create_agent(
                name="cli_assistant",
                system_prompt="你是一个有用的智能助手",
                model_id=self.current_model,
            )
            agent.set_console_output_enabled(False)

            from agentscope.message import Msg

            user_msg = Msg(name="user", content=message, role="user")

            with console.status("[dim]🤔 处理中...[/dim]"):
                reply_content = []
                async for msg, last in stream_printing_messages(
                    agents=[agent],
                    coroutine_task=agent([user_msg]),
                ):
                    if not hasattr(msg, "content") or not msg.content:
                        continue

                    for content_block in msg.content:
                        if not isinstance(content_block, dict):
                            continue

                        block_type = content_block.get("type")
                        if block_type == "tool_use":
                            tool_name = content_block.get("name", "unknown")
                            console.print(
                                f"[magenta]🔧 调用工具: {tool_name}[/magenta]"
                            )
                        elif block_type == "tool_result":
                            output = content_block.get("output", [])
                            if output:
                                for o in output:
                                    if isinstance(o, dict) and o.get("type") == "text":
                                        console.print(
                                            f"[magenta]📤 工具返回: {o.get('text', '')}[/magenta]"
                                        )
                        elif msg.role == "assistant" and block_type == "text":
                            text_content = content_block.get("text", "")
                            if text_content:
                                reply_content.append(text_content)

            if reply_content:
                for content_block in reply_content:
                    markdown_content = Markdown(content_block)
                    console.print("[cyan]🤖:[/cyan]", end=" ")
                    console.print(markdown_content)

            console.print()
            self.message_count += 2

        except Exception as e:
            console.print(f"[error]❌ 错误: {str(e)}[/error]")
            console.print()

    async def run(self):
        """运行 CLI"""
        await self.initialize()

        print_banner()
        print_session_info(self.bot_flow, self.message_count, self.session_start)

        while self.running:
            try:
                user_input = Prompt.ask("[green]>[/green] ")

                if not user_input.strip():
                    continue

                if user_input.startswith("/"):
                    await self.handle_command(user_input)
                else:
                    await self.chat(user_input)

            except KeyboardInterrupt:
                console.print("\n[yellow]使用 /exit 退出[/yellow]")
                continue
            except EOFError:
                break

        console.print("\n[cyan]👋 再见！[/cyan]")

    async def handle_command(self, command: str):
        """处理命令"""
        cmd = command.strip().lower()

        if cmd in ["/exit", "/quit", "exit", "quit", "q"]:
            self.running = False

        elif cmd == "/help":
            print_help()

        elif cmd == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            print_banner()

        elif cmd == "/history":
            console.print(f"\n[cyan]消息历史: {self.message_count} 条[/cyan]\n")

        elif cmd == "/stats":
            print_stats(self.message_count, self.session_start)

        elif cmd == "/models":
            print_models(self.bot_flow)

        elif cmd == "/tools":
            print_tools(self.bot_flow)

        elif cmd.startswith("/model"):
            parts = command.split()
            if len(parts) > 1:
                model_name = parts[1]
                if model_name in self.bot_flow.config.model_configs:
                    self.current_model = model_name
                    console.print(f"[success]✅ 已切换到模型: {model_name}[/success]\n")
                else:
                    console.print(f"[error]❌ 未知的模型: {model_name}[/error]")
                    console.print("[cyan]使用 /models 查看可用模型[/cyan]\n")
            else:
                console.print(f"[cyan]当前模型: {self.current_model}[/cyan]")
                console.print("[cyan]使用 /model <名称> 切换模型[/cyan]\n")

        else:
            console.print(f"[warning]⚠️ 未知命令: {command}[/warning]")
            console.print("[cyan]输入 /help 获取帮助[/cyan]\n")


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="OpenBot CLI - 交互式控制台")
    parser.add_argument(
        "--workspace",
        "-w",
        type=str,
        default=None,
        help="工作区目录",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default="doubao_auto",
        help="默认模型",
    )

    args = parser.parse_args()

    cli = OpenBotCLI(homespace=args.workspace)
    cli.current_model = args.model
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
