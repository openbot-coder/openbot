# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


WORKING_DIR = Path(os.environ.get("OPENBOT_WORKING_DIR", "workspace"))


def _resolve_file_path(file_path: str) -> str:
    """解析文件路径：
    - 如果是绝对路径，则保持不变。
    - 如果是相对路径，则基于 WORKING_DIR 解析。

    ⚠️ 安全警告：
    此函数目前允许访问绝对路径，这可能存在安全风险（路径遍历）。
    建议在生产环境中限制只能访问 WORKING_DIR 及其子目录。

    Args:
        file_path: 输入的文件路径（绝对或相对）。

    Returns:
        解析后的绝对文件路径字符串。
    """
    path = Path(file_path)
    if path.is_absolute():
        return str(path)
    else:
        return str(WORKING_DIR / file_path)


async def read_file(  # pylint: disable=too-many-return-statements
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> ToolResponse:
    """读取文件内容。相对路径将基于 WORKING_DIR 解析。

    使用 start_line/end_line 可以读取特定行范围（输出将包含行号）。
    省略这两个参数则读取整个文件。

    Args:
        file_path (`str`):
            文件路径。
        start_line (`int`, 可选):
            起始行号（从 1 开始，包含）。
        end_line (`int`, 可选):
            结束行号（从 1 开始，包含）。
    """

    file_path = _resolve_file_path(file_path)

    if not os.path.exists(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: 文件 {file_path} 不存在。",
                ),
            ],
        )

    if not os.path.isfile(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: 路径 {file_path} 不是一个文件。",
                ),
            ],
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        range_requested = start_line is not None or end_line is not None

        if range_requested:
            total = len(all_lines)
            s = max(1, start_line if start_line is not None else 1)
            e = min(total, end_line if end_line is not None else total)

            if s > total:
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=(
                                f"错误: start_line {s} 超过了文件长度 "
                                f"({total} 行) 在 {file_path} 中。"
                            ),
                        ),
                    ],
                )

            if s > e:
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=(
                                f"错误: start_line ({s}) 大于 "
                                f"end_line ({e}) 在 {file_path} 中。"
                            ),
                        ),
                    ],
                )

            selected = all_lines[s - 1 : e]
            content = "".join(selected)
            header = f"{file_path}  (行 {s}-{e} 共 {total} 行)\n"
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=header + content,
                    ),
                ],
            )
        else:
            content = "".join(all_lines)
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=content,
                    ),
                ],
            )

    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: 读取文件失败，原因: \n{e}",
                ),
            ],
        )


async def write_file(
    file_path: str,
    content: str,
) -> ToolResponse:
    """创建或覆盖文件。相对路径将基于 WORKING_DIR 解析。

    Args:
        file_path (`str`):
            文件路径。
        content (`str`):
            要写入的内容。
    """

    if not file_path:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="错误: 未提供 `file_path`。",
                ),
            ],
        )

    file_path = _resolve_file_path(file_path)

    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"写入了 {len(content)} 字节到 {file_path}。",
                ),
            ],
        )
    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: 写入文件失败，原因: \n{e}",
                ),
            ],
        )


async def edit_file(
    file_path: str,
    old_text: str,
    new_text: str,
) -> ToolResponse:
    """在文件中查找并替换文本。所有出现的 old_text 都将被替换为 new_text。
    相对路径将基于 WORKING_DIR 解析。

    Args:
        file_path (`str`):
            文件路径。
        old_text (`str`):
            要查找的确切文本。
        new_text (`str`):
            替换文本。
    """

    response = await read_file(file_path=file_path)
    if response.content and len(response.content) > 0:
        error_text = response.content[0].get("text", "")
        if error_text.startswith("错误:"):
            return response
    if not response.content or len(response.content) == 0:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: 读取文件 {file_path} 失败。",
                ),
            ],
        )

    content = response.content[0].get("text", "")
    if old_text not in content:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: 在 {file_path} 中未找到要替换的文本。",
                ),
            ],
        )

    new_content = content.replace(old_text, new_text)
    write_response = await write_file(file_path=file_path, content=new_content)

    if write_response.content and len(write_response.content) > 0:
        write_text = write_response.content[0].get("text", "")
        if write_text.startswith("错误:"):
            return write_response

    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=f"成功替换了 {file_path} 中的文本。",
            ),
        ],
    )


async def append_file(
    file_path: str,
    content: str,
) -> ToolResponse:
    """将内容追加到文件末尾。相对路径将基于 WORKING_DIR 解析。

    Args:
        file_path (`str`):
            文件路径。
        content (`str`):
            要追加的内容。
    """

    if not file_path:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="错误: 未提供 `file_path`。",
                ),
            ],
        )

    file_path = _resolve_file_path(file_path)

    try:
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(content)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"追加了 {len(content)} 字节到 {file_path}。",
                ),
            ],
        )
    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: 追加文件失败，原因: \n{e}",
                ),
            ],
        )


async def remove_file(
    file_path: str,
) -> ToolResponse:
    """将文件移动到 .trash 目录而不是永久删除它。
    相对路径将基于 WORKING_DIR 解析。

    Args:
        file_path (`str`):
            要移除的文件路径。
    """
    if not file_path:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="错误: 未提供 `file_path`。",
                ),
            ],
        )

    file_path_obj = Path(_resolve_file_path(file_path))

    if not file_path_obj.exists():
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: 文件 {file_path} 不存在。",
                ),
            ],
        )

    if not file_path_obj.is_file():
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: 路径 {file_path} 不是一个文件。",
                ),
            ],
        )

    trash_dir = WORKING_DIR / ".trash"
    trash_dir.mkdir(parents=True, exist_ok=True)

    # 在垃圾桶中生成唯一文件名以避免冲突
    timestamp = int(time.time())
    trash_filename = f"{file_path_obj.name}.{timestamp}"
    trash_path = trash_dir / trash_filename

    try:
        shutil.move(str(file_path_obj), str(trash_path))
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"已将 {file_path} 移动到回收站 {trash_path}。",
                ),
            ],
        )
    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误: 移除文件失败，原因: \n{e}",
                ),
            ],
        )
