import asyncio
from openbot.agents.tools import McpManager, LangChainMCPToolManager


async def test_mcp_import():
    """测试MCP模块导入"""
    print("Testing MCP module import...")
    try:
        # 测试McpManager导入
        manager = McpManager()
        print("✓ McpManager imported successfully")

        # 测试LangChainMCPToolManager导入
        tool_manager = LangChainMCPToolManager()
        print("✓ LangChainMCPToolManager imported successfully")

        return True
    except Exception as e:
        print(f"✗ Error importing MCP modules: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("=== MCP Functionality Test ===")
    success = await test_mcp_import()

    if success:
        print("\n🎉 All MCP tests passed!")
    else:
        print("\n❌ Some MCP tests failed!")


if __name__ == "__main__":
    asyncio.run(main())
