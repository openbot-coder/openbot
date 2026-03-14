"""
OpenBot CLI - 交互式控制台界面
"""

import asyncio
import logging
import os
import sys
import locale
from datetime import datetime
from pathlib import Path

# 设置标准输入输出编码为UTF-8
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 设置环境变量强制使用UTF-8编码
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['LC_ALL'] = 'en_US.UTF-8'
os.environ['LANG'] = 'en_US.UTF-8'

logging.basicConfig(level=logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("agentscope").setLevel(logging.ERROR)
logging.getLogger("agentscope_runtime").setLevel(logging.ERROR)
logging.getLogger("root").setLevel(logging.CRITICAL)

from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style as PromptStyle
from rich.theme import Theme
from rich.markdown import Markdown

custom_theme = Theme(
    {
        "info": "sky_blue2",
        "warning": "bold dark_orange",
        "error": "bold bright_red on grey15",
        "success": "bold spring_green3",
        "tool": "bold #FFFFE0",     # 工具调用 - 浅黄色 (light yellow)
        "tool_func": "white",        # 调用函数 - 白色
        "tool_arg": "#808080",       # 调用参数 - 灰色
        "tool_result": "bold #FFFFE0",  # 工具调用结果 - 浅黄色
        "tool_result_content": "#808080",  # 具体结果 - 灰色
        "user": "bold #00FF7F",
        "assistant": "bold #00BFFF",  # 机器人回复 - 鲜蓝色 (DeepSkyBlue)
        "muted": "dim grey70",
        "highlight": "bold bright_yellow",
    }
)

console = Console(theme=custom_theme)
from agentscope.pipeline import stream_printing_messages
from openbot.gateway.botflow import BotFlow
from openbot.agents.tool_manger import ToolKitManager
from openbot.config import BotFlowConfig


def print_banner():
    """Print welcome banner"""
    console.print()
    console.print(
        "╔══════════════════════════════════════════════════════════╗",
        style="bold cyan",
    )
    console.print(
        "║         🤖 OpenBot CLI - Multi-Agent Interactive Session  ║",
        style="bold cyan",
    )
    console.print(
        "╚══════════════════════════════════════════════════════════╝",
        style="bold cyan",
    )
    console.print()


def print_help():
    """Print help information"""
    console.print("\n[bold yellow]Available Commands:[/bold yellow]")
    console.print("  [green]/help[/green]      - Show help information")
    console.print("  [green]/clear[/green]    - Clear session history")
    console.print("  [green]/history[/green] - Show current session message count")
    console.print("  [green]/stats[/green]    - Show session statistics")
    console.print("  [green]/models[/green]   - Show available models")
    console.print("  [green]/tools[/green]    - Show available tools")
    console.print("  [green]/model[/green]    - Switch current model")
    console.print("  [green]/exit[/green]     - Exit the program")
    console.print()


def print_session_info(bot_flow: BotFlow, message_count: int, session_start: datetime):
    """Print session information"""
    available_models = list(bot_flow.config.model_configs.keys())

    console.print(
        "┌──────────────────────────────────────────────────────────┐", style="dim"
    )
    console.print(
        "│                         Session Info                      │", style="dim"
    )
    console.print(
        "├──────────────────────────────────────────────────────────┤", style="dim"
    )
    console.print(f"│  Available Models: {', '.join(available_models):<30} │")
    console.print(f"│  Message History: {message_count} messages{' ' * 25}│")
    console.print(f"│  Session Duration: {datetime.now() - session_start}{' ' * 19}│")
    console.print(
        "└──────────────────────────────────────────────────────────┘", style="dim"
    )
    console.print()
    console.print("[dim]Type /help for help, /exit to quit[/dim]")
    console.print()


def print_stats(message_count: int, session_start: datetime):
    """Print session statistics"""
    duration = datetime.now() - session_start
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    console.print("\n[bold cyan]Session Statistics:[/bold cyan]")
    console.print(f"  Session Duration: {hours:02d}:{minutes:02d}:{seconds:02d}")
    console.print(f"  Total Messages: {message_count}\n")


def print_models(bot_flow: BotFlow):
    """Print available models"""
    console.print("\n[bold cyan]Available Models:[/bold cyan]")

    for i, (name, config) in enumerate(bot_flow.config.model_configs.items(), 1):
        provider = getattr(config, "provider", "unknown")
        model_name = getattr(config, "model", name)
        console.print(f"  {i}. [white]{name}[/white]")
        console.print(f"      Provider: {provider}, Model: {model_name}")
    console.print()


def print_tools(bot_flow: BotFlow):
    """Print available tools"""
    tools = bot_flow.toolkit_manager.list_tools()

    console.print(f"\n[bold cyan]Available Tools ({len(tools)}):[/bold cyan]")

    for i, tool in enumerate(tools[:20], 1):
        console.print(f"  {i}. [white]{tool}[/white]")

    if len(tools) > 20:
        console.print(f"  [dim]... and {len(tools) - 20} more tools[/dim]")
    console.print()


class OpenBotCLI:
    def __init__(self, homespace: str = None, workspace: str = None):
        # homespace: bot 的配置、记忆、技能根目录
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

        # workspace: 用户工作目录，默认为当前目录
        if workspace:
            self.workspace = workspace
        else:
            self.workspace = os.getcwd()

        os.environ["OPENBOT_HOMESPACE"] = self.homespace
        os.environ["OPENBOT_WORKSPACE"] = self.workspace

        self.bot_flow = None
        self.session_start = datetime.now()
        self.message_count = 0
        self.current_model = "doubao_auto"
        self.running = True
        # 初始化 prompt_toolkit 会话 - 鲜绿色 (#00FF7F)
        self.prompt_session = PromptSession(
            style=PromptStyle.from_dict({
                'prompt': 'bold #00FF7F',
                'input': '#ffffff',
            })
        )

    async def initialize(self):
        """Initialize BotFlow"""
        console.print("[cyan]Initializing OpenBot...[/cyan]")
        console.print(f"[dim]HomeSpace (Bot config): {self.homespace}[/dim]")
        console.print(f"[dim]Workspace (User work dir): {self.workspace}[/dim]")

        # 初始化过程中静默日志
        logging.disable(logging.CRITICAL)
        
        self.bot_flow = BotFlow(homespace=self.homespace)
        await self.bot_flow.initialize()

        available_models = list(self.bot_flow.config.model_configs.keys())
        # 校验用户指定的模型是否存在
        if available_models:
            if self.current_model not in available_models:
                console.print(f"[warning]⚠️ Specified model '{self.current_model}' not found, using default: {available_models[0]}[/warning]")
                self.current_model = available_models[0]

        # 恢复日志级别
        logging.disable(logging.NOTSET)
        
        console.print("[success]✅ OpenBot initialized successfully[/success]")
        console.print(f"[dim]Available models: {', '.join(available_models)}[/dim]")
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
        """Process chat message"""
        if not message.strip():
            return

        # 用于标记是否被用户中断
        interrupted = False

        try:
            agent = self.bot_flow.create_agent(
                name="cli_assistant",
                system_prompt="You are a helpful AI assistant",
                model_id=self.current_model,
            )
            agent.set_console_output_enabled(False)

            from agentscope.message import Msg

            user_msg = Msg(name="user", content=message, role="user")

            with console.status("[dim]🤔 Processing...[/dim]"):
                reply_content = []
                try:
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
                                # 获取工具参数
                                tool_args = content_block.get("input", {})
                                args_str = ", ".join([f"{k}={repr(v)}" for k, v in tool_args.items()]) if tool_args else ""
                                console.print(
                                    f"[tool]🔧 Tool Call: [tool_func]{tool_name}[/tool_func]([tool_arg]{args_str}[/tool_arg])[/tool]"
                                )
                            elif block_type == "tool_result":
                                output = content_block.get("output", [])
                                if output:
                                    for o in output:
                                        if isinstance(o, dict) and o.get("type") == "text":
                                            result_text = o.get('text', '')
                                            # 计算行数
                                            lines = result_text.split('\n')
                                            line_count = len(lines)
                                            
                                            if line_count > 10:
                                                # 超过10行，截断并显示提示
                                                truncated_lines = lines[:10]
                                                truncated_text = '\n'.join(truncated_lines)
                                                console.print(
                                                    f"[tool_result]📤 Result: [tool_result_content]{truncated_text}[/tool_result_content]\n"
                                                    f"[tool_result]   [dim](... {line_count - 10} more lines, output truncated ...)[/tool_result]"
                                                )
                                            else:
                                                console.print(
                                                    f"[tool_result]📤 Result: [tool_result_content]{result_text}[/tool_result_content][/tool_result]"
                                                )
                            elif msg.role == "assistant" and block_type == "text":
                                text_content = content_block.get("text", "")
                                if text_content:
                                    reply_content.append(text_content)
                except KeyboardInterrupt:
                    # 用户按 Ctrl+C 中断思考
                    interrupted = True
                    console.print()
                    console.print("[warning]⚠️ 当前思考已被中断，输入已取消[/warning]")
                    console.print()
                    return

            # 如果被中断，不显示回复内容
            if interrupted:
                return

            # 获取 bot 名称
            bot_name = getattr(agent, "name", "botname").upper() if agent else "botname"
            
            if reply_content:
                for content_block in reply_content:
                    markdown_content = Markdown(content_block)
                    console.print(f"[assistant]{bot_name} >[/assistant]", end=" ")
                    console.print(markdown_content)

            console.print()
            self.message_count += 2

        except KeyboardInterrupt:
            # 捕获外层的 KeyboardInterrupt
            console.print()
            console.print("[warning]⚠️ 当前思考已被中断，输入已取消[/warning]")
            console.print()
        except Exception as e:
            console.print(f"[error]❌ Error: {str(e)}[/error]")
            console.print()

    async def run(self):
        """运行 CLI"""
        await self.initialize()

        print_banner()
        print_session_info(self.bot_flow, self.message_count, self.session_start)

        while self.running:
            try:
                user_input = await self.prompt_session.prompt_async("YOU > ")
                # prompt_toolkit 自动处理编码，无需额外解码

                if not user_input.strip():
                    continue

                if user_input.startswith("/"):
                    await self.handle_command(user_input)
                else:
                    await self.chat(user_input)

            except UnicodeDecodeError:
                console.print("[warning]⚠️ Invalid characters in input, please try again[/warning]")
                continue
            except KeyboardInterrupt:
                console.print("\n[warning]Use /exit to quit[/warning]")
                continue
            except EOFError:
                console.print("\n[info]Received exit signal, quitting...[/info]")
                break
            except Exception as e:
                console.print(f"[error]❌ Error: {str(e)}[/error]")
                console.print()

        console.print("\n[info]👋 Goodbye![/info]")

    async def handle_command(self, command: str):
        """Handle commands"""
        cmd = command.strip().lower()

        if cmd in ["/exit", "/quit", "exit", "quit", "q"]:
            self.running = False

        elif cmd == "/help":
            print_help()

        elif cmd == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            print_banner()

        elif cmd == "/history":
            console.print(f"\n[cyan]Message History: {self.message_count} messages[/cyan]\n")

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
                    console.print(f"[success]✅ Switched to model: {model_name}[/success]\n")
                else:
                    console.print(f"[error]❌ Unknown model: {model_name}[/error]")
                    console.print("[info]Use /models to see available models[/info]\n")
            else:
                console.print(f"[info]Current model: {self.current_model}[/info]")
                console.print("[info]Use /model <name> to switch model[/info]\n")

        else:
            console.print(f"[warning]⚠️ Unknown command: {command}[/warning]")
            console.print("[info]Type /help for help[/info]\n")


async def main():
    """Main function"""
    import argparse

    # 启动前静默所有日志
    logging.disable(logging.CRITICAL)
    
    parser = argparse.ArgumentParser(description="OpenBot CLI - Interactive Console")
    parser.add_argument(
        "--homespace",
        type=str,
        default=None,
        help="Bot's config, memory, skills root directory (default: ~/.openbot)",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        type=str,
        default=None,
        help="User's working directory (default: current directory)",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default="doubao_auto",
        help="Default model",
    )

    args = parser.parse_args()

    print("Starting OpenBot CLI...")
    print("Initializing OpenBot...")
    
    # homespace: bot 配置目录，默认 ~/.openbot
    homespace = args.homespace or os.path.expanduser("~/.openbot")
    # workspace: 用户工作目录，默认当前目录
    workspace = args.workspace or os.getcwd()
    
    print(f"HomeSpace (Bot config): {homespace}")
    print(f"Workspace (User work dir): {workspace}")

    cli = OpenBotCLI(homespace=homespace, workspace=workspace)
    cli.current_model = args.model
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
