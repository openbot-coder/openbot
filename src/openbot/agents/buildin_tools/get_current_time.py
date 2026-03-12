# -*- coding: utf-8 -*-
"""返回当前本地时间（含时区信息）的工具。"""

from datetime import datetime, timezone

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


async def get_current_time() -> ToolResponse:
    """获取带时区信息的当前系统时间。

    以可读格式返回本地时间，包含时区名称和 UTC 偏移量。
    适用于依赖时间上下文的任务，例如定时调度。

    Returns:
        `ToolResponse`:
            当前本地时间字符串，
            例如 "2026-02-13 19:30:45 CST (UTC+0800)"。
    """
    try:
        now = datetime.now().astimezone()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    except Exception:
        time_str = datetime.now(timezone.utc).isoformat() + " (UTC)"

    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=time_str,
            ),
        ],
    )
