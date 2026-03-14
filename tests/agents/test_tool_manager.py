import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from openbot.agents.tool_manger import ToolKitManager


class TestToolKitManager:
    @pytest.fixture
    def tool_manager(self):
        return ToolKitManager()

    def test_init(self, tool_manager):
        assert tool_manager._toolkit is not None
        assert tool_manager._registered_skill_dirs == []
        assert isinstance(tool_manager.toolkit, MagicMock) or hasattr(tool_manager.toolkit, "register_tool_function")

    def test_register_buildin_tools(self, tool_manager):
        # Mock the register_tool_function method
        tool_manager._toolkit.register_tool_function = MagicMock()
        tool_manager._toolkit.reset_equipped_tools = MagicMock()

        toolkit = tool_manager.register_buildin_tools()

        # Check that all buildin tools are registered
        assert tool_manager._toolkit.register_tool_function.call_count == 12
        expected_tools = [
            "execute_python_code",
            "execute_shell_command",
            "read_file",
            "write_file",
            "edit_file",
            "append_file",
            "grep_search",
            "glob_search",
            "send_file_to_user",
            "get_current_time",
            "reset_equipped_tools"
        ]
        for tool in expected_tools:
            tool_manager._toolkit.register_tool_function.assert_any_call(
                pytest.helpers.any_instance_of(object)  # Just check it's called with some function
            )

        assert toolkit == tool_manager._toolkit

    def test_register_db_tools(self, tool_manager):
        # Mock the required methods
        tool_manager._toolkit.create_tool_group = MagicMock()
        tool_manager._toolkit.register_tool_function = MagicMock()

        toolkit = tool_manager.register_db_tools()

        # Check that database group is created
        tool_manager._toolkit.create_tool_group.assert_called_once_with(
            group_name="database",
            description="数据库工具包",
            active=False,
            notes=pytest.helpers.any_instance_of(str)
        )

        # Check that 5 db tools are registered
        assert tool_manager._toolkit.register_tool_function.call_count == 5
        expected_db_methods = ["connect", "close", "list_tables", "get_table_info", "execute_sql"]
        for method in expected_db_methods:
            tool_manager._toolkit.register_tool_function.assert_any_call(
                pytest.helpers.any_instance_of(object),
                group_name="database"
            )

        assert toolkit == tool_manager._toolkit

    @pytest.mark.asyncio
    async def test_register_mcp_tools_empty_config(self, tool_manager):
        mcp_config = {}
        toolkit = await tool_manager.register_mcp_tools(mcp_config)
        assert toolkit == tool_manager._toolkit

    @pytest.mark.asyncio
    async def test_register_mcp_tools_no_servers(self, tool_manager):
        mcp_config = {"mcpServers": {}}
        toolkit = await tool_manager.register_mcp_tools(mcp_config)
        assert toolkit == tool_manager._toolkit

    @pytest.mark.asyncio
    async def test_register_mcp_tools_dict_config(self, tool_manager):
        mcp_config = {
            "mcpServers": {
                "test-server": {
                    "url": "http://localhost:8000/mcp",
                    "stateful": True,
                    "api_key": "test-key"
                }
            }
        }

        # Mock the MCP client
        mock_client = AsyncMock()
        mock_client.list_tools.return_value = ["tool1", "tool2"]
        
        with patch("openbot.agents.tool_manger.HttpStatefulClient", return_value=mock_client) as mock_client_cls:
            with patch.object(tool_manager._toolkit, "create_tool_group") as mock_create_group:
                with patch.object(tool_manager._toolkit, "register_mcp_client") as mock_register:
                    toolkit = await tool_manager.register_mcp_tools(mcp_config)

                    # Check client is created
                    mock_client_cls.assert_called_once()
                    args = mock_client_cls.call_args.kwargs
                    assert args["name"] == "test-server"
                    assert args["url"] == "http://localhost:8000/mcp"
                    assert args["api_key"] == "test-key"
                    
                    # Check connect is called
                    mock_client.connect.assert_awaited_once()
                    
                    # Check tools are listed
                    mock_client.list_tools.assert_called_once()
                    
                    # Check group is created
                    mock_create_group.assert_called_once_with(
                        group_name="test-server",
                        description="MCP 服务 test-server，提供以下工具：tool1, tool2",
                        active=True
                    )
                    
                    # Check client is registered
                    mock_register.assert_awaited_once_with(mock_client, group_name="test-server")

                    assert toolkit == tool_manager._toolkit

    @pytest.mark.asyncio
    async def test_register_mcp_tools_list_config(self, tool_manager):
        mcp_config = {
            "mcpServers": [
                {
                    "name": "server1",
                    "url": "http://localhost:8000/mcp",
                    "stateful": False
                },
                {
                    "name": "server2",
                    "command": "mcp-server",
                    "args": ["--config", "config.json"]
                }
            ]
        }

        with patch("openbot.agents.tool_manger.HttpStatelessClient") as mock_http_client:
            with patch("openbot.agents.tool_manger.StdIOStatefulClient") as mock_stdio_client:
                mock_http_instance = AsyncMock()
                mock_http_instance.list_tools.return_value = ["http_tool"]
                mock_http_client.return_value = mock_http_instance
                
                mock_stdio_instance = AsyncMock()
                mock_stdio_instance.list_tools.return_value = ["stdio_tool"]
                mock_stdio_client.return_value = mock_stdio_instance
                
                with patch.object(tool_manager._toolkit, "create_tool_group"):
                    with patch.object(tool_manager._toolkit, "register_mcp_client"):
                        await tool_manager.register_mcp_tools(mcp_config)

                        # Check both clients are created
                        mock_http_client.assert_called_once()
                        mock_stdio_client.assert_called_once()
                        
                        # Check both connect called
                        mock_http_instance.connect.assert_awaited_once()
                        mock_stdio_instance.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_mcp_tools_missing_name(self, tool_manager, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        
        mcp_config = {
            "mcpServers": [
                {
                    "url": "http://localhost:8000/mcp",
                    # Missing name
                }
            ]
        }

        await tool_manager.register_mcp_tools(mcp_config)
        
        # Check warning is logged
        assert "MCP server config missing 'name', skipping." in caplog.text

    @pytest.mark.asyncio
    async def test_register_mcp_tools_unsupported_config(self, tool_manager, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        
        mcp_config = {
            "mcpServers": {
                "test-server": {
                    "invalid_key": "value"
                }
            }
        }

        await tool_manager.register_mcp_tools(mcp_config)
        
        assert "Unsupported MCP configuration for test-server" in caplog.text

    @pytest.mark.asyncio
    async def test_register_mcp_tools_exception_handling(self, tool_manager, caplog):
        import logging
        caplog.set_level(logging.ERROR)
        
        mcp_config = {
            "mcpServers": {
                "test-server": {
                    "url": "http://localhost:8000/mcp"
                }
            }
        }

        with patch("openbot.agents.tool_manger.HttpStatefulClient", side_effect=Exception("Connection error")):
            await tool_manager.register_mcp_tools(mcp_config)
            
            assert "Failed to register MCP client test-server: Connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_register_skill_dir_not_exists(self, tool_manager, caplog):
        import logging
        caplog.set_level(logging.ERROR)
        
        non_existent_dir = "/non/existent/skill/dir"
        await tool_manager.register_skill_dir(non_existent_dir)
        
        assert f"Skill directory {non_existent_dir} does not exist or is not a directory." in caplog.text

    @pytest.mark.asyncio
    async def test_register_skill_dir_success(self, tool_manager, tmp_path, caplog):
        import logging
        caplog.set_level(logging.INFO)
        
        # Create test skill directory structure
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        
        # Create a skill subdirectory
        test_skill = skill_dir / "test_skill"
        test_skill.mkdir()
        
        # Create hidden directory that should be skipped
        hidden_skill = skill_dir / ".hidden_skill"
        hidden_skill.mkdir()
        
        # Mock register_agent_skill
        tool_manager._toolkit.register_agent_skill = MagicMock()
        
        await tool_manager.register_skill_dir(str(skill_dir))
        
        # Check skill is registered
        tool_manager._toolkit.register_agent_skill.assert_called_once_with(test_skill)
        assert str(test_skill.absolute()) in tool_manager._registered_skill_dirs
        assert f"Successfully registered skill directory: {test_skill}" in caplog.text
        
        # Register again - should not duplicate
        tool_manager._toolkit.register_agent_skill.reset_mock()
        await tool_manager.register_skill_dir(str(skill_dir))
        tool_manager._toolkit.register_agent_skill.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_skill_dir_exception_handling(self, tool_manager, tmp_path, caplog):
        import logging
        caplog.set_level(logging.ERROR)
        
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        test_skill = skill_dir / "test_skill"
        test_skill.mkdir()
        
        # Mock register_agent_skill to raise exception
        tool_manager._toolkit.register_agent_skill = MagicMock(side_effect=Exception("Invalid skill"))
        
        await tool_manager.register_skill_dir(str(skill_dir))
        
        assert f"Failed to register skill directory {test_skill}: Invalid skill" in caplog.text
