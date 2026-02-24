"""BotFlow 核心应用 - FastAPI"""

import asyncio
import logging
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, Callable, Any

from fastapi import FastAPI, WebSocket, Request

from openbot.config import OpenbotConfig
from openbot.agents.core import OpenBotExecutor
from .database import DatabaseManager, ChatMessage, ContentType
from .task import Task, TaskManager


logger = logging.getLogger(__name__)


class BotFlow:
    """BotFlow 核心类"""

    def __init__(
        self,
        config: OpenbotConfig,
    ):
        self._config = config
        self._app = FastAPI(title="BotFlow", version="0.3.0")

        self._agent_executor = OpenBotExecutor(config)
        self.task_manager = TaskManager()
        self.message_queue = asyncio.Queue()

        self.channels: dict[str, Any] = {}
        self._message_handler: Optional[Callable] = None

        self._register_routes()
        self._app.add_event_handler("startup", self._on_startup)
        self._app.add_event_handler("shutdown", self._on_shutdown)

    def _register_routes(self):
        """注册路由"""

        @self._app.get("/")
        async def root():
            return {"name": "BotFlow", "version": "0.3.0"}

        @self._app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "task_count": len(self.task_manager.list_tasks()),
            }

    async def _on_startup(self):
        """启动事件"""
        await self._agent_executor.init_agent()
        await asyncio.gather(*[channel.start() for channel in self.channels.values()])
        logger.info("BotFlow started")

    async def _on_shutdown(self):
        """关闭事件"""
        for channel in self.channels.values():
            if hasattr(channel, "stop"):
                await channel.stop()
        self.task_manager.close()
        logger.info("BotFlow shutdown")

    def set_message_handler(self, handler: Callable):
        """设置消息处理器"""
        self._message_handler = handler

    async def handle_message(self, message: ChatMessage) -> None:
        """处理消息"""
        task = Task(
            name=f"process_msg_{message.channel_id}",
            func=self._process_message,
            args=(message,),
        )
        self.task_manager.submit(task)

    async def _process_message(self, message: ChatMessage) -> None:
        """处理消息事件"""
        start_time = time.time()
        response_content = ""

        if self._agent_executor and self._message_handler:
            try:
                response_content = await self._message_handler(message)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                response_content = "Sorry, I encountered an error."
        else:
            response_content = f"Received: {message.content}"

        process_time = int((time.time() - start_time) * 1000)

        bot_message = ChatMessage(
            channel_id=message.channel_id,
            content=response_content,
            content_type=ContentType.TEXT,
            role="bot",
            process_time_ms=process_time,
        )

        channel = self.channels.get(message.channel_id)
        if channel and hasattr(channel, "send"):
            await channel.send(bot_message)

        logger.info(f"Processed message in {process_time}ms")

    def register_channel(self, name: str, channel: Any):
        """注册通道"""
        self.channels[name] = channel
        if hasattr(channel, "set_message_handler"):
            channel.set_message_handler(self.handle_message)
        logger.info(f"Registered channel: {name}")

    @property
    def app(self) -> FastAPI:
        """获取 FastAPI 应用实例"""
        return self._app
