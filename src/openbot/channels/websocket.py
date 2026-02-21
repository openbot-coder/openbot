import asyncio
import json
from typing import AsyncIterator
from websockets.server import serve
from websockets.exceptions import ConnectionClosedError
from rich.console import Console
from .base import ChatChannel, ChatMessage, ContentType


class WebSocketChannel(ChatChannel):
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.running = False
        self.console = Console()
        self.server = None
        self.connections = set()
        self.botflow = None

    @property
    def channel_id(self) -> str:
        """获取 Channel ID"""
        return f"websocket-{self.host}:{self.port}"

    async def start(self) -> None:
        """启动 WebSocket 服务器"""
        self.running = True
        self.console.print(
            f"[bold green]WebSocketChannel started on ws://{self.host}:{self.port}[/bold green]"
        )
        
        # 启动 WebSocket 服务器
        self.server = await serve(
            self._handle_connection,
            self.host,
            self.port
        )

    async def _handle_connection(self, websocket):
        """处理 WebSocket 连接"""
        # 添加到连接集合
        self.connections.add(websocket)
        self.console.print(
            f"[bold blue]New connection established: {websocket.remote_address}[/bold blue]"
        )
        
        try:
            # 发送欢迎消息
            welcome_message = {
                "type": "welcome",
                "message": "Welcome to OpenBot WebSocket Channel!"
            }
            await websocket.send(json.dumps(welcome_message))
            
            # 处理消息
            async for message in websocket:
                await self._process_message(websocket, message)
        except ConnectionClosedError:
            self.console.print(
                f"[bold yellow]Connection closed: {websocket.remote_address}[/bold yellow]"
            )
        finally:
            # 从连接集合中移除
            self.connections.remove(websocket)

    async def _process_message(self, websocket, message):
        """处理接收到的消息"""
        try:
            # 解析消息
            data = json.loads(message)
            content = data.get("content", "")
            
            if content:
                # 创建 ChatMessage
                chat_message = ChatMessage(
                    content=content,
                    role="user",
                    metadata={"channel": "websocket", "remote_address": str(websocket.remote_address)},
                    channel_id=self.channel_id
                )
                
                # 放入消息队列
                try:
                    await self.message_queue.put(chat_message)
                except Exception as e:
                    self.console.print(f"[red]Error putting message to queue: {e}[/red]")
        except json.JSONDecodeError:
            self.console.print("[red]Error decoding JSON message[/red]")
        except Exception as e:
            self.console.print(f"[red]Error processing message: {e}[/red]")

    async def send(self, message: ChatMessage) -> None:
        """发送完整消息"""
        try:
            # 构建消息数据
            message_data = {
                "type": "message",
                "content": message.content,
                "role": message.role,
                "channel_id": message.channel_id,
                "metadata": message.metadata
            }
            
            # 发送消息到所有连接
            disconnected = set()
            for connection in self.connections:
                try:
                    await connection.send(json.dumps(message_data))
                except ConnectionClosedError:
                    disconnected.add(connection)
            
            # 清理断开的连接
            for connection in disconnected:
                if connection in self.connections:
                    self.connections.remove(connection)
        except Exception as e:
            self.console.print(f"[red]Error sending message: {e}[/red]")

    async def send_stream(self, stream: AsyncIterator) -> None:
        """发送流式消息"""
        # WebSocket 通道暂不支持流式消息
        content = ""
        async for chunk in stream:
            if hasattr(chunk, "content") and chunk.content:
                content += chunk.content
        
        # 发送完整消息
        message = ChatMessage(
            content=content,
            role="bot",
            channel_id=self.channel_id
        )
        await self.send(message)

    async def on_receive(self, message: ChatMessage) -> None:
        """处理接收消息"""
        # WebSocket 通道不需要特殊处理接收消息
        pass

    async def stop(self) -> None:
        """停止 WebSocket 服务器"""
        self.running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.console.print("[bold red]WebSocketChannel stopped[/bold red]")


# 注册 WebSocketChannel
from .base import ChannelBuilder
ChannelBuilder.register("websocket", WebSocketChannel)
