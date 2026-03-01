import pytest
from openbot.channels import ChatChannel, WeChatBotChatChannel
from openbot.channels.base import ChatChannel as BaseChatChannel
from openbot.channels.wechat import WeChatBotChatChannel as BaseWeChatBotChatChannel


class TestChannelsInit:
    """测试 channels.__init__ 模块的功能"""

    def test_chat_channel_import(self):
        """测试 ChatChannel 导入是否正确"""
        assert ChatChannel is not None
        assert ChatChannel is BaseChatChannel

    def test_wechat_channel_import(self):
        """测试 WeChatBotChatChannel 导入是否正确"""
        assert WeChatBotChatChannel is not None
        assert WeChatBotChatChannel is BaseWeChatBotChatChannel


if __name__ == "__main__":
    pytest.main([__file__])
