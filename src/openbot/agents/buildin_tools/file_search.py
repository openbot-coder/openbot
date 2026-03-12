# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long
"""文件搜索工具：grep（内容检索）与 glob（文件发现）。"""

import re
import os

from pathlib import Path
from typing import Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


from .file_io import _resolve_file_path

WORKING_DIR = Path(os.environ.get("OPENBOT_WORKING_DIR", "."))

# 跳过二进制文件/大文件
_BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".svg",
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".flac",
        ".wav",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".7z",
        ".rar",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".dat",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        ".pyc",
        ".pyo",
        ".class",
        ".o",
        ".a",
    },
)

_MAX_MATCHES = 200
_MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


def _is_text_file(path: Path) -> bool:
    """启发式判断：跳过已知二进制后缀与大文件。"""
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return False
    try:
        if path.stat().st_size > _MAX_FILE_SIZE:
            return False
    except OSError:
        return False
    return True


async def grep_search(  # pylint: disable=too-many-branches
    pattern: str,
    path: Optional[str] = None,
    is_regex: bool = False,
    case_sensitive: bool = True,
    context_lines: int = 0,
) -> ToolResponse:
    """按模式递归搜索文件内容。相对路径基于 WORKING_DIR 解析。
    输出格式：``path:line_number: content``。

    Args:
        pattern (`str`):
            搜索字符串（is_regex=True 时按正则处理）。
        path (`str`, optional):
            要搜索的文件或目录。默认 WORKING_DIR。
        is_regex (`bool`, optional):
            是否将 pattern 视为正则表达式。默认 False。
        case_sensitive (`bool`, optional):
            是否区分大小写。默认 True。
        context_lines (`int`, optional):
            每个匹配项前后显示的上下文行数（类似 grep -C）。
            默认 0。
    """
    if not pattern:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="错误：未提供搜索 `pattern`。",
                ),
            ],
        )

    search_root = Path(_resolve_file_path(path)) if path else WORKING_DIR

    if not search_root.exists():
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误：路径 {search_root} 不存在。",
                ),
            ],
        )

    # 编译正则
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        if is_regex:
            regex = re.compile(pattern, flags)
        else:
            regex = re.compile(re.escape(pattern), flags)
    except re.error as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误：无效正则表达式 — {e}",
                ),
            ],
        )

    matches: list[str] = []
    truncated = False

    # 收集待搜索文件
    single_file = search_root.is_file()
    if single_file:
        files = [search_root]
    else:
        files = sorted(
            f for f in search_root.rglob("*") if f.is_file() and _is_text_file(f)
        )

    for file_path in files:
        if truncated:
            break
        try:
            lines = file_path.read_text(
                encoding="utf-8",
                errors="ignore",
            ).splitlines()
        except OSError:
            continue

        for line_no, line in enumerate(lines, start=1):
            if regex.search(line):
                if len(matches) >= _MAX_MATCHES:
                    truncated = True
                    break

                # 上下文窗口
                start = max(0, line_no - 1 - context_lines)
                end = min(len(lines), line_no + context_lines)

                # 单文件搜索时显示文件名，而不是 '.'
                if single_file:
                    rel = file_path.name
                else:
                    rel = _relative_display(file_path, search_root)
                for ctx_idx in range(start, end):
                    prefix = ">" if ctx_idx == line_no - 1 else " "
                    matches.append(
                        f"{rel}:{ctx_idx + 1}:{prefix} {lines[ctx_idx]}",
                    )
                if context_lines > 0:
                    matches.append("---")

    if not matches:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"未找到匹配模式的结果：{pattern}",
                ),
            ],
        )

    result = "\n".join(matches)
    if truncated:
        result += f"\n\n（结果已截断，最多显示 {_MAX_MATCHES} 条匹配。）"

    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=result,
            ),
        ],
    )


async def glob_search(
    pattern: str,
    path: Optional[str] = None,
) -> ToolResponse:
    """查找匹配 glob 模式的文件（如 ``"*.py"``、``"**/*.json"``）。
    相对路径基于 WORKING_DIR 解析。

    Args:
        pattern (`str`):
            要匹配的 glob 模式。
        path (`str`, optional):
            搜索根目录。默认 WORKING_DIR。
    """
    if not pattern:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="错误：未提供 glob `pattern`。",
                ),
            ],
        )

    search_root = Path(_resolve_file_path(path)) if path else WORKING_DIR

    if not search_root.exists():
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误：路径 {search_root} 不存在。",
                ),
            ],
        )

    if not search_root.is_dir():
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误：路径 {search_root} 不是目录。",
                ),
            ],
        )

    try:
        results: list[str] = []
        truncated = False
        for entry in sorted(search_root.glob(pattern)):
            rel = _relative_display(entry, search_root)
            suffix = "/" if entry.is_dir() else ""
            results.append(f"{rel}{suffix}")
            if len(results) >= _MAX_MATCHES:
                truncated = True
                break

        if not results:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"没有文件匹配该模式：{pattern}",
                    ),
                ],
            )

        text = "\n".join(results)
        if truncated:
            text += f"\n\n（结果已截断，最多显示 {_MAX_MATCHES} 条记录。）"

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=text,
                ),
            ],
        )
    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误：Glob 搜索失败\n{e}",
                ),
            ],
        )


def _relative_display(target: Path, root: Path) -> str:
    """尽量返回相对路径字符串，否则返回绝对路径。"""
    try:
        return str(target.relative_to(root))
    except ValueError:
        return str(target)
