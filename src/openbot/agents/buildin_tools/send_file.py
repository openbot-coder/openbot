# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long,too-many-return-statements
import os
import mimetypes

from agentscope.tool import ToolResponse
from agentscope.message import (
    TextBlock,
    ImageBlock,
    AudioBlock,
    VideoBlock,
    URLSource,
    Base64Source,
)

from typing import Union, Literal

try:
    from typing import Required, TypedDict
except ImportError:
    from typing_extensions import Required, TypedDict


class FileBlock(TypedDict, total=False):
    """The file block"""

    type: Required[Literal["file"]]
    source: Required[Union[URLSource, Base64Source]]
    filename: Required[str]


def _auto_as_type(mt: str) -> str:
    if mt.startswith("image/"):
        return "image"
    if mt.startswith("audio/"):
        return "audio"
    if mt.startswith("video/"):
        return "video"
    if mt.startswith("text/"):
        return "text"
    return "file"


async def send_file_to_user(
    file_path: str,
) -> ToolResponse:
    """将文件发送给用户。

    Args:
        file_path (`str`):
            要发送的文件路径。

    Returns:
        `ToolResponse`:
            包含文件或错误信息的工具响应。
    """

    if not os.path.exists(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误：文件 {file_path} 不存在。",
                ),
            ],
        )

    if not os.path.isfile(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误：路径 {file_path} 不是文件。",
                ),
            ],
        )

    # 检测 MIME 类型
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        # 未知类型默认使用 application/octet-stream
        mime_type = "application/octet-stream"
    as_type = _auto_as_type(mime_type)

    try:
        # 文本文件
        if as_type == "text":
            with open(file_path, "r", encoding="utf-8") as file:
                return ToolResponse(
                    content=[TextBlock(type="text", text=file.read())],
                )

        # 使用本地 file URL 而非 base64
        absolute_path = os.path.abspath(file_path)
        file_url = f"file://{absolute_path}"
        source = {"type": "url", "url": file_url}

        if as_type == "image":
            return ToolResponse(
                content=[
                    ImageBlock(type="image", source=source),
                    TextBlock(type="text", text="已成功发送文件"),
                ],
            )
        if as_type == "audio":
            return ToolResponse(
                content=[
                    AudioBlock(type="audio", source=source),
                    TextBlock(type="text", text="已成功发送文件"),
                ],
            )
        if as_type == "video":
            return ToolResponse(
                content=[
                    VideoBlock(type="video", source=source),
                    TextBlock(type="text", text="已成功发送文件"),
                ],
            )

        return ToolResponse(
            content=[
                FileBlock(
                    type="file",
                    source=source,
                    filename=os.path.basename(file_path),
                ),
                TextBlock(type="text", text="已成功发送文件"),
            ],
        )

    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误：发送文件失败\n{e}",
                ),
            ],
        )
