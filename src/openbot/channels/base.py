import uuid
import asyncio

from abc import ABC, abstractmethod
from enum import StrEnum
import logging
from typing import AsyncIterator, Literal, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from openbot.botflow.core import BotFlow


class ContentType(StrEnum):
    TEXT = "text"
    VIDEO = "video"
    IMAGE = "image"
    FILE = "file"
    LINK = "link"


class ChatMessage(BaseModel):
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


class ChatChannel(ABC):
    @abstractmethod
    async def start(self) -> None:
        """启动 Channel"""
        pass

    @abstractmethod
    async def send(self, message: ChatMessage) -> None:
        """发送完整消息"""
        pass

    @abstractmethod
    async def on_receive(self, message: ChatMessage) -> None:
        """处理接收消息"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止 Channel"""
        pass

    def set_message_queue(self, message_queue: asyncio.Queue) -> None:
        """设置消息 Queue"""
        self._message_queue = message_queue

    @property
    def message_queue(self) -> asyncio.Queue:
        """获取消息 Queue"""
        if hasattr(self, "_message_queue"):
            return self._message_queue
        else:
            raise AttributeError("message_queue not set")


class ChannelBuilder:
    __channel_types = {}

    @classmethod
    def register(cls, channel_type: str, channel_class: type[ChatChannel]) -> None:
        """注册 Channel 类"""
        cls.__channel_types[channel_type] = channel_class

    @classmethod
    def create_channel(cls, channel_type: str, **kwargs) -> ChatChannel:
        """创建 Channel"""
        channel_class = cls.__channel_types.get(channel_type)
        if channel_class:
            return channel_class(**kwargs)
        else:
            raise ValueError(f"Unknown channel type: {channel_type}")


class ChatChannelManager:
    def __init__(self) -> None:
        self._channels: dict[str, ChatChannel] = {}
        self._message_queue = asyncio.Queue()

    async def on_receive(self, message: ChatMessage) -> None:
        """处理接收消息"""
        self._message_queue.put_nowait(message)

    async def send(self, message: ChatMessage) -> None:
        """发送消息"""
        if message.channel_id in self._channels:
            await self._channels[message.channel_id].send(message)
        else:
            logging.error(f"Channel {message.channel_id} not found")

    def register(self, name: str, channel: ChatChannel) -> None:
        """注册 Channel"""
        channel.set_message_queue(self._message_queue)
        self._channels[name] = channel

    def get(self, name: str) -> ChatChannel:
        """获取 Channel"""
        return self._channels.get(name, None)

    async def start(self) -> None:
        """启动所有 Channel"""
        for channel in self._channels.values():
            await channel.start()

    async def stop(self) -> None:
        """停止所有 Channel"""
        for channel in self._channels.values():
            await channel.stop()
