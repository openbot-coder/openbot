"""BotFlow 通道基类"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any, Type

from ..database import ChatMessage, ContentType


class ChatChannel(ABC):
    """聊天通道抽象基类"""

    def __init__(self, name: str):
        self.name = name
        self._message_handler: Optional[Callable] = None
        self._running = False

    def set_message_handler(self, handler: Callable[[ChatMessage], Any]):
        """设置消息处理器"""
        self._message_handler = handler

    @abstractmethod
    async def start(self) -> None:
        """启动通道"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止通道"""
        pass

    @abstractmethod
    async def send(self, message: ChatMessage) -> None:
        """发送消息"""
        pass

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

        return channel_cls(channel_name, **init_kwargs)
