# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long
"""Shell 命令工具。"""

import asyncio
import locale
import sys
from pathlib import Path
from typing import Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

WORKING_DIR = Path.home() / ".openbot"


# pylint: disable=too-many-branches
async def execute_shell_command(
    command: str,
    timeout: int = 60,
    cwd: Optional[Path] = None,
) -> ToolResponse:
    """执行给定的 Shell 命令，并在 <returncode></returncode>、
    <stdout></stdout> 和 <stderr></stderr> 标签中返回返回码、标准输出和错误信息。

    Args:
        command (`str`):
            要执行的 Shell 命令。
        timeout (`int`, 默认为 `60`):
            允许命令运行的最大时间（秒）。默认是 60 秒。
        cwd (`Optional[Path]`, 默认为 `None`):
            命令执行的工作目录。如果为 None，默认为 WORKING_DIR。

    Returns:
        `ToolResponse`:
            包含已执行命令的返回码、标准输出和标准错误的工具响应。
            如果发生超时，返回码将为 -1，stderr 将包含超时信息。
    """

    cmd = (command or "").strip()

    # 设置工作目录
    working_dir = cwd if cwd is not None else WORKING_DIR

    try:
        # ⚠️ 安全警告: 使用 shell=True 存在命令注入风险。
        # 请确保 command 来源可信或已过滤。
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            bufsize=0,
            cwd=str(working_dir),
        )

        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            stdout, stderr = await proc.communicate()
            # 获取系统默认编码，Windows 下通常是 gbk 或 cp936
            encoding = locale.getpreferredencoding(False) or "utf-8"
            stdout_str = stdout.decode(encoding, errors="replace").strip("\n")
            stderr_str = stderr.decode(encoding, errors="replace").strip("\n")
            returncode = proc.returncode

        except asyncio.TimeoutError:
            # 处理超时
            stderr_suffix = (
                f"⚠️ 超时错误: 命令执行超过了 {timeout} 秒的限制。"
                f"如果该命令需要更多时间完成，请考虑增加超时值。"
            )
            returncode = -1
            try:
                proc.terminate()
                # 等待优雅终止
                try:
                    await asyncio.wait_for(proc.wait(), timeout=1)
                except asyncio.TimeoutError:
                    # 如果优雅终止失败，强制杀死进程
                    proc.kill()
                    await proc.wait()

                stdout, stderr = await proc.communicate()
                encoding = locale.getpreferredencoding(False) or "utf-8"
                stdout_str = stdout.decode(encoding, errors="replace").strip(
                    "\n",
                )
                stderr_str = stderr.decode(encoding, errors="replace").strip(
                    "\n",
                )
                if stderr_str:
                    stderr_str += f"\n{stderr_suffix}"
                else:
                    stderr_str = stderr_suffix
            except ProcessLookupError:
                stdout_str = ""
                stderr_str = stderr_suffix

        # 以人类友好的方式格式化响应
        if returncode == 0:
            # 成功情况：仅显示输出
            if stdout_str:
                response_text = stdout_str
            else:
                response_text = "命令执行成功（无输出）。"
        else:
            # 错误情况：显示详细信息
            response_parts = [f"命令失败，退出码 {returncode}。"]
            if stdout_str:
                response_parts.append(f"\n[标准输出]\n{stdout_str}")
            if stderr_str:
                response_parts.append(f"\n[标准错误]\n{stderr_str}")
            response_text = "".join(response_parts)

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=response_text,
                ),
            ],
        )

    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: Shell 命令执行失败，原因: \n{e}",
                ),
            ],
        )


async def execute_python_code(
    code: str,
    timeout: int = 60,
    cwd: Optional[Path] = None,
) -> ToolResponse:
    """在子进程中执行 Python 代码。

    该函数将提供的 Python 代码包装在临时脚本中（通过 -c 参数），
    并使用当前的 Python 解释器执行它。它会捕获 stdout 和 stderr。

    Args:
        code (`str`):
            要执行的 Python 代码。
        timeout (`int`, 默认为 `60`):
            允许执行的最大时间（秒）。
        cwd (`Optional[Path]`, 默认为 `None`):
            执行的工作目录。如果为 None，默认为 WORKING_DIR。

    Returns:
        `ToolResponse`:
            包含执行结果（stdout/stderr）的工具响应。
    """
    if not code or not code.strip():
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="错误: 未提供 Python 代码。",
                )
            ]
        )

    # 使用与当前进程相同的 Python 解释器
    python_executable = sys.executable

    # 我们将使用 'python -c code' 通过 subprocess exec 执行（不使用 shell=True）以避免注入

    working_dir = cwd if cwd is not None else WORKING_DIR

    try:
        proc = await asyncio.create_subprocess_exec(
            python_executable,
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(working_dir),
        )

        try:
            # 带超时等待
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            # 解码输出
            encoding = locale.getpreferredencoding(False) or "utf-8"
            stdout_str = stdout.decode(encoding, errors="replace").strip()
            stderr_str = stderr.decode(encoding, errors="replace").strip()
            returncode = proc.returncode

        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"错误: Python 执行在 {timeout} 秒后超时。",
                    )
                ]
            )

        # 格式化响应
        response_parts = []
        if returncode == 0:
            if stdout_str:
                response_parts.append(stdout_str)
            else:
                response_parts.append("执行成功（无输出）。")
        else:
            response_parts.append(f"执行失败，退出码 {returncode}。")
            if stdout_str:
                response_parts.append(f"\n[标准输出]\n{stdout_str}")
            if stderr_str:
                response_parts.append(f"\n[标准错误]\n{stderr_str}")

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="\n".join(response_parts),
                )
            ]
        )

    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: Python 执行失败，原因: \n{e}",
                )
            ]
        )
