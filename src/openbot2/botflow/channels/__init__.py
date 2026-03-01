"""BotFlow 通道模块"""

from .base import ChatChannel, ChannelBuilder
from .wechat import WeChatBotChatChannel

__all__ = ["ChatChannel", "ChannelBuilder", "WeChatBotChatChannel"]
