"""BotFlow 通道基类"""

import uuid
from datetime import datetime
from enum import StrEnum
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any, Type, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, FastAPI


class ContentType(StrEnum):
    """消息内容类型"""

    TEXT = "text"
    VIDEO = "video"
    IMAGE = "image"
    FILE = "file"
    LINK = "link"
    STREAM = "stream"


class ChatMessage(BaseModel):
    """消息模型"""

    channel_id: str = Field(default="", description="渠道 ID")
    msg_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="消息 ID"
    )
    content: str = Field(default="", description="消息内容")
    content_type: ContentType = Field(
        default=ContentType.TEXT, description="消息内容类型"
    )
    role: Literal["user", "bot", "system"] = Field(
        default="user", description="消息角色"
    )
    metadata: dict = Field(default_factory=dict, description="消息元数据")
    input_tokens: int = Field(default=0, description="输入 token 数量")
    output_tokens: int = Field(default=0, description="输出 token 数量")
    process_time_ms: int = Field(default=0, description="处理时间（毫秒）")
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="创建时间"
    )


class ChatChannel(ABC):
    """聊天通道抽象基类"""

    def __init__(self, name: str):
        self.name = name
        self._message_handler: Optional[Callable] = None
        self._running = False
        self._router = self._init_router()

    @abstractmethod
    def _init_router(self) -> APIRouter:
        """初始化路由"""
        raise NotImplementedError

    def install_router(self, fastapi_app: FastAPI) -> None:
        """安装路由"""
        fastapi_app.include_router(self._router)

    @abstractmethod
    def set_message_handler(self, handler: Callable[[ChatMessage], Any]):
        """设置消息处理器"""
        self._message_handler = handler

    @abstractmethod
    async def start(self) -> None:
        """启动通道"""
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        """停止通道"""
        raise NotImplementedError

    @abstractmethod
    async def send(self, message: ChatMessage) -> None:
        """发送消息"""
        raise NotImplementedError

    async def on_receive(self, message: ChatMessage) -> None:
        """接收消息回调"""
        if self._message_handler:
            await self._message_handler(message)


class ChannelBuilder:
    """通道构建器"""

    def __init__(self):
        self._channels: dict[str, Type[ChatChannel]] = {}

    def register(self, name: str, channel_cls: Type[ChatChannel]) -> "ChannelBuilder":
        """注册通道"""
        self._channels[name] = channel_cls
        return self

    def get(self, name: str) -> Optional[Type[ChatChannel]]:
        """获取通道类"""
        return self._channels.get(name)

    def list_channels(self) -> list[str]:
        """列出所有通道名称"""
        return list(self._channels.keys())

    def build(self, channel_name: str, init_kwargs: dict) -> "ChatChannel":
        """构建通道"""
        channel_cls = self._channels.get(channel_name)
        if not channel_cls:
            raise ValueError(f"Channel {channel_name} not registered")

        return channel_cls(**init_kwargs)
