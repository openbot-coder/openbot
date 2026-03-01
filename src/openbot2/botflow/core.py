"""BotFlow 核心应用 - FastAPI"""

import asyncio
import logging
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, Callable, Any

from fastapi import FastAPI, Request

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

        self._agent_executor = OpenBotExecutor(
            config.model_configs, config.agent_config
        )
        self.task_manager = TaskManager()
        self.message_queue = asyncio.Queue()

        self.channels: dict[str, Any] = {}
        self._message_handler: Optional[Callable] = None

        # 初始化通道构建器
        from .channels import ChannelBuilder, WeChatBotChatChannel

        self.channel_builder = ChannelBuilder()
        self.channel_builder.register("wechat", WeChatBotChatChannel)

        # 根据配置创建和注册通道
        for channel_config in config.channels:
            if channel_config.enabled:
                try:
                    # 处理不同通道的配置格式
                    if channel_config.name == "wechat":
                        # wechat通道的配置格式
                        params = channel_config.params.copy()
                        # WeChatBotChatChannel需要s_token和s_encoding_aes_key参数
                        # 确保这些参数存在
                        if "s_token" not in params:
                            params["s_token"] = ""
                        if "s_encoding_aes_key" not in params:
                            params["s_encoding_aes_key"] = ""
                        channel = self.channel_builder.build(
                            channel_config.name, params
                        )
                        # 直接在BotFlow中添加微信通道的路由
                        from fastapi import APIRouter

                        wechat_router = APIRouter()

                        # 确保path以/开头
                        wechat_path = channel_config.path
                        if not wechat_path.startswith("/"):
                            wechat_path = "/" + wechat_path

                        @wechat_router.get(wechat_path)
                        async def wechat_verify(request: Request):
                            print(f"WeChat verify request received at {wechat_path}")
                            # 从查询参数中获取参数
                            msg_signature = request.query_params.get("msg_signature")
                            timestamp = request.query_params.get("timestamp")
                            nonce = request.query_params.get("nonce")
                            echostr = request.query_params.get("echostr")
                            print(
                                f"Parameters: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}, echostr={echostr}"
                            )
                            return await channel._verify_url(
                                request, msg_signature, timestamp, nonce, echostr
                            )

                        @wechat_router.post(wechat_path)
                        async def wechat_message(request: Request):
                            print(f"WeChat message request received at {wechat_path}")
                            # 从查询参数中获取参数
                            msg_signature = request.query_params.get("msg_signature")
                            timestamp = request.query_params.get("timestamp")
                            nonce = request.query_params.get("nonce")
                            print(
                                f"Parameters: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}"
                            )
                            return await channel._handle_message(
                                request, msg_signature, timestamp, nonce
                            )

                        self._app.include_router(wechat_router)
                        print(f"Directly added WeChat routes for path: {wechat_path}")
                        logger.info(
                            f"Directly added WeChat routes for path: {wechat_path}"
                        )
                    else:
                        # 其他通道使用默认方式
                        channel = self.channel_builder.build(
                            channel_config.name, channel_config.params
                        )

                    self.register_channel(channel_config.name, channel)
                    # 安装通道路由
                    if hasattr(channel, "install_router"):
                        if channel_config.name == "wechat":
                            # WeChatBotChatChannel需要prefix参数
                            channel.install_router(
                                self._app,
                                prefix=channel_config.path
                                if hasattr(channel_config, "path")
                                and channel_config.path
                                else "/wechat",
                            )
                        else:
                            channel.install_router(self._app)
                except Exception as e:
                    logger.error(f"Failed to create channel {channel_config.name}: {e}")

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

        if self._agent_executor:
            try:
                # 找到对应的通道
                channel_name = (
                    message.channel_id.split(":")[0]
                    if ":" in message.channel_id
                    else message.channel_id
                )
                channel = self.channels.get(channel_name)

                if channel_name == "wechat":
                    # 对于微信通道，使用get_full_response方法获取完整回复
                    reply_message = await self._agent_executor.get_full_response(
                        message
                    )
                    if channel and hasattr(channel, "send"):
                        await channel.send(reply_message)
                        print(
                            f"Sent final reply to WeChat channel: {reply_message.content}"
                        )
                else:
                    # 对于其他通道，使用原来的achat方法
                    reply_messages = await self._agent_executor.achat(message)
                    for reply_msg in reply_messages:
                        if channel and hasattr(channel, "send"):
                            await channel.send(reply_msg)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # 发送错误消息
                error_message = ChatMessage(
                    channel_id=message.channel_id,
                    content="Sorry, I encountered an error.",
                    content_type=ContentType.TEXT,
                    role="bot",
                    metadata={"finish": True},
                )
                channel_name = (
                    message.channel_id.split(":")[0]
                    if ":" in message.channel_id
                    else message.channel_id
                )
                channel = self.channels.get(channel_name)
                if channel and hasattr(channel, "send"):
                    await channel.send(error_message)
        else:
            # 没有智能体，直接回复
            response_content = f"Received: {message.content}"
            bot_message = ChatMessage(
                channel_id=message.channel_id,
                content=response_content,
                content_type=ContentType.TEXT,
                role="bot",
                metadata={"finish": True},
            )
            channel_name = (
                message.channel_id.split(":")[0]
                if ":" in message.channel_id
                else message.channel_id
            )
            channel = self.channels.get(channel_name)
            if channel and hasattr(channel, "send"):
                await channel.send(bot_message)

        process_time = int((time.time() - start_time) * 1000)
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
