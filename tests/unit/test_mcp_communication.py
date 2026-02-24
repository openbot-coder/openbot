import asyncio
import json
import tempfile
import os
from openbot.agents.tools import McpManager, LangChainMCPToolManager
from openbot.agents.tools.core import McpConfig, McpServerConfig


class MockMultiServerMCPClient:
    """模拟MultiServerMCPClient"""

    def __init__(self, servers):
        self.servers = servers
        self.tools = [
            {
                "name": "echo",
                "description": "Echo back the input",
                "parameters": {
                    "text": {"type": "string", "description": "Text to echo"}
                },
            }
        ]

    async def get_tools(self):
        """模拟获取工具列表"""
        return self.tools

    async def invoke(self, tool_name, **kwargs):
        """模拟调用工具"""
        if tool_name == "echo":
            return {"result": kwargs.get("text", "")}
        return {"error": "Tool not found"}


async def test_mcp_communication():
    """测试MCP服务器通信"""
    print("=== Testing MCP Server Communication ===")

    # 创建临时配置文件
    config_data = {
        "servers": [
            {"name": "default", "url": "http://localhost:8000", "enabled": True}
        ],
        "default_server": "default",
        "retry_attempts": 3,
        "retry_delay": 1,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_config_path = f.name

    try:
        # 创建MCP管理器
        print("1. Creating MCP manager...")
        manager = McpManager(temp_config_path)
        print("✓ MCP manager created successfully")

        # 模拟客户端
        print("2. Creating mock MCP client...")
        mock_client = MockMultiServerMCPClient(config_data["servers"])
        manager.client = mock_client
        print("✓ Mock MCP client created successfully")

        # 测试获取工具
        print("3. Testing get_tools...")
        tools = await manager.get_tools()
        print(f"✓ Got {len(tools)} tools")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")

        # 测试调用工具
        print("4. Testing invoke tool...")
        result = await manager.invoke("echo", text="Hello MCP!")
        print(f"✓ Tool invocation result: {result}")

        # 测试LangChainMCPToolManager
        print("5. Testing LangChainMCPToolManager...")
        tool_manager = LangChainMCPToolManager(temp_config_path)
        print("✓ LangChainMCPToolManager created successfully")

        # 测试获取工具列表
        print("6. Testing get_tools from LangChainMCPToolManager...")
        # 这里我们需要模拟内部的MCP管理器
        tool_manager.mcp_manager.client = mock_client
        mcp_tools = tool_manager.get_tools()
        print(f"✓ Got {len(mcp_tools)} MCP tools")

        print("\n🎉 All MCP communication tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ MCP communication test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if os.path.exists(temp_config_path):
            os.unlink(temp_config_path)


async def main():
    """主函数"""
    await test_mcp_communication()


if __name__ == "__main__":
    asyncio.run(main())
