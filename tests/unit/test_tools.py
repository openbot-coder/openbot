"""Tests for openbot.agents.tools module"""

import pytest
import asyncio
import json
import os
from unittest.mock import Mock, patch, mock_open, AsyncMock, MagicMock
from pathlib import Path
from datetime import datetime

from openbot.agents.tools import (
    get_current_time,
    remove_file,
    run_bash_command,
    ToolsManager,
    RUBISHBIN,
)


class TestGetCurrentTime:
    """Test get_current_time function"""

    def test_get_current_time_returns_string(self):
        """Test that get_current_time returns a string"""
        result = get_current_time()
        assert isinstance(result, str)

    def test_get_current_time_format(self):
        """Test that get_current_time returns correct format"""
        result = get_current_time()
        # Should be in format: YYYY-MM-DD HH:MM:SS
        assert len(result) == 19
        assert result[4] == '-'
        assert result[7] == '-'
        assert result[10] == ' '
        assert result[13] == ':'
        assert result[16] == ':'

    def test_get_current_time_is_current(self):
        """Test that get_current_time returns current time"""
        before = datetime.now()
        result = get_current_time()
        after = datetime.now()
        
        result_dt = datetime.strptime(result, "%Y-%m-%d %H:%M:%S")
        assert before <= result_dt <= after


class TestRemoveFile:
    """Test remove_file function"""

    def test_remove_file_moves_to_trash(self, tmp_path):
        """Test that remove_file moves file to trash"""
        # Create a test file
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test content")
        
        # Create trash directory
        trash_dir = tmp_path / ".trash"
        trash_dir.mkdir(exist_ok=True)
        
        with patch('openbot.agents.tools.RUBISHBIN', trash_dir):
            success, error = remove_file(str(test_file))
            
            assert success is True
            assert error == ""
            assert not test_file.exists()
            assert (trash_dir / "test_file.txt").exists()

    def test_remove_directory_moves_to_trash(self, tmp_path):
        """Test that remove_file moves directory to trash"""
        # Create a test directory
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
        
        # Create trash directory
        trash_dir = tmp_path / ".trash"
        trash_dir.mkdir(exist_ok=True)
        
        with patch('openbot.agents.tools.RUBISHBIN', trash_dir):
            success, error = remove_file(str(test_dir))
            
            assert success is True
            assert error == ""
            assert not test_dir.exists()
            assert (trash_dir / "test_dir").exists()

    def test_remove_file_creates_trash_if_not_exists(self, tmp_path):
        """Test that remove_file creates trash directory if it doesn't exist"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test content")
        
        trash_dir = tmp_path / ".trash"
        
        with patch('openbot.agents.tools.RUBISHBIN', trash_dir):
            success, error = remove_file(str(test_file))
            
            assert success is True
            assert trash_dir.exists()

    def test_remove_file_not_found(self, tmp_path):
        """Test remove_file with non-existent file"""
        non_existent = tmp_path / "non_existent.txt"
        
        trash_dir = tmp_path / ".trash"
        trash_dir.mkdir(exist_ok=True)
        
        with patch('openbot.agents.tools.RUBISHBIN', trash_dir):
            success, error = remove_file(str(non_existent))
            
            assert success is False
            assert "not found" in error

    def test_remove_file_overwrites_existing_in_trash(self, tmp_path):
        """Test that remove_file overwrites existing file in trash"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("new content")
        
        trash_dir = tmp_path / ".trash"
        trash_dir.mkdir(exist_ok=True)
        (trash_dir / "test_file.txt").write_text("old content")
        
        with patch('openbot.agents.tools.RUBISHBIN', trash_dir):
            success, error = remove_file(str(test_file))
            
            assert success is True
            assert (trash_dir / "test_file.txt").read_text() == "new content"


class TestRunBashCommand:
    """Test run_bash_command function"""

    @patch('subprocess.run')
    @patch('logging.info')
    def test_run_bash_command_success(self, mock_log, mock_run):
        """Test successful command execution"""
        mock_run.return_value = Mock(stdout="  output  ", returncode=0)
        
        result = run_bash_command("echo hello")
        
        assert result == "output"
        mock_run.assert_called_once()
        mock_log.assert_called_once()

    @patch('subprocess.run')
    @patch('logging.info')
    def test_run_bash_command_strips_output(self, mock_log, mock_run):
        """Test that output is stripped of whitespace"""
        mock_run.return_value = Mock(stdout="  trimmed  ", returncode=0)
        
        result = run_bash_command("echo test")
        
        assert result == "trimmed"

    @patch('subprocess.run')
    @patch('logging.info')
    def test_run_bash_command_failure(self, mock_log, mock_run):
        """Test command failure handling"""
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "cmd", output="error output")
        
        result = run_bash_command("bad_command")
        
        assert "Error" in result
        assert "exit code 1" in result

    @patch('subprocess.run')
    @patch('logging.info')
    def test_run_bash_command_uses_shell(self, mock_log, mock_run):
        """Test that command uses shell=True"""
        mock_run.return_value = Mock(stdout="", returncode=0)
        
        run_bash_command("echo test")
        
        _, kwargs = mock_run.call_args
        assert kwargs['shell'] is True

    @patch('subprocess.run')
    @patch('logging.info')
    def test_run_bash_command_logs_execution(self, mock_log, mock_run):
        """Test that command execution is logged"""
        mock_run.return_value = Mock(stdout="", returncode=0)
        
        run_bash_command("echo test")
        
        mock_log.assert_called_once()
        assert "echo test" in mock_log.call_args[0][0]


class TestToolsManager:
    """Test ToolsManager class"""

    def test_init(self):
        """Test ToolsManager initialization"""
        manager = ToolsManager()
        
        assert manager._mcp_configs == {}
        assert manager._clients == []

    @patch('os.path.exists')
    def test_load_tools_from_config_file_not_found(self, mock_exists):
        """Test load_tools_from_config with missing file"""
        mock_exists.return_value = False
        
        manager = ToolsManager()
        success, tools = manager.load_tools_from_config("/nonexistent/config.json")
        
        assert success is False
        assert tools == []

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "mcpServers": {
            "test": {"command": "test", "args": ["arg1"]}
        }
    }))
    @patch('openbot.agents.tools.MultiServerMCPClient')
    def test_load_tools_from_config_success(self, mock_client, mock_file, mock_exists):
        """Test successful config loading"""
        mock_exists.return_value = True
        
        manager = ToolsManager()
        success = manager.load_tools_from_config("config.json")
        
        assert success is True
        assert "test" in manager._mcp_configs

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="invalid json")
    def test_load_tools_from_config_invalid_json(self, mock_file, mock_exists):
        """Test config loading with invalid JSON"""
        mock_exists.return_value = True
        
        manager = ToolsManager()
        success, tools = manager.load_tools_from_config("config.json")
        
        assert success is False

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({}))
    def test_load_tools_from_config_no_mcp_servers(self, mock_file, mock_exists):
        """Test config loading without mcpServers"""
        mock_exists.return_value = True
        
        manager = ToolsManager()
        success = manager.load_tools_from_config("config.json")
        
        assert success is True

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch.dict(os.environ, {"TEST_VAR": "test_value"})
    def test_load_tools_from_config_with_env_vars(self, mock_file, mock_exists):
        """Test config loading with environment variables"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps({
            "mcpServers": {
                "test": {"command": "${TEST_VAR}"}
            }
        })
        
        manager = ToolsManager()
        success = manager.load_tools_from_config("config.json")
        
        assert success is True
        assert manager._mcp_configs["test"]["command"] == "test_value"

    @patch('openbot.agents.tools.MultiServerMCPClient')
    def test_load_tools_from_dict(self, mock_client):
        """Test loading tools from dictionary"""
        manager = ToolsManager()
        config = {
            "test": {"command": "test", "args": ["arg1"]}
        }
        
        success = manager.load_tools_from_dict(config)
        
        assert success is True
        assert "test" in manager._mcp_configs
        mock_client.assert_called_once()

    @patch('openbot.agents.tools.MultiServerMCPClient')
    def test_load_tools_from_dict_with_mcp_servers_key(self, mock_client):
        """Test loading with mcpServers wrapper"""
        manager = ToolsManager()
        config = {
            "mcpServers": {
                "test": {"command": "test"}
            }
        }
        
        success = manager.load_tools_from_dict(config)
        
        assert success is True
        assert "test" in manager._mcp_configs

    @patch('openbot.agents.tools.MultiServerMCPClient')
    def test_load_tools_from_dict_duplicate_server(self, mock_client):
        """Test loading duplicate server is skipped"""
        manager = ToolsManager()
        manager._mcp_configs["existing"] = {"command": "existing"}
        
        config = {
            "existing": {"command": "new"},
            "new": {"command": "new"}
        }
        
        success = manager.load_tools_from_dict(config)
        
        assert success is True
        # Should only create client for "new" server
        mock_client.assert_called_once()

    @patch('openbot.agents.tools.MultiServerMCPClient')
    def test_load_tools_from_dict_default_transport(self, mock_client):
        """Test that default transport is added"""
        manager = ToolsManager()
        config = {
            "test": {"command": "test"}  # No transport specified
        }
        
        manager.load_tools_from_dict(config)
        
        assert manager._mcp_configs["test"]["transport"] == "stdio"

    def test_resolve_env_vars_nested_dict(self):
        """Test resolving env vars in nested dict"""
        manager = ToolsManager()
        with patch.dict(os.environ, {"VAR": "value"}):
            config = {
                "level1": {
                    "level2": "${VAR}"
                }
            }
            result = manager._resolve_env_vars(config)
            
            assert result["level1"]["level2"] == "value"

    def test_resolve_env_vars_missing_var(self):
        """Test resolving missing env var"""
        manager = ToolsManager()
        config = {"key": "${MISSING_VAR}"}
        
        result = manager._resolve_env_vars(config)
        
        assert result["key"] is None

    def test_resolve_env_vars_not_env_var(self):
        """Test that non-env-var strings are preserved"""
        manager = ToolsManager()
        config = {"key": "normal_string"}
        
        result = manager._resolve_env_vars(config)
        
        assert result["key"] == "normal_string"

    @pytest.mark.asyncio
    async def test_get_tools_empty(self):
        """Test get_tools with no clients"""
        manager = ToolsManager()
        
        tools = await manager.get_tools()
        
        assert tools == []

    @pytest.mark.asyncio
    async def test_get_tools_single_client(self):
        """Test get_tools with one client"""
        manager = ToolsManager()
        mock_client = AsyncMock()
        mock_client.get_tools.return_value = [Mock(name="tool1")]
        manager._clients = [mock_client]
        
        tools = await manager.get_tools()
        
        assert len(tools) == 1
        assert tools[0].name == "tool1"

    @pytest.mark.asyncio
    async def test_get_tools_multiple_clients(self):
        """Test get_tools with multiple clients"""
        manager = ToolsManager()
        mock_client1 = AsyncMock()
        mock_client1.get_tools.return_value = [Mock(name="tool1")]
        mock_client2 = AsyncMock()
        mock_client2.get_tools.return_value = [Mock(name="tool2")]
        manager._clients = [mock_client1, mock_client2]
        
        tools = await manager.get_tools()
        
        assert len(tools) == 2


class TestToolsIntegration:
    """Integration tests for tools module"""

    @pytest.mark.asyncio
    async def test_full_workflow(self, tmp_path):
        """Test complete tools workflow"""
        # Create a config file
        config_file = tmp_path / "test_config.json"
        config_file.write_text(json.dumps({
            "mcpServers": {}
        }))
        
        manager = ToolsManager()
        
        # Load config
        success = manager.load_tools_from_config(str(config_file))
        assert success is True
        
        # Get tools (should be empty since no real MCP servers)
        tools = await manager.get_tools()
        assert isinstance(tools, list)
