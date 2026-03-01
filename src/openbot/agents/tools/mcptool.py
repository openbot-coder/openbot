import json
from math import e
import os
import io
import sys
from pathlib import Path
from itertools import chain
import asyncio
import logging
from typing import List, Tuple, Any, Optional, Dict, Callable
from datetime import datetime
import subprocess
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import (
    StdioConnection,
    SSEConnection,
    StreamableHttpConnection,
    WebsocketConnection,
)
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.tools import BaseTool, tool
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)

from vxutils import singleton
from openbot.agents.tools.build_in import BUILD_IN_TOOLS

CONNECTION_MAP = {
    "stdio": StdioConnection,
    "http": StreamableHttpConnection,
    "websocket": WebsocketConnection,
    "sse": SSEConnection,
}


@singleton
class McpToolsMiddleware(AgentMiddleware):
    """MCP工具中间件"""

    _mcp_client: MultiServerMCPClient = MultiServerMCPClient()

    def __init__(self, mcp_config_path: str = "mcp.json"):
        self._mcp_tools: Dict[str, List[BaseTool]] = {}
        self._server_status: Dict[str, dict] = {}
        self._mcp_configs = {}
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_interval = 10  # 60秒心跳间隔
        self._keepalive_timeout = 600  # 600秒保活
        self._check_event = asyncio.Event()

        try:
            self._mcp_config_path = mcp_config_path
            with open(self._mcp_config_path, "r") as f:
                mcp_configs = json.load(f)
        except Exception as e:
            logging.error(f"Error loading MCP config file {mcp_config_path}: {e}")

            # 即使配置文件不存在，也要保留传入的路径
            self._mcp_config_path = mcp_config_path
            return

        mcp_configs = self._resolve_env_vars(mcp_configs)
        self.add_mcp_server(mcp_configs)

        # 添加内置工具
        self._mcp_tools["builtin"] = BUILD_IN_TOOLS

        # 初始化管理工具
        self._init_management_tools()

    async def start(self):
        """启动MCP工具中间件"""
        if self._running:
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self.run_heartbeat())

    def _init_management_tools(self):
        """初始化管理工具（添加、删除、列出MCP服务器）"""

        @tool
        def add_mcp_server_tool(mcp_configs: dict) -> dict:
            """添加MCP服务器

            Args:
                mcp_configs: MCP配置字典，键为服务器名称，值为服务器配置

            Returns:
                操作结果，包含成功和失败的服务器信息
            """
            return self.add_mcp_server(mcp_configs)

        @tool
        def remove_mcp_server_tool(name: str) -> bool:
            """删除MCP服务器

            Args:
                name: 服务器名称

            Returns:
                是否成功删除
            """
            return self.remove_mcp_server(name)

        @tool
        def list_mcp_servers_tool() -> dict:
            """列出所有MCP服务器信息

            Returns:
                服务器信息字典，键为服务器名称，值包含工具列表和状态信息
            """
            return self.list_mcp_servers()

        @tool
        def save_mcp_config_tool() -> bool:
            """保存MCP配置到文件

            Returns:
                是否成功保存
            """
            return self._save_config()

        # 添加管理工具到 _mcp_tools
        self._mcp_tools["management"] = [
            add_mcp_server_tool,
            remove_mcp_server_tool,
            list_mcp_servers_tool,
            save_mcp_config_tool,
        ]

    @property
    def tools(self) -> List[BaseTool]:
        """Middleware 注册的工具 - LangChain 会自动收集这些工具"""
        return list(chain(*self._mcp_tools.values()))

    @property
    def config_path(self) -> str:
        """获取MCP配置文件路径"""
        return self._mcp_config_path

    def _stop_heartbeat(self):
        """停止心跳任务"""
        self._running = False
        if self._heartbeat_task:
            try:
                self._heartbeat_task.cancel()
            except Exception as e:
                logging.error(f"Error canceling heartbeat task: {e}")
            # 不在这里设置为None，让调用者决定是否需要设置

    async def do_heartbeat(self, server_name: str):
        """对单个服务器做心跳检查"""
        # 检查服务器健康状态
        try:
            # 检查服务器是否在连接列表中
            if server_name not in self._mcp_client.connections:
                logging.warning(
                    f"Server {server_name} not in connections, skipping heartbeat"
                )
                return

            tools = await self._mcp_client.get_tools(server_name=server_name)
            self._mcp_tools[server_name] = tools
            if server_name not in self._server_status:
                self._server_status[server_name] = {
                    "last_used": datetime.now(),
                    "expired_time": datetime.now().timestamp()
                    + self._keepalive_timeout,
                    "is_healthy": True,
                    "consecutive_failures": 0,
                }
            else:
                # 更新服务器状态
                self._server_status[server_name]["last_used"] = datetime.now()
                self._server_status[server_name]["expired_time"] = (
                    datetime.now().timestamp() + self._keepalive_timeout
                )
                self._server_status[server_name]["is_healthy"] = True
                self._server_status[server_name]["consecutive_failures"] = 0
        except Exception as e:
            # 只记录警告级别日志，避免过多的错误信息
            logging.warning(
                f"Server {server_name} health check failed: {type(e).__name__}"
            )
            self._mcp_client.connections.pop(server_name, None)
            consecutive_failures = 1

            if server_name in self._server_status:
                consecutive_failures += self._server_status[server_name][
                    "consecutive_failures"
                ]

            self._server_status[server_name] = {
                "last_used": datetime.now(),
                "expired_time": datetime.now().timestamp()
                + self._keepalive_timeout * consecutive_failures,
                "is_healthy": False,
                "consecutive_failures": consecutive_failures,
            }

    async def run_heartbeat(self):
        """通过大循环轮询服务器状态"""
        while self._running:
            tasks = []
            for server_name in list(self.mcp_client.connections.keys()):
                if server_name not in self._server_status or (
                    self._server_status[server_name]["expired_time"]
                    <= datetime.now().timestamp()
                ):
                    tasks.append(self.do_heartbeat(server_name))
            if tasks:
                await asyncio.gather(*tasks)

            try:
                # 使用 asyncio.sleep 代替 asyncio.wait 和 Event
                await asyncio.sleep(self._heartbeat_interval)
            except asyncio.CancelledError:
                # 任务被取消，退出循环
                break

    def add_mcp_server(self, mcp_configs: dict) -> dict:
        """添加MCP工具（异步版本）

        Args:
            mcp_configs: MCP配置字典，键为服务器名称，值为服务器配置。

        Returns:
            操作结果，包含成功和失败的服务器信息
        """
        mcp_configs = mcp_configs or {}
        if "mcpServers" in mcp_configs:
            mcp_configs = mcp_configs["mcpServers"]

        if not mcp_configs:
            return {"error": {}, "success": []}

        mcp_configs = self._resolve_env_vars(mcp_configs)

        result = {"error": {}, "success": []}
        for name, mcp_config in mcp_configs.items():
            if name in self.mcp_client.connections:
                result["error"][name] = "already exists"
                continue

            transport = mcp_config.get("transport", "stdio")
            if transport not in CONNECTION_MAP:
                result["error"][name] = f"Invalid transport {transport}"
                continue

            try:
                self._mcp_client.connections[name] = CONNECTION_MAP[transport](
                    **mcp_config
                )
                result["success"].append(name)
                self._mcp_configs[name] = mcp_config
            except Exception as e:
                result["error"][name] = str(e)
        # 触发心跳检查
        self._check_event.set()
        if result["success"]:
            self._save_config()
        return result

    @property
    def mcp_client(self) -> MultiServerMCPClient:
        """获取MCP客户端"""
        return self._mcp_client

    def wrap_tool_call(
        self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], Any]
    ) -> Any:
        """在工具调用后更新服务器状态"""
        result = handler(request)
        tool_name = (
            request.tool_call.get("name", "") if hasattr(request, "tool_call") else ""
        )
        for server_name in self._server_status:
            if tool_name in [t.name for t in self._mcp_tools.get(server_name, [])]:
                self._server_status[server_name] = {
                    "last_used": datetime.now(),
                    "is_healthy": True,
                    "consecutive_failures": 0,
                    "expired_time": datetime.now().timestamp()
                    + self._keepalive_timeout,
                }
                break
        return result

    async def awrap_tool_call(
        self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], Any]
    ) -> Any:
        """在工具调用后更新服务器状态（异步版本）"""
        result = await handler(request)
        tool_name = (
            request.tool_call.get("name", "") if hasattr(request, "tool_call") else ""
        )
        for server_name in self._server_status:
            if tool_name in [t.name for t in self._mcp_tools.get(server_name, [])]:
                self._server_status[server_name] = {
                    "last_used": datetime.now(),
                    "is_healthy": True,
                    "consecutive_failures": 0,
                    "expired_time": datetime.now().timestamp()
                    + self._keepalive_timeout,
                }
                break
        return result

    def refresh_server(self, server_name: str) -> bool:
        """手动刷新指定服务器的工具"""
        if server_name not in self.mcp_client.connections:
            return False

        if server_name in self._server_status:
            self._server_status[server_name][
                "expired_time"
            ] = datetime.now().timestamp()
        self._check_event.set()
        return True

    def remove_mcp_server(self, name: str) -> bool:
        """删除MCP服务器

        Args:
            name: 服务器名称

        Returns:
            是否成功
        """

        try:
            if name in self._mcp_configs:
                del self._mcp_configs[name]
                self._save_config()

            if name in self.mcp_client.connections:
                del self.mcp_client.connections[name]

            if name in self._mcp_tools:
                del self._mcp_tools[name]

            if name in self._server_status:
                del self._server_status[name]

            logging.info(f"Successfully removed MCP server {name}")
            return True
        except Exception as e:
            logging.error(f"Error removing MCP server {name}: {e}")
            return False

    def list_mcp_servers(self) -> List[Dict[str, Any]]:
        """列出所有MCP服务器信息

        Returns:
            服务器信息列表，每个元素包含服务器名称、工具列表和状态信息
        """
        # result是一个列表
        result = []
        for server_name in self.mcp_client.connections.keys():
            # 确保服务器名称是字符串
            server_name = str(server_name)
            tools = self._mcp_tools.get(server_name, [])
            status = self._server_status.get(server_name, {})

            tool_dict = {}
            for t in tools:
                tool_dict[t.name] = t.description

            result.append(
                {
                    "server_name": server_name,
                    "tool_count": len(tools),
                    "is_healthy": status.get("is_healthy", True),
                    "last_used": status.get("last_used"),
                    "expired_time": status.get("expired_time"),
                    "tools": tool_dict,
                }
            )
        return result

    def _resolve_env_vars(self, config_dict: dict) -> dict:
        """解析配置中的环境变量引用"""
        result = {}
        for key, value in config_dict.items():
            if isinstance(value, dict):
                result[key] = self._resolve_env_vars(value)
            elif isinstance(value, list):
                result[key] = [
                    (
                        self._resolve_env_vars(item)
                        if isinstance(item, dict)
                        else self._resolve_env_var(item)
                    )
                    for item in value
                ]
            else:
                result[key] = self._resolve_env_var(value)
        return result

    def _resolve_env_var(self, value: Any) -> Any:
        """解析单个环境变量引用"""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.environ.get(env_var, value)
        return value

    def _save_config(self):
        """保存配置到 mcp.json 文件"""
        try:
            config = {"mcpServers": {}}
            for name, mcp_config in self._mcp_configs.items():
                config["mcpServers"][name] = mcp_config

            with open(self._mcp_config_path, "w") as f:
                json.dump(config, f, indent=4)
            logging.info(f"Successfully saved MCP config to {self._mcp_config_path}")
        except FileNotFoundError as e:
            logging.error(
                f"Config file path not found: {self._mcp_config_path}, error: {e}"
            )
        except PermissionError as e:
            logging.error(
                f"Permission denied when saving config: {self._mcp_config_path}, error: {e}"
            )
        except Exception as e:
            logging.error(f"Error saving MCP config: {type(e).__name__}: {e}")


async def init_mcp_middleware(mcp_config_path: str = "mcp.json") -> McpToolsMiddleware:
    """初始化MCP工具中间件"""
    mcp_tools_middleware = McpToolsMiddleware(mcp_config_path)
    await mcp_tools_middleware.start()
    return mcp_tools_middleware
