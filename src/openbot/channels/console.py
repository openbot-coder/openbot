import asyncio
from typing import AsyncIterator
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from langchain_core.messages import AnyMessage, HumanMessage
from openbot.botflow.core import Task
from .base import ChatChannel, ChannelBuilder, ChatMessage, ContentType


class ConsoleChannel(ChatChannel):
    def __init__(self, prompt: str = "openbot> "):
        self.prompt = prompt
        self.running = False
        self.session = PromptSession()
        self.console = Console()
        self.completer = WordCompleter(
            ["exit", "help", "clear", "history"], ignore_case=True
        )
        self.style = Style.from_dict(
            {
                "prompt": "#00ff00 bold",
                "input": "#ffffff",
            }
        )
        self.bot_thinging_status = self.console.status("Thinking...", spinner="dots")
        self._input_blocking = asyncio.Event()
        self.botflow = None

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
                    )

                    if user_input.lower() in ["exit", "quit", "q"]:
                        self.running = False
                        break

                    elif user_input.lower() == "help":
                        self._show_help()
                        continue

                    elif user_input.lower() == "clear":
                        self.console.clear()
                        continue

                    elif user_input.lower() == "history":
                        self._show_history()
                        continue

                    elif user_input.lower() == "":
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

        await self.stop()

    def _show_help(self) -> None:
        """显示帮助信息"""
        self.console.print(
            Panel(
                "[bold cyan]Available commands:[/bold cyan]\n\n"
                + "[green]exit[/green] - Exit the console\n"
                + "[green]help[/green] - Show this help message\n"
                + "[green]clear[/green] - Clear the console\n"
                + "[green]history[/green] - Show command history",
                title="[bold blue]Help[/bold blue]",
                border_style="blue",
            )
        )

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
