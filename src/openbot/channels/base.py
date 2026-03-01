"""通道基类"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from openbot.common.config import ChannelConfig
from openbot.common.datamodel import Question, Answer


class Channel(ABC):
    """通道基类"""

    def __init__(self, config: ChannelConfig):
        self.config = config
        self.name = config.name
        self.enabled = config.enabled
        self.path = config.path
        self.params = config.params

    @abstractmethod
    async def start(self):
        """启动通道"""
        pass

    @abstractmethod
    async def stop(self):
        """停止通道"""
        pass

    @abstractmethod
    async def handle_message(self, message: Dict[str, Any]) -> Optional[Answer]:
        """处理消息

        Args:
            message: 消息内容

        Returns:
            回答内容
        """
        pass

    @abstractmethod
    def get_webhook_handler(self):
        """获取Webhook处理器

        Returns:
            Webhook处理器函数
        """
        pass
