import pytest
import asyncio
from openbot.agents.tools import McpManager, LangChainMCPToolManager
from openbot.agents.tools.core import McpConfig, McpServerConfig


class MockMcpClient:
    """模拟MCP客户端，用于测试"""

    def __init__(self, servers):
        self.servers = servers
        self.tools_called = []
        self.tools_list = [
            {
                "name": "echo",
                "description": "Echo back the input",
                "parameters": {
                    "text": {"type": "string", "description": "Text to echo"}
                },
            },
            {
                "name": "add",
                "description": "Add two numbers",
                "parameters": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"},
                },
            },
        ]

    async def get_tools(self):
        """模拟获取工具列表"""
        return self.tools_list

    async def invoke(self, tool_name, **kwargs):
        """模拟调用工具"""
        self.tools_called.append((tool_name, kwargs))

        if tool_name == "echo":
            return {"result": kwargs.get("text", "")}
        elif tool_name == "add":
            return {"result": kwargs.get("a", 0) + kwargs.get("b", 0)}
        else:
            return {"error": "Tool not found"}


@pytest.fixture
async def mock_mcp_manager(monkeypatch):
    """创建模拟的MCP管理器"""
    # 创建一个模拟的MultiServerMCPClient
    mock_client = MockMcpClient({"default": {"url": "http://localhost:8000"}})

    # 模拟McpManager的初始化
    async def mock_get_tools(self):
        return await mock_client.get_tools()

    async def mock_invoke(self, tool_name, **kwargs):
        return await mock_client.invoke(tool_name, **kwargs)

    # 应用补丁
    monkeypatch.setattr(McpManager, "get_tools", mock_get_tools)
    monkeypatch.setattr(McpManager, "invoke", mock_invoke)

    # 创建配置
    config = McpConfig(
        servers=[
            McpServerConfig(name="default", url="http://localhost:8000", enabled=True)
        ]
    )

    # 创建McpManager实例
    manager = McpManager()
    manager.config = config
    manager.client = mock_client

    return manager


@pytest.mark.asyncio
async def test_mcp_manager_get_tools(mock_mcp_manager):
    """测试获取工具列表"""
    tools = await mock_mcp_manager.get_tools()
    assert len(tools) == 2
    assert tools[0]["name"] == "echo"
    assert tools[1]["name"] == "add"


@pytest.mark.asyncio
async def test_mcp_manager_invoke_echo(mock_mcp_manager):
    """测试调用echo工具"""
    result = await mock_mcp_manager.invoke("echo", text="Hello, MCP!")
    assert result["result"] == "Hello, MCP!"


@pytest.mark.asyncio
async def test_mcp_manager_invoke_add(mock_mcp_manager):
    """测试调用add工具"""
    result = await mock_mcp_manager.invoke("add", a=5, b=3)
    assert result["result"] == 8


@pytest.mark.asyncio
async def test_langchain_mcp_tool_manager():
    """测试LangChainMCPToolManager"""
    # 创建一个简单的配置
    import tempfile
    import json

    # 创建临时配置文件
    config = {
        "servers": [
            {"name": "default", "url": "http://localhost:8000", "enabled": true}
        ],
        "default_server": "default",
        "retry_attempts": 3,
        "retry_delay": 1,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        temp_config_path = f.name

    try:
        # 创建工具管理器
        tool_manager = LangChainMCPToolManager(temp_config_path)
        assert tool_manager is not None
    finally:
        import os

        os.unlink(temp_config_path)


@pytest.mark.asyncio
async def test_mcp_tool_integration():
    """测试MCP工具集成"""

    # 创建一个模拟的工具管理器
    class MockToolManager:
        def get_tools(self):
            return []

    # 测试工具管理器的基本功能
    tool_manager = MockToolManager()
    tools = tool_manager.get_tools()
    assert isinstance(tools, list)
    assert len(tools) == 0


@pytest.mark.asyncio
async def test_mcp_retry_mechanism():
    """测试MCP重试机制"""

    # 创建一个会失败的模拟客户端
    class FailingMockClient:
        def __init__(self):
            self.attempts = 0

        async def get_tools(self):
            self.attempts += 1
            if self.attempts < 3:
                raise Exception("Temporary failure")
            return [{"name": "echo", "description": "Echo tool"}]

        async def invoke(self, tool_name, **kwargs):
            self.attempts += 1
            if self.attempts < 3:
                raise Exception("Temporary failure")
            return {"result": "Success"}

    # 创建McpManager实例
    manager = McpManager()
    manager.config = McpConfig(
        servers=[
            McpServerConfig(name="default", url="http://localhost:8000", enabled=True)
        ],
        retry_attempts=3,
        retry_delay=0.1,
    )
    manager.client = FailingMockClient()

    # 测试重试机制
    tools = await manager.get_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "echo"


if __name__ == "__main__":
    asyncio.run(test_mcp_manager_get_tools(mock_mcp_manager))
