try:
    from openbot.agents.tools import McpManager, LangChainMCPToolManager

    print("MCP modules imported successfully")
except Exception as e:
    print(f"Error importing MCP modules: {e}")
    import traceback

    traceback.print_exc()
