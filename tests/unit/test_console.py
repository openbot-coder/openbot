import asyncio
import os
from unittest.mock import Mock, patch, MagicMock
from openbot.channels.console import ConsoleChannel, CommandCompleter
from openbot.channels.base import ChatMessage, ContentType


class TestConsoleChannel:
    """测试 ConsoleChannel 模块"""

    def test_command_completer(self):
        """测试命令补全器"""
        completer = CommandCompleter()
        
        # 测试补全功能
        class MockDocument:
            def __init__(self, text):
                self.text = text
        
        mock_document = MockDocument("h")
        completions = list(completer.get_completions(mock_document, None))
        
        # 验证补全结果
        assert len(completions) > 0
        assert any(completion.text == "help" for completion in completions)

    def test_console_channel_initialization(self):
        """测试控制台通道初始化"""
        channel = ConsoleChannel(prompt="test>")
        
        assert channel.prompt == "test>"
        assert channel.channel_id == "console"
        assert not channel.running
        assert channel.history_file == os.path.expanduser("~/.openbot_history")
        assert channel.botflow is None

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    async def test_console_channel_start(self, mock_prompt_session, mock_console_class):
        """测试控制台通道启动"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console.status = Mock(return_value=Mock(stop=Mock()))
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_prompt_session.return_value = mock_session
        
        # 创建通道并启动
        channel = ConsoleChannel()
        await channel.start()
        
        # 验证启动
        assert channel.running is True
        mock_console.print.assert_called()

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    async def test_console_channel_stop(self, mock_prompt_session, mock_console_class):
        """测试控制台通道停止"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console.status = Mock(return_value=Mock(stop=Mock()))
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_prompt_session.return_value = mock_session
        
        # 创建通道并启动
        channel = ConsoleChannel()
        await channel.start()
        await channel.stop()
        
        # 验证停止
        assert channel.running is False
        mock_console.print.assert_called()

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    async def test_console_channel_send(self, mock_prompt_session, mock_console_class):
        """测试控制台通道发送消息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console.status = Mock(return_value=Mock(stop=Mock()))
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_prompt_session.return_value = mock_session
        
        # 创建通道
        channel = ConsoleChannel()
        
        # 测试发送普通消息
        message = ChatMessage(
            content="Hello, world!",
            role="bot",
            channel_id="console"
        )
        await channel.send(message)
        
        # 测试发送带元数据的消息
        message_with_metadata = ChatMessage(
            content="Test content",
            role="bot",
            channel_id="console",
            metadata={"step": "model"}
        )
        await channel.send(message_with_metadata)
        
        # 验证调用
        assert mock_console.print.called

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    async def test_console_channel_on_receive(self, mock_prompt_session, mock_console_class):
        """测试控制台通道接收消息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_prompt_session.return_value = mock_session
        
        # 创建通道
        channel = ConsoleChannel()
        
        # 测试接收消息
        message = ChatMessage(
            content="Hello",
            role="user",
            channel_id="console"
        )
        await channel.on_receive(message)
        
        # 验证调用（on_receive 方法应该不做任何事情）
        # 这里主要是确保方法能够正常执行，不会抛出异常
        assert True

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    def test_console_channel_show_help(self, mock_prompt_session, mock_console_class):
        """测试显示帮助信息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_prompt_session.return_value = mock_session
        
        # 创建通道并测试
        channel = ConsoleChannel()
        channel._show_help()
        
        # 验证调用
        mock_console.print.assert_called()

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    async def test_console_channel_show_status(self, mock_prompt_session, mock_console_class):
        """测试显示状态信息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_prompt_session.return_value = mock_session
        
        # 创建通道并测试
        channel = ConsoleChannel()
        await channel._show_status()
        
        # 验证调用
        mock_console.print.assert_called()

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    async def test_console_channel_show_tasks(self, mock_prompt_session, mock_console_class):
        """测试显示任务信息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_prompt_session.return_value = mock_session
        
        # 创建通道并测试
        channel = ConsoleChannel()
        await channel._show_tasks()
        
        # 验证调用
        mock_console.print.assert_called()

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    async def test_console_channel_show_channels(self, mock_prompt_session, mock_console_class):
        """测试显示通道信息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_prompt_session.return_value = mock_session
        
        # 创建通道并测试
        channel = ConsoleChannel()
        await channel._show_channels()
        
        # 验证调用
        mock_console.print.assert_called()

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    def test_console_channel_show_version(self, mock_prompt_session, mock_console_class):
        """测试显示版本信息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_prompt_session.return_value = mock_session
        
        # 创建通道并测试
        channel = ConsoleChannel()
        channel._show_version()
        
        # 验证调用
        mock_console.print.assert_called()

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    def test_console_channel_show_history(self, mock_prompt_session, mock_console_class):
        """测试显示历史信息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_session.history = []
        mock_prompt_session.return_value = mock_session
        
        # 创建通道并测试
        channel = ConsoleChannel()
        channel._show_history()
        
        # 验证调用
        mock_console.print.assert_called()

    @patch('openbot.channels.console.Console')
    @patch('openbot.channels.console.PromptSession')
    async def test_console_channel_handle_command(self, mock_prompt_session, mock_console_class):
        """测试处理命令"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console.clear = Mock()
        mock_console.status = Mock(return_value=Mock(stop=Mock()))
        mock_console_class.return_value = mock_console
        
        mock_session = Mock()
        mock_session.history = []
        mock_prompt_session.return_value = mock_session
        
        # 创建通道并测试
        channel = ConsoleChannel()
        await channel.start()
        
        # 测试不同命令
        await channel._handle_command("help")
        await channel._handle_command("clear")
        await channel._handle_command("history")
        await channel._handle_command("unknown")
        
        # 验证调用
        mock_console.print.assert_called()
        mock_console.clear.assert_called()
