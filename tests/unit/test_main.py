import asyncio
import argparse
import logging
from unittest.mock import Mock, patch
from openbot.main import main, run_server, run_client


class TestMain:
    """测试 main.py 模块"""

    @patch("openbot.main.ConfigManager")
    @patch("openbot.main.BotFlow")
    @patch("argparse.ArgumentParser.parse_args")
    async def test_main_server_mode(
        self, mock_parse_args, mock_botflow_class, mock_config_manager_class
    ):
        """测试服务器模式"""
        # 模拟命令行参数
        mock_args = Mock()
        mock_args.command = "server"
        mock_args.config = "test_config.json"
        mock_args.console = True
        mock_parse_args.return_value = mock_args

        # 模拟配置管理器
        mock_config_manager = Mock()
        mock_config = Mock()
        mock_config.channels = {"console": Mock(enabled=False)}
        mock_config_manager.get.return_value = mock_config
        mock_config_manager_class.return_value = mock_config_manager

        # 模拟 BotFlow
        mock_botflow = Mock()
        mock_botflow.run = Mock(return_value=asyncio.Future())
        mock_botflow.run.return_value.set_result(None)
        mock_botflow.stop = Mock(return_value=asyncio.Future())
        mock_botflow.stop.return_value.set_result(None)
        mock_botflow_class.return_value = mock_botflow

        # 运行 main 函数（使用超时以避免无限等待）
        try:
            await asyncio.wait_for(main(), timeout=1.0)
        except asyncio.TimeoutError:
            # 预期的超时，因为我们模拟了 run 方法
            pass

        # 验证调用
        mock_config_manager_class.assert_called_once_with("test_config.json")
        assert mock_config.channels["console"].enabled is True
        mock_botflow_class.assert_called_once_with(mock_config)
        mock_botflow.run.assert_called_once()
        mock_botflow.stop.assert_called_once()

    @patch("argparse.ArgumentParser.parse_args")
    @patch("logging.warning")
    async def test_main_client_mode(self, mock_warning, mock_parse_args):
        """测试客户端模式"""
        # 模拟命令行参数
        mock_args = Mock()
        mock_args.command = "client"
        mock_args.url = "ws://localhost:8000"
        mock_args.config = "test_config.json"
        mock_args.token = "test_token"
        mock_parse_args.return_value = mock_args

        # 运行 run_client 函数
        await run_client(mock_args.url, mock_args.config, mock_args.token)

        # 验证调用
        mock_warning.assert_any_call("Client mode is not implemented in MVP version.")
        mock_warning.assert_any_call("Please use server mode instead.")

    @patch("openbot.main.ConfigManager")
    @patch("openbot.main.BotFlow")
    @patch("argparse.ArgumentParser.parse_args")
    async def test_main_backward_compatibility(
        self, mock_parse_args, mock_botflow_class, mock_config_manager_class
    ):
        """测试向后兼容模式"""
        # 模拟命令行参数（无 command）
        mock_args = Mock()
        mock_args.command = None
        mock_args.config = "test_config.json"
        mock_args.channel = "console"
        mock_parse_args.return_value = mock_args

        # 模拟配置管理器
        mock_config_manager = Mock()
        mock_config = Mock()
        mock_config.channels = {"console": Mock(enabled=False)}
        mock_config_manager.get.return_value = mock_config
        mock_config_manager_class.return_value = mock_config_manager

        # 模拟 BotFlow
        mock_botflow = Mock()
        mock_botflow.run = Mock(return_value=asyncio.Future())
        mock_botflow.run.return_value.set_result(None)
        mock_botflow.stop = Mock(return_value=asyncio.Future())
        mock_botflow.stop.return_value.set_result(None)
        mock_botflow_class.return_value = mock_botflow

        # 运行 main 函数（使用超时以避免无限等待）
        try:
            await asyncio.wait_for(main(), timeout=1.0)
        except asyncio.TimeoutError:
            # 预期的超时，因为我们模拟了 run 方法
            pass

        # 验证调用
        mock_config_manager_class.assert_called_once_with("test_config.json")
        mock_botflow_class.assert_called_once_with(mock_config)
        mock_botflow.run.assert_called_once()
        mock_botflow.stop.assert_called_once()

    @patch("openbot.main.ConfigManager")
    @patch("openbot.main.BotFlow")
    async def test_run_server(self, mock_botflow_class, mock_config_manager_class):
        """测试 run_server 函数"""
        # 模拟配置管理器
        mock_config_manager = Mock()
        mock_config = Mock()
        mock_config.channels = {"console": Mock(enabled=False)}
        mock_config_manager.get.return_value = mock_config
        mock_config_manager_class.return_value = mock_config_manager

        # 模拟 BotFlow
        mock_botflow = Mock()
        mock_botflow.run = Mock(return_value=asyncio.Future())
        mock_botflow.run.return_value.set_result(None)
        mock_botflow.stop = Mock(return_value=asyncio.Future())
        mock_botflow.stop.return_value.set_result(None)
        mock_botflow_class.return_value = mock_botflow

        # 运行 run_server 函数（使用超时以避免无限等待）
        try:
            await asyncio.wait_for(
                run_server("test_config.json", console=True), timeout=1.0
            )
        except asyncio.TimeoutError:
            # 预期的超时，因为我们模拟了 run 方法
            pass

        # 验证调用
        mock_config_manager_class.assert_called_once_with("test_config.json")
        assert mock_config.channels["console"].enabled is True
        mock_botflow_class.assert_called_once_with(mock_config)
        mock_botflow.run.assert_called_once()
        mock_botflow.stop.assert_called_once()

    @patch("logging.info")
    @patch("logging.warning")
    async def test_run_client(self, mock_warning, mock_info):
        """测试 run_client 函数"""
        # 运行 run_client 函数
        await run_client("ws://localhost:8000", "test_config.json", "test_token")

        # 验证调用
        mock_info.assert_any_call(
            "Starting OpenBot client with URL: ws://localhost:8000"
        )
        mock_info.assert_any_call("Loading configuration from: test_config.json")
        mock_warning.assert_any_call("Client mode is not implemented in MVP version.")
        mock_warning.assert_any_call("Please use server mode instead.")
