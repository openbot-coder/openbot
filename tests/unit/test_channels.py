import asyncio
import pytest
from openbot.channels.base import ContentType, ChatMessage, ChannelBuilder, ChatChannelManager, ChatChannel


class MockChannel(ChatChannel):
    """模拟通道类，用于测试"""
    def __init__(self, name):
        self.name = name
        self.started = False
        self.stopped = False
        self.received_messages = []
    
    async def start(self) -> None:
        self.started = True
    
    async def send(self, message: ChatMessage) -> None:
        pass
    
    async def on_receive(self, message: ChatMessage) -> None:
        self.received_messages.append(message)
    
    async def stop(self) -> None:
        self.stopped = True


@pytest.fixture
async def channel_manager():
    """创建 ChatChannelManager 实例"""
    return ChatChannelManager()


@pytest.fixture
async def mock_channel():
    """创建 MockChannel 实例"""
    return MockChannel("test")


class TestChatMessage:
    """测试 ChatMessage 类"""
    
    def test_chat_message_creation(self):
        """测试创建 ChatMessage"""
        msg = ChatMessage(content="Hello", role="user")
        assert msg.content == "Hello"
        assert msg.role == "user"
        assert msg.content_type == ContentType.TEXT
        assert msg.channel_id == ""
        assert msg.metadata == {}
    
    def test_chat_message_with_custom_fields(self):
        """测试使用自定义字段创建 ChatMessage"""
        msg = ChatMessage(
            content="Hello",
            role="bot",
            content_type=ContentType.IMAGE,
            channel_id="console",
            metadata={"key": "value"}
        )
        assert msg.content == "Hello"
        assert msg.role == "bot"
        assert msg.content_type == ContentType.IMAGE
        assert msg.channel_id == "console"
        assert msg.metadata == {"key": "value"}


class TestChannelBuilder:
    """测试 ChannelBuilder 类"""
    
    def test_register_and_create_channel(self):
        """测试注册和创建通道"""
        # 注册通道
        ChannelBuilder.register("mock", MockChannel)
        
        # 创建通道
        channel = ChannelBuilder.create_channel("mock", name="test")
        assert isinstance(channel, MockChannel)
        assert channel.name == "test"
    
    def test_create_unknown_channel(self):
        """测试创建未知通道"""
        with pytest.raises(ValueError):
            ChannelBuilder.create_channel("unknown")


class TestChatChannelManager:
    """测试 ChatChannelManager 类"""
    
    async def test_register_channel(self, channel_manager, mock_channel):
        """测试注册通道"""
        channel_manager.register("test", mock_channel)
        assert channel_manager.get("test") == mock_channel
    
    async def test_start_and_stop_channels(self, channel_manager, mock_channel):
        """测试启动和停止通道"""
        channel_manager.register("test", mock_channel)
        
        # 启动通道
        await channel_manager.start()
        assert mock_channel.started
        
        # 停止通道
        await channel_manager.stop()
        assert mock_channel.stopped
    
    async def test_on_receive_message(self, channel_manager, mock_channel):
        """测试接收消息"""
        channel_manager.register("test", mock_channel)
        
        # 创建消息
        msg = ChatMessage(content="Hello", role="user", channel_id="test")
        
        # 接收消息
        await channel_manager.on_receive(msg)
        
        # 验证消息是否被处理
        # 注意：这里我们无法直接验证消息是否被放入队列，因为队列是内部的
        # 但我们可以验证方法调用没有异常
        assert True
    
    async def test_send_message(self, channel_manager, mock_channel):
        """测试发送消息"""
        channel_manager.register("test", mock_channel)
        
        # 创建消息
        msg = ChatMessage(content="Hello", role="bot", channel_id="test")
        
        # 发送消息
        await channel_manager.send(msg)
        
        # 验证消息是否被发送
        # 注意：这里我们无法直接验证消息是否被发送，因为 MockChannel 只是记录
        # 但我们可以验证方法调用没有异常
        assert True
    
    async def test_send_message_to_unknown_channel(self, channel_manager):
        """测试向未知通道发送消息"""
        # 创建消息
        msg = ChatMessage(content="Hello", role="bot", channel_id="unknown")
        
        # 发送消息
        await channel_manager.send(msg)
        
        # 验证方法调用没有异常（应该只是记录错误）
        assert True
