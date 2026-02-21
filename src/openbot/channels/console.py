import asyncio
from typing import AsyncIterator
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.completion import WordCompleter, Completer, Completion
from prompt_toolkit.styles import Style
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from langchain_core.messages import AnyMessage, HumanMessage
from openbot.botflow.core import Task
from .base import ChatChannel, ChannelBuilder, ChatMessage, ContentType
import os


class CommandCompleter(Completer):
    """命令补全器"""
    
    def __init__(self):
        self.commands = {
            "exit": "退出控制台",
            "quit": "退出控制台",
            "q": "退出控制台",
            "help": "显示帮助信息",
            "clear": "清除控制台",
            "history": "显示命令历史",
            "status": "显示系统状态",
            "tasks": "显示当前任务",
            "channels": "显示可用通道",
            "version": "显示版本信息",
        }
    
    def get_completions(self, document, complete_event):
        """获取补全项"""
        text = document.text.lower()
        for command, description in self.commands.items():
            if command.startswith(text):
                yield Completion(
                    command,
                    start_position=-len(text),
                    display=command,
                    display_meta=description
                )


class ConsoleChannel(ChatChannel):
    def __init__(self, prompt: str = "openbot> "):
        self.prompt = prompt
        self.running = False
        self.history_file = os.path.expanduser("~/.openbot_history")
        self.session = PromptSession(
            history=FileHistory(self.history_file),
            auto_suggest=AutoSuggestFromHistory()
        )
        self.console = Console()
        self.completer = CommandCompleter()
        self.style = Style.from_dict(
            {
                "prompt": "#00ff00 bold",
                "input": "#ffffff",
            }
        )
        self.bot_thinging_status = self.console.status("Thinking...", spinner="dots")
        self._input_blocking = asyncio.Event()
        self.botflow = None
        self.command_aliases = {
            "quit": "exit",
            "q": "exit",
        }

    @property
    def channel_id(self) -> str:
        """获取 Channel ID"""
        return "console"

    async def start(self) -> None:
        self.running = True
        self.console.print(
            Panel(
                "OpenBot Console Channel started.\nType 'exit' to quit.\nType 'help' for available commands.",
                title="[bold blue]OpenBot[/bold blue]",
                border_style="blue",
            )
        )
        asyncio.create_task(self.run())

    async def send(self, message: ChatMessage) -> None:
        """发送完整消息"""
        self.console.print()
        try:
            # 尝试渲染为 Markdown
            if message.metadata.get("step") == "model" and message.content != "":
                markdown = Markdown(message.content)
                self.console.print(markdown)
                self.bot_thinging_status.stop()
                self._input_blocking.set()
            elif not message.metadata.get("step", None):
                self.console.print(
                    f"[dim cyan]{message.metadata.get('tool_name')}[/dim]: {message.content}..."
                )
        except Exception:
            # 如果渲染失败，直接打印
            self.console.print(Panel(message.content, border_style="blue"))
        self.console.print()

    async def send_stream(self, stream: AsyncIterator[AnyMessage]) -> None:
        content = ""
        self.console.print()
        async for chunk in stream:
            if hasattr(chunk, "content") and chunk.content:
                content += chunk.content
                self.console.print(chunk.content, end="", flush=True)
        self.console.print()
        self.console.print()

    async def run(self) -> None:
        """运行控制台通道"""
        while self.running:
            try:
                with patch_stdout(raw=True):
                    user_input = await self.session.prompt_async(
                        self.prompt,
                        completer=self.completer,
                        style=self.style,
                        enable_history_search=True,
                        include_default_pygments_style=False,
                        bottom_toolbar="Press Tab for completions, Ctrl+R for history search",
                    )

                    # 处理命令别名
                    command = user_input.lower().strip()
                    if command in self.command_aliases:
                        command = self.command_aliases[command]

                    if command in ["exit", "quit", "q"]:
                        self.running = False
                        break

                    elif command == "help":
                        self._show_help()
                        continue

                    elif command == "clear":
                        self.console.clear()
                        continue

                    elif command == "history":
                        self._show_history()
                        continue

                    elif command == "status":
                        await self._show_status()
                        continue

                    elif command == "tasks":
                        await self._show_tasks()
                        continue

                    elif command == "channels":
                        await self._show_channels()
                        continue

                    elif command == "version":
                        self._show_version()
                        continue

                    elif command == "":
                        continue

                    elif user_input.startswith("/"):
                        await self._handle_command(user_input[1:].lower())
                    else:
                        self.bot_thinging_status.start()
                        # 创建 HumanMessage
                        human_message = HumanMessage(
                            content=user_input,
                            role="user",
                            metadata={"channel": "console"},
                        )
                        # 转换为 ChatMessage
                        chat_message = ChatMessage(
                            content=user_input,
                            role="user",
                            metadata={"channel": "console", "original_message": human_message},
                            channel_id=self.channel_id
                        )
                        # 放入消息队列
                        try:
                            await self.message_queue.put(chat_message)
                        except Exception as e:
                            self.console.print(f"[red]Error putting message to queue: {e}[/red]")
                        # 等待响应
                        await self._input_blocking.wait()
                        self._input_blocking.clear()
            except EOFError:
                self.running = False
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use 'exit' to quit properly.[/yellow]")

        await self.stop()

    def _show_help(self) -> None:
        """显示帮助信息"""
        table = Table(title="[bold blue]Help[/bold blue]", border_style="blue")
        table.add_column("Command", style="green", width=15)
        table.add_column("Description", style="white")
        
        table.add_row("exit, quit, q", "Exit the console")
        table.add_row("help", "Show this help message")
        table.add_row("clear", "Clear the console")
        table.add_row("history", "Show command history")
        table.add_row("status", "Show system status")
        table.add_row("tasks", "Show current tasks")
        table.add_row("channels", "Show available channels")
        table.add_row("version", "Show version information")
        
        self.console.print(table)
    
    async def _show_status(self) -> None:
        """显示系统状态"""
        table = Table(title="[bold blue]System Status[/bold blue]", border_style="blue")
        table.add_column("Component", style="cyan", width=20)
        table.add_column("Status", style="white")
        
        # 检查 BotFlow 状态
        if self.botflow:
            table.add_row("BotFlow", "Running")
            
            # 检查通道状态
            channel_manager = self.botflow.channel_manager()
            if channel_manager:
                table.add_row("Channel Manager", "Initialized")
        else:
            table.add_row("BotFlow", "Not initialized")
        
        table.add_row("Console Channel", "Running" if self.running else "Stopped")
        table.add_row("History File", self.history_file)
        
        self.console.print(table)
    
    async def _show_tasks(self) -> None:
        """显示当前任务"""
        if self.botflow and hasattr(self.botflow, "task_manager"):
            # 这里可以添加任务管理器的状态信息
            self.console.print(Panel(
                "Task Manager initialized\n" +
                "(Task list functionality not implemented yet)",
                title="[bold blue]Current Tasks[/bold blue]",
                border_style="blue"
            ))
        else:
            self.console.print(Panel(
                "Task Manager not initialized",
                title="[bold blue]Current Tasks[/bold blue]",
                border_style="blue"
            ))
    
    async def _show_channels(self) -> None:
        """显示可用通道"""
        if self.botflow:
            channel_manager = self.botflow.channel_manager()
            if channel_manager:
                table = Table(title="[bold blue]Available Channels[/bold blue]", border_style="blue")
                table.add_column("Channel ID", style="cyan", width=25)
                table.add_column("Status", style="white")
                
                # 这里可以添加通道列表
                table.add_row(self.channel_id, "Running")
                
                self.console.print(table)
            else:
                self.console.print(Panel(
                    "Channel Manager not initialized",
                    title="[bold blue]Available Channels[/bold blue]",
                    border_style="blue"
                ))
        else:
            self.console.print(Panel(
                "BotFlow not initialized",
                title="[bold blue]Available Channels[/bold blue]",
                border_style="blue"
            ))
    
    def _show_version(self) -> None:
        """显示版本信息"""
        try:
            import importlib.metadata
            version = importlib.metadata.version("openbot")
        except Exception:
            version = "0.1.0"
        
        self.console.print(Panel(
            f"OpenBot version: [bold green]{version}[/bold green]\n" +
            "Multi-channel AI Bot with self-evolution capabilities",
            title="[bold blue]Version Information[/bold blue]",
            border_style="blue"
        ))

    def _show_history(self) -> None:
        """显示命令历史"""
        history = list(self.session.history)
        if not history:
            self.console.print("[yellow]No history available.[/yellow]")
            return

        self.console.print(
            Panel("[bold cyan]Command History:[/bold cyan]", border_style="cyan")
        )
        for i, entry in enumerate(reversed(history), 1):
            self.console.print(f"[green]{i}.[/green] {entry}")

    async def _handle_command(self, command: str) -> None:
        """处理命令"""
        if command == "exit":
            self.running = False
        elif command == "help":
            self._show_help()
        elif command == "clear":
            self.console.clear()
        elif command == "history":
            self._show_history()
        else:
            self.console.print(f"[yellow]Unknown command: {command}[/yellow]")

    async def on_receive(self, message: ChatMessage) -> None:
        """处理接收消息"""
        # 控制台通道不需要特殊处理接收消息
        pass

    async def stop(self) -> None:
        self.running = False
        self.console.print("[bold red]OpenBot Console Channel stopped.[/bold red]")
        self.bot_thinging_status.stop()


ChannelBuilder.register("console", ConsoleChannel)
