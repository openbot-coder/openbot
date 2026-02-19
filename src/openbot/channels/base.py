from abc import ABC, abstractmethod
from typing import AsyncIterator
from pydantic import BaseModel

class Message(BaseModel):
    content: str
    role: str  # "user" | "assistant"
    metadata: dict | None = None

class ChatChannel(ABC):
    @abstractmethod
    async def start(self) -> None:
        """启动 Channel"""
        pass
    
    @abstractmethod
    async def send(self, message: Message) -> None:
        """发送完整消息"""
        pass
    
    @abstractmethod
    async def send_stream(self, stream: AsyncIterator[str]) -> None:
        """发送流式响应"""
        pass
    
    @abstractmethod
    async def receive(self) -> AsyncIterator[Message]:
        """接收消息流"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止 Channel"""
        pass