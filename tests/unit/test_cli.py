"""Tests for openbot.agents.cli module"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, patch, AsyncMock, MagicMock, mock_open
from pathlib import Path
from datetime import datetime

from openbot.agents.cli import AgentCLI, setup_logging, main
from openbot.channels.base import ChatMessage, ContentType


class TestSetupLogging:
    """Test setup_logging function"""

    @patch("pathlib.Path.mkdir")
    @patch("logging.FileHandler")
    @patch("logging.StreamHandler")
    @patch("logging.getLogger")
    def test_setup_logging_creates_log_dir(
        self, mock_get_logger, mock_stream_handler, mock_file_handler, mock_mkdir
    ):
        """Test that setup_logging creates logs directory"""
        setup_logging()

        mock_mkdir.assert_called_once_with(exist_ok=True)

    @patch("pathlib.Path.mkdir")
    @patch("logging.FileHandler")
    @patch("logging.StreamHandler")
    @patch("logging.getLogger")
    @patch("datetime.datetime")
    def test_setup_logging_uses_date_in_filename(
        self,
        mock_datetime,
        mock_get_logger,
        mock_stream_handler,
        mock_file_handler,
        mock_mkdir,
    ):
        """Test that log file includes date in filename"""
        mock_now = Mock()
        mock_now.strftime.return_value = "20260101"
        mock_datetime.now.return_value = mock_now

        with patch("openbot.agents.cli.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            setup_logging()

        # Verify FileHandler was called with a path containing the date
        call_args = mock_file_handler.call_args
        assert "20260101" in str(call_args)

    @patch("pathlib.Path.mkdir")
    @patch("logging.FileHandler")
    @patch("logging.StreamHandler")
    @patch("logging.getLogger")
    def test_setup_logging_configures_root_logger(
        self, mock_get_logger, mock_stream_handler, mock_file_handler, mock_mkdir
    ):
        """Test that root logger is configured"""
        mock_root_logger = Mock()
        mock_get_logger.return_value = mock_root_logger

        setup_logging()

        mock_get_logger.assert_called_once()
        assert mock_root_logger.setLevel.called
        assert mock_root_logger.addHandler.called


class TestAgentCLI:
    """Test AgentCLI class"""

    def test_init(self):
        """Test AgentCLI initialization"""
        cli = AgentCLI()

        assert cli.agent is None
        assert cli.running is False
        assert cli.channel_id == "cli_console"
        assert cli.prompt == "openbot> "
        assert cli._current_response_started is False

    def test_init_creates_console(self):
        """Test that AgentCLI creates a Console instance"""
        cli = AgentCLI()

        assert cli.console is not None

    def test_init_creates_session(self):
        """Test that AgentCLI creates a PromptSession"""
        cli = AgentCLI()

        assert cli.session is not None

    @patch("rich.console.Console.print")
    def test_print_banner(self, mock_print):
        """Test print_banner method"""
        cli = AgentCLI()
        cli.print_banner()

        mock_print.assert_called_once()
        # Verify Panel was called with OpenBot text
        call_args = mock_print.call_args
        assert "OpenBot" in str(call_args)

    @patch("rich.console.Console.print")
    def test_print_help(self, mock_print):
        """Test print_help method"""
        cli = AgentCLI()
        cli.print_help()

        # Should print table with commands
        assert mock_print.called
        call_args = str(mock_print.call_args)
        assert "/help" in call_args or "help" in call_args

    @patch("rich.console.Console.print")
    def test_print_models_without_agent(self, mock_print):
        """Test print_models when agent is None"""
        cli = AgentCLI()
        cli.print_models()

        mock_print.assert_called_once()
        assert (
            "未初始化" in str(mock_print.call_args)
            or "error" in str(mock_print.call_args).lower()
        )

    @patch("rich.console.Console.print")
    def test_print_models_with_agent(self, mock_print):
        """Test print_models with agent"""
        cli = AgentCLI()
        cli.agent = Mock()
        cli.agent.model_manager.list_models.return_value = {
            "model1": Mock(model_name="gpt-4"),
            "model2": Mock(model_name="claude-3"),
        }

        cli.print_models()

        assert mock_print.called

    @pytest.mark.asyncio
    async def test_print_tools_without_agent(self):
        """Test print_tools when agent is None"""
        cli = AgentCLI()

        with patch.object(cli.console, "print") as mock_print:
            await cli.print_tools()

            mock_print.assert_called_once()
            assert (
                "未初始化" in str(mock_print.call_args)
                or "error" in str(mock_print.call_args).lower()
            )

    @pytest.mark.asyncio
    async def test_print_tools_with_agent(self):
        """Test print_tools with agent"""
        cli = AgentCLI()
        cli.agent = Mock()
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test description"
        cli.agent._tools_manager.get_tools = AsyncMock(return_value=[mock_tool])

        with patch.object(cli.console, "print") as mock_print:
            await cli.print_tools()

            assert mock_print.called

    @patch("rich.console.Console.print")
    def test_print_status_without_agent(self, mock_print):
        """Test print_status when agent is None"""
        cli = AgentCLI()
        cli.running = True
        cli.print_status()

        assert mock_print.called

    @patch("rich.console.Console.print")
    def test_print_status_with_agent(self, mock_print):
        """Test print_status with agent"""
        cli = AgentCLI()
        cli.running = True
        cli.agent = Mock()
        cli.agent._agent_config.workspace = "/test/workspace"
        cli.print_status()

        assert mock_print.called

    def test_handle_streaming_message_model_step(self):
        """Test handle_streaming_message with model step"""
        cli = AgentCLI()
        message = ChatMessage(
            channel_id="test",
            content="Test response",
            role="bot",
            content_type=ContentType.TEXT,
            metadata={"step": "model"},
        )

        with patch.object(cli.console, "print") as mock_print:
            result = cli.handle_streaming_message(message)

            assert cli._current_response_started is True
            assert mock_print.called

    def test_handle_streaming_message_tools_step(self):
        """Test handle_streaming_message with tools step"""
        cli = AgentCLI()
        message = ChatMessage(
            channel_id="test",
            content="CallTools [result]",
            role="bot",
            content_type=ContentType.TEXT,
            metadata={"step": "tools"},
        )

        with patch.object(cli.console, "print") as mock_print:
            result = cli.handle_streaming_message(message)

            assert mock_print.called

    def test_handle_streaming_message_other_step(self):
        """Test handle_streaming_message with other step"""
        cli = AgentCLI()
        message = ChatMessage(
            channel_id="test",
            content="Processing...",
            role="bot",
            content_type=ContentType.TEXT,
            metadata={"step": "other"},
        )

        with patch.object(cli.console, "print") as mock_print:
            result = cli.handle_streaming_message(message)

            # Other steps should not print anything
            mock_print.assert_not_called()

    @pytest.mark.asyncio
    async def test_background_init_success(self):
        """Test _background_init success"""
        cli = AgentCLI()
        cli.agent = Mock()
        cli.agent.init_agent = AsyncMock()

        with patch.object(cli.console, "print") as mock_print:
            await cli._background_init()

            cli.agent.init_agent.assert_called_once()
            mock_print.assert_called_once()

    @pytest.mark.asyncio
    async def test_background_init_failure(self):
        """Test _background_init failure"""
        cli = AgentCLI()
        cli.agent = Mock()
        cli.agent.init_agent = AsyncMock(side_effect=Exception("Init failed"))

        with patch.object(cli.console, "print") as mock_print:
            await cli._background_init()

            mock_print.assert_called_once()
            assert (
                "失败" in str(mock_print.call_args)
                or "error" in str(mock_print.call_args).lower()
            )

    @pytest.mark.asyncio
    async def test_ensure_agent_ready_already_initialized(self):
        """Test _ensure_agent_ready when already initialized"""
        cli = AgentCLI()
        cli.agent = Mock()
        cli.agent.is_initialized = True

        result = await cli._ensure_agent_ready()

        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_agent_ready_initializing(self):
        """Test _ensure_agent_ready when initializing"""
        cli = AgentCLI()
        cli.agent = Mock()
        cli.agent.is_initialized = False
        cli.agent.is_initializing = True

        # Mock the while loop to exit immediately
        async def mock_init():
            cli.agent.is_initializing = False
            cli.agent.is_initialized = True

        cli.agent.init_agent = mock_init

        with patch.object(cli.console, "print"):
            result = await cli._ensure_agent_ready()

        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_agent_ready_not_initialized(self):
        """Test _ensure_agent_ready when not initialized"""
        cli = AgentCLI()
        cli.agent = Mock()
        cli.agent.is_initialized = False
        cli.agent.is_initializing = False
        cli.agent.init_agent = AsyncMock()

        with patch.object(cli.console, "status"):
            result = await cli._ensure_agent_ready()

        assert result is True
        cli.agent.init_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_agent_ready_no_agent(self):
        """Test _ensure_agent_ready when agent is None"""
        cli = AgentCLI()
        cli.agent = None

        with patch.object(cli.console, "print") as mock_print:
            result = await cli._ensure_agent_ready()

            assert result is False
            mock_print.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_without_agent(self):
        """Test chat when agent is None"""
        cli = AgentCLI()
        cli.agent = None

        with patch.object(cli.console, "print") as mock_print:
            await cli.chat("Hello")

            mock_print.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_with_agent(self):
        """Test chat with agent"""
        cli = AgentCLI()
        cli.agent = Mock()
        cli.agent.is_initialized = True
        cli.agent.achat = AsyncMock(return_value=[])

        with patch.object(cli.console, "print"):
            with patch.object(cli.console, "status"):
                await cli.chat("Hello")

        cli.agent.achat.assert_called_once()


class TestMain:
    """Test main function"""

    @patch("openbot.agents.cli.setup_logging")
    @patch("openbot.agents.cli.AgentCLI")
    @patch("asyncio.run")
    @patch("os.path.exists")
    def test_main_success(
        self, mock_exists, mock_asyncio_run, mock_cli_class, mock_setup_logging
    ):
        """Test main function success"""
        mock_exists.return_value = True
        mock_cli = Mock()
        mock_cli_class.return_value = mock_cli

        main()

        mock_setup_logging.assert_called_once()
        mock_cli_class.assert_called_once()
        mock_asyncio_run.assert_called_once()

    @patch("openbot.agents.cli.setup_logging")
    @patch("openbot.agents.cli.AgentCLI")
    @patch("asyncio.run")
    @patch("os.path.exists")
    @patch("rich.console.Console.print")
    def test_main_config_not_exists(
        self,
        mock_console_print,
        mock_exists,
        mock_asyncio_run,
        mock_cli_class,
        mock_setup_logging,
    ):
        """Test main function when config doesn't exist"""
        mock_exists.return_value = False
        mock_cli = Mock()
        mock_cli_class.return_value = mock_cli

        main()

        mock_setup_logging.assert_called_once()
        mock_console_print.assert_called()

    @patch("openbot.agents.cli.setup_logging")
    @patch("openbot.agents.cli.AgentCLI")
    @patch("asyncio.run")
    @patch("sys.exit")
    def test_main_exception(
        self, mock_exit, mock_asyncio_run, mock_cli_class, mock_setup_logging
    ):
        """Test main function with exception"""
        mock_asyncio_run.side_effect = Exception("Test error")

        main()

        mock_exit.assert_called_once_with(1)
