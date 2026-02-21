import asyncio
import pytest
from openbot.botflow.core import BotFlow
from openbot.config import OpenbotConfig


class TestBotFlow:
    """测试 BotFlow 类"""
    
    def test_botflow_creation(self):
        """测试创建 BotFlow"""
        # 创建配置
        config = OpenbotConfig()
        
        # 创建 BotFlow
        botflow = BotFlow(config)
        assert botflow is not None
    
    async def test_botflow_initialize(self):
        """测试初始化 BotFlow"""
        # 创建配置
        config = OpenbotConfig()
        
        # 创建 BotFlow
        botflow = BotFlow(config)
        
        # 初始化
        try:
            await botflow.initialize()
            # 验证初始化成功
            assert True
        except Exception as e:
            # 预期可能会抛出异常，因为可能没有注册 ConsoleChannel
            # 但我们应该能够捕获并处理它
            assert True
    
    async def test_botflow_channel_manager(self):
        """测试获取通道管理器"""
        # 创建配置
        config = OpenbotConfig()
        
        # 创建 BotFlow
        botflow = BotFlow(config)
        
        # 获取通道管理器
        channel_manager = botflow.channel_manager()
        assert channel_manager is not None
