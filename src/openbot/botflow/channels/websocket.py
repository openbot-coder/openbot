"""WebSocket 通道实现"""

import asyncio
import logging
from typing import Set

from fastapi import WebSocket

from .base import ChatChannel
from ..database import ChatMessage


logger = logging.getLogger(__name__)


class WebSocketChannel(ChatChannel):
    """WebSocket 通道"""

    def __init__(self, path: str = "/ws/chat"):
        super().__init__(name="websocket")
        self.path = path
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """启动 WebSocket 通道"""
        self._running = True
        logger.info(f"WebSocket channel started at {self.path}")

    async def stop(self) -> None:
        """停止 WebSocket 通道"""
        self._running = False
        async with self._lock:
            for ws in list(self._connections):
                try:
                    await ws.close()
                except Exception:
                    pass
            self._connections.clear()
        logger.info("WebSocket channel stopped")

    async def send(self, message: ChatMessage) -> None:
        """发送消息到所有连接"""
        async with self._lock:
            disconnected = set()
            for ws in self._connections:
                try:
                    await ws.send_text(message.content)
                except Exception:
                    disconnected.add(ws)

            for ws in disconnected:
                self._connections.discard(ws)

    async def handle_connection(self, websocket: WebSocket) -> None:
        """处理 WebSocket 连接"""
        await websocket.accept()

        async with self._lock:
            self._connections.add(websocket)

        try:
            while self._running:
                try:
                    data = await websocket.receive_text()
                    msg = ChatMessage(
                        channel_id="websocket",
                        content=data,
                        role="user"
                    )
                    await self.on_receive(msg)
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                    break
        finally:
            async with self._lock:
                self._connections.discard(websocket)
            try:
                await websocket.close()
            except Exception:
                pass
