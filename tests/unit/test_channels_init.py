import pytest
from openbot.channels import ChatChannel, ConsoleChannel, WebSocketChannel
from openbot.channels.base import ChatChannel as BaseChatChannel
from openbot.channels.console import ConsoleChannel as BaseConsoleChannel
from openbot.channels.websocket import WebSocketChannel as BaseWebSocketChannel


class TestChannelsInit:
    """测试 channels.__init__ 模块的功能"""

    def test_chat_channel_import(self):
        """测试 ChatChannel 导入是否正确"""
        assert ChatChannel is not None
        assert ChatChannel is BaseChatChannel

    def test_console_channel_import(self):
        """测试 ConsoleChannel 导入是否正确"""
        assert ConsoleChannel is not None
        assert ConsoleChannel is BaseConsoleChannel

    def test_websocket_channel_import(self):
        """测试 WebSocketChannel 导入是否正确"""
        assert WebSocketChannel is not None
        assert WebSocketChannel is BaseWebSocketChannel


if __name__ == "__main__":
    pytest.main([__file__])
