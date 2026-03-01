"""内置工具集合"""

import os
import io
import sys
from pathlib import Path
import logging
from typing import Tuple
from datetime import datetime
import subprocess
from deepagents.middleware import SubAgentMiddleware
from deepagents.middleware.skills import SkillsMiddleware

__all__ = [
    "BUILD_IN_TOOLS",
]


TRASH_DIR = Path(f"{os.environ.get('OPENBOT_WORKSPACE', '.')}/.openbot/.trash")
TRASH_DIR.mkdir(parents=True, exist_ok=True)

os.environ["OPENBOT_TRASH_DIR"] = str(TRASH_DIR.absolute())

CLEAN_BUILD_IN = {
    "print": print,
    "len": len,
    "range": range,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sum": sum,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "sorted": sorted,
    "reversed": reversed,
    "any": any,
    "all": all,
    "isinstance": isinstance,
    "type": type,
    "ord": ord,
    "chr": chr,
    "hex": hex,
    "oct": oct,
    "bin": bin,
    "divmod": divmod,
    "pow": pow,
    "input": input,
    "open": open,
}


def get_current_time() -> str:
    """获取当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def remove_file(file_path: str) -> Tuple[bool, str]:
    """删除文件"""
    if not TRASH_DIR.exists():
        TRASH_DIR.mkdir(parents=True, exist_ok=True)

    file_path = Path(file_path)
    if file_path.exists():
        file_path.rename(TRASH_DIR / file_path.name)
        return True, ""
    return False, f"File or directory {file_path} not found"


def python_script(script: str) -> str:
    """执行Python脚本

    Args:
        script: 要执行的Python脚本字符串。

    Notes:
        脚本中只能使用函数和变量：{clean_build_in}.

    Returns:
        脚本执行结果或错误信息。如果脚本有print输出，返回输出内容。

    """

    try:
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()
        try:
            # 使用受限的执行环境
            exec(script, {"__builtins__": CLEAN_BUILD_IN})
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        return output if output else None

    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


python_script.__doc__ = python_script.__doc__.format(
    clean_build_in=list(CLEAN_BUILD_IN.keys())
)


def shell_command(command: str, cwd: str = None) -> str:
    """执行shell命令

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


BUILD_IN_TOOLS = [
    get_current_time,
    remove_file,
    python_script,
    shell_command,
]
