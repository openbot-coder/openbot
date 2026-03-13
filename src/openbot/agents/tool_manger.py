"""toolkit manager"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from agentscope.tool import Toolkit
from agentscope.mcp import (
    HttpStatefulClient,
    HttpStatelessClient,
    StdIOStatefulClient,
)
import asyncio
from openbot.agents.buildin_tools import (
    execute_python_code,
    execute_shell_command,
    read_file,
    write_file,
    edit_file,
    append_file,
    grep_search,
    glob_search,
    send_file_to_user,
    get_current_time,
    SQLiteTool,
)


class ToolKitManager:
    def __init__(self):
        self._toolkit = Toolkit()
        self._registered_skill_dirs: List[str] = []

    @property
    def toolkit(self) -> Toolkit:
        """获取工具包"""
        return self._toolkit

    def register_buildin_tools(self) -> Toolkit:
        """构建内建工具包"""

        self._toolkit.register_tool_function(execute_python_code)
        self._toolkit.register_tool_function(execute_shell_command)
        self._toolkit.register_tool_function(read_file)
        self._toolkit.register_tool_function(write_file)
        self._toolkit.register_tool_function(edit_file)
        self._toolkit.register_tool_function(append_file)
        self._toolkit.register_tool_function(grep_search)
        self._toolkit.register_tool_function(glob_search)
        self._toolkit.register_tool_function(send_file_to_user)
        self._toolkit.register_tool_function(get_current_time)
        self._toolkit.register_tool_function(self._toolkit.reset_equipped_tools)
        return self._toolkit

    def register_db_tools(self) -> Toolkit:
        """注册数据库工具包"""
        db_tool = SQLiteTool()
        self._toolkit.create_tool_group(
            group_name="database",
            description="数据库工具包",
            active=False,
            notes="""
            数据库工具包，用于执行数据库操作。
            1、连接数据库：使用connect方法连接到数据库。
            2、list_tables: 列出数据库中的所有表。
            3、get_table_info: 获取指定表的结构信息。
            4、execute_sql: 执行SQL语句。
            5、close: 关闭数据库连接。
            """,
        )

        self._toolkit.register_tool_function(db_tool.connect, group_name="database")
        self._toolkit.register_tool_function(db_tool.close, group_name="database")
        self._toolkit.register_tool_function(db_tool.list_tables, group_name="database")
        self._toolkit.register_tool_function(
            db_tool.get_table_info, group_name="database"
        )
        self._toolkit.register_tool_function(db_tool.execute_sql, group_name="database")
        return self._toolkit

    async def register_mcp_tools(self, mcp_config: dict) -> Toolkit:
        """注册MCP工具包"""
        if "mcpServers" not in mcp_config:
            return self._toolkit

        mcp_servers = mcp_config["mcpServers"]

        # 支持 dict (server_name: config) 或 list [config, ...]
        if not mcp_servers:
            logging.warning("No MCP servers found in config.")
            return self._toolkit

        tasks = []

        if isinstance(mcp_servers, dict):
            for name, config in mcp_servers.items():
                tasks.append(self._register_single_mcp(name, config))
        elif isinstance(mcp_servers, list):
            for config in mcp_servers:
                name = config.get("name")
                if not name:
                    logging.warning("MCP server config missing 'name', skipping.")
                    continue
                tasks.append(self._register_single_mcp(name, config))

        if tasks:
            await asyncio.gather(*tasks)
        return self._toolkit

    async def _register_single_mcp(self, name: str, config: dict) -> None:
        """注册单个 MCP 服务"""
        client = None
        try:
            if "url" in config:
                # HTTP 类型的 MCP 服务
                stateful = config.get("stateful", True)
                client_kwargs = {
                    k: v
                    for k, v in config.items()
                    if k
                    not in [
                        "url",
                        "headers",
                        "timeout",
                        "sse_read_timeout",
                        "transport",
                        "stateful",
                    ]
                }

                if stateful:
                    client = HttpStatefulClient(
                        name=name,
                        url=config["url"],
                        transport=config.get("transport", "sse"),
                        headers=config.get("headers", None),
                        timeout=config.get("timeout", 30),
                        sse_read_timeout=config.get("sse_read_timeout", 60 * 5),
                        ** client_kwargs,
                    )
                    await client.connect()
                else:
                    client = HttpStatelessClient(
                        name=name,
                        url=config["url"],
                        transport=config.get("transport", "sse"),
                        headers=config.get("headers", None),
                        timeout=config.get("timeout", 30),
                        sse_read_timeout=config.get("sse_read_timeout", 60 * 5),
                        ** client_kwargs,
                    )
            elif "command" in config:
                # StdIO 类型的 MCP 服务 (AgentScope 中目前只有有状态客户端)
                client_kwargs = {
                    k: v
                    for k, v in config.items()
                    if k
                    not in [
                        "command",
                        "args",
                        "env",
                        "cwd",
                        "encoding",
                        "encoding_error_handler",
                    ]
                }
                client = StdIOStatefulClient(
                    name=name,
                    command=config["command"],
                    args=config.get("args", []),
                    env=config.get("env", None),
                    cwd=config.get("cwd", None),
                    encoding=config.get("encoding", "utf-8"),
                    encoding_error_handler=config.get(
                        "encoding_error_handler", "strict"
                    ),
                    **client_kwargs,
                )
                await client.connect()

            if client:
                list_tools = client.list_tools()
                if list_tools:
                    description = (
                        f"MCP 服务 {name}，提供以下工具：{', '.join(list_tools)}"
                    )
                    self._toolkit.create_tool_group(
                        group_name=name, description=description, active=True
                    )
                    await self._toolkit.register_mcp_client(client, group_name=name)
                logging.info(f"Successfully registered MCP client: {name}")
            else:
                logging.warning(f"Unsupported MCP configuration for {name}: {config}")

        except Exception as e:
            logging.error(f"Failed to register MCP client {name}: {e}")

    async def register_skill_dir(self, skill_dir: str) -> None:
        """注册技能目录"""
        skill_dir = Path(skill_dir)
        if skill_dir.exists() and skill_dir.is_dir():
            for sub_dir in skill_dir.iterdir():
                if sub_dir.name.startswith(".") or sub_dir.name.startswith("_"):
                    continue

                if (
                    sub_dir.is_dir()
                    and str(sub_dir.absolute()) not in self._registered_skill_dirs
                ):
                    try:
                        self._toolkit.register_agent_skill(sub_dir)
                        self._registered_skill_dirs.append(str(sub_dir.absolute()))
                        logging.info(
                            f"Successfully registered skill directory: {sub_dir}"
                        )
                    except Exception as e:
                        logging.error(
                            f"Failed to register skill directory {sub_dir}: {e}"
                        )
        else:
            logging.error(
                f"Skill directory {skill_dir} does not exist or is not a directory."
            )
