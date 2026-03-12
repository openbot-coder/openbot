# -*- coding: utf-8 -*-
"""桌面/屏幕截图工具。"""

import json
import os
import platform
import subprocess
import tempfile
import time

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


def _tool_error(msg: str) -> ToolResponse:
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=json.dumps(
                    {"ok": False, "error": msg},
                    ensure_ascii=False,
                    indent=2,
                ),
            ),
        ],
    )


def _tool_ok(path: str, message: str) -> ToolResponse:
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=json.dumps(
                    {
                        "ok": True,
                        "path": os.path.abspath(path),
                        "message": message,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            ),
        ],
    )


def _capture_mss(path: str) -> ToolResponse:
    """使用 mss 进行全屏截图（Windows、Linux、macOS）。"""
    try:
        import mss
    except ImportError:
        return _tool_error(
            "desktop_screenshot 依赖 'mss' 包。请执行: pip install mss",
        )
    try:
        with mss.mss() as sct:
            # mon=0: 合并所有显示器
            sct.shot(mon=0, output=path)
        if not os.path.isfile(path):
            return _tool_error("mss 报告成功，但未生成文件")
        return _tool_ok(path, f"Desktop screenshot saved to {path}")
    except Exception as e:
        return _tool_error(f"desktop_screenshot (mss) failed: {e!s}")


def _capture_macos_screencapture(
    path: str,
    capture_window: bool,
) -> ToolResponse:
    """macOS：screencapture（使用 -w 支持窗口选择）。"""
    cmd = ["screencapture", "-x", path]
    if capture_window:
        cmd.insert(-1, "-w")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or "未知错误"
            return _tool_error(f"screencapture failed: {stderr}")
        if not os.path.isfile(path):
            return _tool_error(
                "screencapture 报告成功，但未生成文件",
            )
        return _tool_ok(path, f"Desktop screenshot saved to {path}")
    except subprocess.TimeoutExpired:
        return _tool_error(
            "screencapture 超时（例如窗口选择被取消）",
        )
    except Exception as e:
        return _tool_error(f"desktop_screenshot failed: {e!s}")


async def desktop_screenshot(
    path: str = "",
    capture_window: bool = False,
) -> ToolResponse:
    """截取整个桌面（所有显示器）或单个窗口的截图。

    支持平台：Windows、Linux、macOS。全屏截图在所有平台均使用 mss。
    在 macOS 上，capture_window=True 会使用系统 screencapture 工具，
    让用户点击选择要截取的窗口。

    Args:
        path (`str`):
            截图保存路径（可选）。为空时保存到临时文件并返回该路径。
            建议使用 .png 后缀以输出 PNG。
        capture_window (`bool`):
            在 macOS 上为 True 时，可点击窗口仅截取该窗口。
            在 Windows/Linux 上仅支持全屏（该参数会被忽略）。

    Returns:
        `ToolResponse`:
            包含 "ok"、"path"（保存路径）以及可选 "message"/"error" 的 JSON。
    """
    path = (path or "").strip()
    if not path:
        path = os.path.join(
            tempfile.gettempdir(),
            f"desktop_screenshot_{int(time.time())}.png",
        )
    if not path.lower().endswith(".png"):
        path = path.rstrip("/\\") + ".png"

    system = platform.system()

    # macOS：可通过 screencapture -w 选择窗口
    if system == "Darwin" and capture_window:
        return _capture_macos_screencapture(path, capture_window=True)

    # 全平台（macOS/Linux/Windows）通过 mss 进行全屏截图
    return _capture_mss(path)
