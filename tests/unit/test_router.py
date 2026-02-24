import asyncio
from unittest.mock import Mock
from openbot.botflow.router import ChannelRouter
from openbot.channels.base import ChatChannel, ChatMessage


class TestChannelRouter:
    """测试 ChannelRouter 模块"""

    def test_channel_router_initialization(self):
        """测试通道路由器初始化"""
        router = ChannelRouter()
        assert isinstance(router.channels, dict)
        assert len(router.channels) == 0

    def test_channel_router_register(self):
        """测试注册通道"""
        # 创建路由器
        router = ChannelRouter()

        # 创建模拟通道
        mock_channel = Mock(spec=ChatChannel)
        mock_channel.start = Mock(return_value=asyncio.Future())
        mock_channel.start.return_value.set_result(None)
        mock_channel.send = Mock(return_value=asyncio.Future())
        mock_channel.send.return_value.set_result(None)

        # 注册通道
        router.register("test-channel", mock_channel)

        # 验证注册
        assert "test-channel" in router.channels
        assert router.channels["test-channel"] == mock_channel

    async def test_channel_router_start_all(self):
        """测试启动所有通道"""
        # 创建路由器
        router = ChannelRouter()

        # 创建模拟通道
        mock_channel1 = Mock(spec=ChatChannel)
        mock_channel1.start = Mock(return_value=asyncio.Future())
        mock_channel1.start.return_value.set_result(None)
        mock_channel1.send = Mock(return_value=asyncio.Future())
        mock_channel1.send.return_value.set_result(None)

        mock_channel2 = Mock(spec=ChatChannel)
        mock_channel2.start = Mock(return_value=asyncio.Future())
        mock_channel2.start.return_value.set_result(None)
        mock_channel2.send = Mock(return_value=asyncio.Future())
        mock_channel2.send.return_value.set_result(None)

        # 注册通道
        router.register("channel1", mock_channel1)
        router.register("channel2", mock_channel2)

        # 启动所有通道
        await router.start_all()

        # 验证启动
        mock_channel1.start.assert_called_once()
        mock_channel2.start.assert_called_once()

    async def test_channel_router_broadcast(self):
        """测试广播消息到所有通道"""
        # 创建路由器
        router = ChannelRouter()

        # 创建模拟通道
        mock_channel1 = Mock(spec=ChatChannel)
        mock_channel1.start = Mock(return_value=asyncio.Future())
        mock_channel1.start.return_value.set_result(None)
        mock_channel1.send = Mock(return_value=asyncio.Future())
        mock_channel1.send.return_value.set_result(None)

        mock_channel2 = Mock(spec=ChatChannel)
        mock_channel2.start = Mock(return_value=asyncio.Future())
        mock_channel2.start.return_value.set_result(None)
        mock_channel2.send = Mock(return_value=asyncio.Future())
        mock_channel2.send.return_value.set_result(None)

        # 注册通道
        router.register("channel1", mock_channel1)
        router.register("channel2", mock_channel2)

        # 创建消息
        message = ChatMessage(content="Test message", role="bot")

        # 广播消息
        await router.broadcast(message)

        # 验证广播
        mock_channel1.send.assert_called_once_with(message)
        mock_channel2.send.assert_called_once_with(message)

    async def test_channel_router_broadcast_empty(self):
        """测试广播消息到空通道列表"""
        # 创建路由器
        router = ChannelRouter()

        # 创建消息
        message = ChatMessage(content="Test message", role="bot")

        # 广播消息（应该不会抛出异常）
        await router.broadcast(message)

        # 验证没有调用
        # 这里主要是确保方法能够正常执行，不会抛出异常
        assert True
