import asyncio
import json
from unittest.mock import Mock, patch, MagicMock
from openbot.channels.websocket import WebSocketChannel
from openbot.channels.base import ChatMessage, ContentType


class TestWebSocketChannel:
    """测试 WebSocketChannel 模块"""

    def test_websocket_channel_initialization(self):
        """测试 WebSocket 通道初始化"""
        channel = WebSocketChannel(host="127.0.0.1", port=8000)

        assert channel.host == "127.0.0.1"
        assert channel.port == 8000
        assert not channel.running
        assert channel.server is None
        assert len(channel.connections) == 0
        assert channel.botflow is None
        assert channel.channel_id == "websocket-127.0.0.1:8000"

    @patch("openbot.channels.websocket.Console")
    @patch("openbot.channels.websocket.serve")
    async def test_websocket_channel_start(self, mock_serve, mock_console_class):
        """测试 WebSocket 通道启动"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console

        mock_server = Mock()
        mock_server.close = Mock(return_value=asyncio.Future())
        mock_server.close.return_value.set_result(None)
        mock_server.wait_closed = Mock(return_value=asyncio.Future())
        mock_server.wait_closed.return_value.set_result(None)
        mock_serve.return_value = asyncio.Future()
        mock_serve.return_value.set_result(mock_server)

        # 创建通道并启动
        channel = WebSocketChannel()
        await channel.start()

        # 验证启动
        assert channel.running is True
        assert channel.server == mock_server
        mock_console.print.assert_called()
        mock_serve.assert_called_once()

    @patch("openbot.channels.websocket.Console")
    @patch("openbot.channels.websocket.serve")
    async def test_websocket_channel_stop(self, mock_serve, mock_console_class):
        """测试 WebSocket 通道停止"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console

        mock_server = Mock()
        mock_server.close = Mock(return_value=asyncio.Future())
        mock_server.close.return_value.set_result(None)
        mock_server.wait_closed = Mock(return_value=asyncio.Future())
        mock_server.wait_closed.return_value.set_result(None)
        mock_serve.return_value = asyncio.Future()
        mock_serve.return_value.set_result(mock_server)

        # 创建通道并启动
        channel = WebSocketChannel()
        await channel.start()
        await channel.stop()

        # 验证停止
        assert channel.running is False
        mock_server.close.assert_called_once()
        mock_server.wait_closed.assert_called_once()
        mock_console.print.assert_called()

    @patch("openbot.channels.websocket.Console")
    async def test_websocket_channel_send(self, mock_console_class):
        """测试 WebSocket 通道发送消息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console

        # 创建通道
        channel = WebSocketChannel()

        # 模拟 WebSocket 连接
        mock_websocket = Mock()
        mock_websocket.send = Mock(return_value=asyncio.Future())
        mock_websocket.send.return_value.set_result(None)
        channel.connections.add(mock_websocket)

        # 测试发送消息
        message = ChatMessage(
            content="Hello, world!", role="bot", channel_id=channel.channel_id
        )
        await channel.send(message)

        # 验证调用
        mock_websocket.send.assert_called_once()
        args, kwargs = mock_websocket.send.call_args
        sent_data = json.loads(args[0])
        assert sent_data["type"] == "message"
        assert sent_data["content"] == "Hello, world!"
        assert sent_data["role"] == "bot"

    @patch("openbot.channels.websocket.Console")
    async def test_websocket_channel_send_with_closed_connection(
        self, mock_console_class
    ):
        """测试 WebSocket 通道发送消息时连接已关闭的情况"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console

        # 创建通道
        channel = WebSocketChannel()

        # 模拟已关闭的 WebSocket 连接
        mock_websocket = Mock()
        from websockets.exceptions import ConnectionClosedError

        mock_websocket.send = Mock(
            side_effect=ConnectionClosedError(1000, "Connection closed")
        )
        channel.connections.add(mock_websocket)

        # 测试发送消息
        message = ChatMessage(
            content="Hello, world!", role="bot", channel_id=channel.channel_id
        )
        await channel.send(message)

        # 验证调用
        mock_websocket.send.assert_called_once()
        assert mock_websocket not in channel.connections

    @patch("openbot.channels.websocket.Console")
    async def test_websocket_channel_process_message(self, mock_console_class):
        """测试 WebSocket 通道处理消息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console

        # 创建通道并设置消息队列
        channel = WebSocketChannel()
        message_queue = asyncio.Queue()
        channel.set_message_queue(message_queue)

        # 模拟 WebSocket 连接
        mock_websocket = Mock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)

        # 测试处理消息
        test_message = json.dumps({"content": "Hello from WebSocket"})
        await channel._process_message(mock_websocket, test_message)

        # 验证消息已放入队列
        assert not message_queue.empty()
        queue_message = await message_queue.get()
        assert queue_message.content == "Hello from WebSocket"
        assert queue_message.role == "user"
        assert queue_message.channel_id == channel.channel_id

    @patch("openbot.channels.websocket.Console")
    async def test_websocket_channel_process_invalid_message(self, mock_console_class):
        """测试 WebSocket 通道处理无效消息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console

        # 创建通道
        channel = WebSocketChannel()

        # 模拟 WebSocket 连接
        mock_websocket = Mock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)

        # 测试处理无效消息（非 JSON）
        test_message = "This is not JSON"
        await channel._process_message(mock_websocket, test_message)

        # 验证调用
        mock_console.print.assert_called()

    @patch("openbot.channels.websocket.Console")
    async def test_websocket_channel_handle_connection(self, mock_console_class):
        """测试 WebSocket 通道处理连接"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console

        # 创建通道
        channel = WebSocketChannel()

        # 模拟 WebSocket 连接
        mock_websocket = Mock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)
        mock_websocket.send = Mock(return_value=asyncio.Future())
        mock_websocket.send.return_value.set_result(None)

        # 模拟异步迭代器
        async def mock_async_iter():
            yield json.dumps({"content": "Test message"})

        mock_websocket.__aiter__ = Mock(return_value=mock_async_iter())

        # 设置消息队列
        message_queue = asyncio.Queue()
        channel.set_message_queue(message_queue)

        # 测试处理连接
        try:
            # 使用超时以避免无限等待
            await asyncio.wait_for(
                channel._handle_connection(mock_websocket), timeout=0.5
            )
        except asyncio.TimeoutError:
            # 预期的超时，因为我们模拟了异步迭代器
            pass

        # 验证调用
        assert mock_websocket not in channel.connections
        mock_websocket.send.assert_called_once()
        mock_console.print.assert_called()

    @patch("openbot.channels.websocket.Console")
    async def test_websocket_channel_send_stream(self, mock_console_class):
        """测试 WebSocket 通道发送流式消息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console.print = Mock()
        mock_console_class.return_value = mock_console

        # 创建通道
        channel = WebSocketChannel()

        # 模拟 WebSocket 连接
        mock_websocket = Mock()
        mock_websocket.send = Mock(return_value=asyncio.Future())
        mock_websocket.send.return_value.set_result(None)
        channel.connections.add(mock_websocket)

        # 模拟流式消息
        async def mock_stream():
            class MockMessage:
                def __init__(self, content):
                    self.content = content

            yield MockMessage("Hello, ")
            yield MockMessage("world!")

        # 测试发送流式消息
        await channel.send_stream(mock_stream())

        # 验证调用
        mock_websocket.send.assert_called_once()
        args, kwargs = mock_websocket.send.call_args
        sent_data = json.loads(args[0])
        assert sent_data["type"] == "message"
        assert sent_data["content"] == "Hello, world!"
        assert sent_data["role"] == "bot"

    @patch("openbot.channels.websocket.Console")
    async def test_websocket_channel_on_receive(self, mock_console_class):
        """测试 WebSocket 通道接收消息"""
        # 模拟依赖
        mock_console = Mock()
        mock_console_class.return_value = mock_console

        # 创建通道
        channel = WebSocketChannel()

        # 测试接收消息
        message = ChatMessage(
            content="Hello", role="user", channel_id=channel.channel_id
        )
        await channel.on_receive(message)

        # 验证调用（on_receive 方法应该不做任何事情）
        # 这里主要是确保方法能够正常执行，不会抛出异常
        assert True
