import json
import os
from pathlib import Path
from itertools import chain
import asyncio
import logging
from typing import List, Tuple, Dict
from datetime import datetime
import subprocess
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.tools import BaseTool
from langchain.chat_models import BaseChatModel


def get_current_time() -> str:
    """获取当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


RUBISHBIN = Path("./.trash")


def remove_file(file_path: str) -> Tuple[bool, str]:
    """删除文件"""
    if not RUBISHBIN.exists():
        RUBISHBIN.mkdir(parents=True)

    file_path = Path(file_path)
    if file_path.is_file() and file_path.exists():
        file_path.rename(RUBISHBIN / file_path.name)
        return True, ""
    elif file_path.is_dir() and file_path.exists():
        file_path.rename(RUBISHBIN / file_path.name)
        return True, ""
    return False, f"File or directory {file_path} not found"


def run_bash_command(command: str) -> str:
    """执行 Bash 命令"""
    try:
        result = subprocess.run(
            command.split(),
            shell=True,
            env=os.environ,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: command failed with exit code {e.returncode}: {e.output}"
    finally:
        logging.info(f"Command: {command} executed")


class ToolsManager:
    """工具管理类"""

    def __init__(self):
        self._mcp_configs: dict[str, dict] = {}
        self._clients: List[MultiServerMCPClient] = []

    def load_tools_from_config(self, config_path: str) -> Tuple[bool, List[BaseTool]]:
        """加载配置文件"""
        if not os.path.exists(config_path):
            logging.error(f"Config file {config_path} not found")
            return False, []

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
                config_dict = self._resolve_env_vars(config_dict)

            if "mcpServers" in config_dict:
                mcp_configs = config_dict["mcpServers"]
            else:
                mcp_configs = {}
        except json.JSONDecodeError as e:
            logging.error(f"❌️ Invalid JSON in config file: {e}")
            return False

        return self.load_tools_from_dict(mcp_configs)

    def load_tools_from_dict(self, mcp_configs: dict) -> bool:
        """从 JSON 字符串添加工具,返回是否成功

        例如:
        ```config = {
            "mcpServers": {
                "Excel": {
                "command": "npx",
                "args": [
                    "--yes",
                    "@negokaz/excel-mcp-server"
                ],
                "env": {
                    "EXCEL_MCP_PAGING_CELLS_LIMIT": "4000"
                }
            }
        }
        ```
        或者：
        ```config = {
            "Excel": {
                "transport": "stdio",
                "command": "npx",
                "args": [
                    "--yes",
                    "@negokaz/excel-mcp-server"
                ],
                "env": {
                    "EXCEL_MCP_PAGING_CELLS_LIMIT": "4000"
            }
        }
        ```

        """

        if "mcpServers" in mcp_configs:
            mcp_configs = mcp_configs["mcpServers"]

        new_mcp_configs = {}
        for server_name, server_config in mcp_configs.items():
            if "transport" not in server_config:
                server_config["transport"] = "stdio"

            if server_name not in self._mcp_configs:
                self._mcp_configs[server_name] = server_config
                new_mcp_configs[server_name] = server_config

        client = MultiServerMCPClient(new_mcp_configs)
        self._clients.append(client)
        #tools = await client.get_tools()
        return True

    def _resolve_env_vars(self, config_dict: dict) -> dict:
        """解析配置中的环境变量引用"""
        result = {}
        for key, value in config_dict.items():
            if isinstance(value, dict):
                result[key] = self._resolve_env_vars(value)
            elif isinstance(value, list):
                result[key] = [
                    self._resolve_env_vars(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif (
                isinstance(value, str)
                and value.startswith("${")
                and value.endswith("}")
            ):
                env_var = value[2:-1]
                result[key] = os.environ.get(env_var)
            else:
                result[key] = value
        return result

    async def get_tools(self) -> List[BaseTool]:
        """获取所有工具"""
        tools = await asyncio.gather(*[client.get_tools() for client in self._clients])
        tools = chain.from_iterable(tools)
        return list(tools)


if __name__ == "__main__":
    tools_manager = ToolsManager()
    tools_manager.load_tools_from_config("config/mcp.json")
    tools = asyncio.run(tools_manager.get_tools())
    for tool in tools:
        print(tool)
        print("=" * 20)

    print(len(tools))
