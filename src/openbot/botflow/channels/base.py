"""BotFlow 通道基类"""
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any

from ..database import ChatMessage, ContentType


class ChatChannel(ABC):
    """聊天通道抽象基类"""
    
    def __init__(self, name: str):
        self.name = name
        self._message_handler: Optional[Callable] = None
        self._running = False
    
    def set_message_handler(self, handler: Callable[[str, str, str], Any]):
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
    async def send(self, content: str, reply_to: str = "") -> None:
        """发送消息"""
        pass
    
    async def on_receive(self, content: str, channel_id: str, reply_to: str = "") -> None:
        """接收消息回调"""
        if self._message_handler:
            await self._message_handler(content, channel_id, reply_to)


class ChannelBuilder:
    """通道构建器"""
    
    def __init__(self):
        self._channels: dict[str, ChatChannel] = {}
    
    def register(self, name: str, channel: ChatChannel) -> "ChannelBuilder":
        """注册通道"""
        self._channels[name] = channel
        return self
    
    def get(self, name: str) -> Optional[ChatChannel]:
        """获取通道"""
        return self._channels.get(name)
    
    def list_channels(self) -> list[str]:
        """列出所有通道名称"""
        return list(self._channels.keys())
