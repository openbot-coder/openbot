"""BotFlow 核心应用 - FastAPI"""
import logging
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, Callable, Any

from fastapi import FastAPI, WebSocket, Request

from .config import BotFlowConfig, ChannelConfig
from .database import DatabaseManager, ChatMessage
from .task import Task, TaskManager


logger = logging.getLogger(__name__)


class BotFlow(FastAPI):
    """BotFlow 核心类 - 继承 FastAPI"""
    
    def __init__(
        self,
        config: BotFlowConfig,
        agent: Optional[Any] = None,
    ):
        super().__init__(title="BotFlow", version="0.3.0")
        
        self.config = config
        self.agent = agent
        
        # 初始化组件
        self.db = DatabaseManager(config.db_path)
        self.task_manager = TaskManager()
        
        # 通道
        self.channels: dict[str, Any] = {}
        
        # 消息处理器
        self._message_handler: Optional[Callable] = None
        
        # 注册路由
        self._register_routes()
        
        # 生命周期事件
        self.add_event_handler("startup", self._on_startup)
        self.add_event_handler("shutdown", self._on_shutdown)
    
    def _register_routes(self):
        """注册路由"""
        @self.get("/")
        async def root():
            return {"name": "BotFlow", "version": "0.3.0"}
        
        @self.get("/health")
        async def health():
            return {
                "status": "healthy",
                "task_count": len(self.task_manager.list_tasks())
            }
    
    async def _on_startup(self):
        """启动事件"""
        await self.db.initialize()
        await self.task_manager.start()
        logger.info("BotFlow started")
    
    async def _on_shutdown(self):
        """关闭事件"""
        for channel in self.channels.values():
            if hasattr(channel, 'stop'):
                await channel.stop()
        self.task_manager.close()
        logger.info("BotFlow shutdown")
    
    def set_message_handler(self, handler: Callable):
        """设置消息处理器"""
        self._message_handler = handler
    
    async def handle_message(self, content: str, channel_id: str, reply_to: str = ""):
        """处理消息"""
        # 保存用户消息
        user_message = ChatMessage(
            content=content,
            role="user",
            channel_id=channel_id
        )
        await self.db.save_message(user_message)
        
        # 创建处理任务
        task = Task(
            name=f"process_msg_{channel_id}",
            func=self._process_message,
            args=(content, channel_id, reply_to)
        )
        self.task_manager.submit(task)
    
    async def _process_message(self, content: str, channel_id: str, reply_to: str = ""):
        """处理消息事件"""
        start_time = time.time()
        
        response_content = ""
        
        # 如果有 agent，使用 agent 处理
        if self.agent and self._message_handler:
            try:
                response_content = await self._message_handler(content, channel_id)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                response_content = "Sorry, I encountered an error."
        else:
            # 默认回复
            response_content = f"Received: {content}"
        
        process_time = int((time.time() - start_time) * 1000)
        
        # 保存响应
        bot_message = ChatMessage(
            content=response_content,
            role="bot",
            channel_id=channel_id,
            process_time_ms=process_time
        )
        await self.db.save_message(bot_message)
        
        logger.info(f"Processed message in {process_time}ms")
        return response_content
    
    def register_channel(self, name: str, channel: Any):
        """注册通道"""
        self.channels[name] = channel
        if hasattr(channel, 'set_message_handler'):
            channel.set_message_handler(self.handle_message)
        logger.info(f"Registered channel: {name}")
