import json
import os
from pathlib import Path
from itertools import chain
import asyncio
import logging
from typing import List, Tuple
from datetime import datetime
import subprocess
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.tools import BaseTool


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


def run_bash_command(command: str, cwd: str = None) -> str:
    """执行 Bash 命令

    Args:
        command: 要执行的命令字符串
        cwd: 工作目录，默认为 None（使用当前目录）

    Returns:
        命令输出或错误信息
    """
    try:
        # 如果没有指定 cwd，尝试从环境变量获取工作目录
        if cwd is None:
            cwd = os.environ.get("OPENBOT_WORKSPACE", ".")

        # 使用 shell=True 时，直接传递 command 字符串，不要 split()
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            env=os.environ,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        output = result.stdout.strip() if result.stdout else ""
        if result.stderr:
            output += f"\n[stderr]: {result.stderr.strip()}"

        return output if output else "Command executed successfully (no output)"

    except subprocess.CalledProcessError as e:
        error_msg = f"Error: command failed with exit code {e.returncode}"
        if e.stdout:
            error_msg += f"\nstdout: {e.stdout.strip()}"
        if e.stderr:
            error_msg += f"\nstderr: {e.stderr.strip()}"
        return error_msg
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"
    finally:
        logging.info(f"Command executed: {command} (cwd: {cwd})")


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
        # tools = await client.get_tools()
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
