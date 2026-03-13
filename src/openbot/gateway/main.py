"""
OpenBot Gateway - 启动入口

此文件仅用于直接运行:
    python -m openbot.gateway.main
    uvicorn openbot.gateway.main:app
"""

import os
from openbot.gateway.botflow import BotFlow

# 创建 BotFlow 实例
_homespace = os.getenv("OPENBOT_HOMESPACE", "E:\\src\\openbot\\.openbot")
_bot_flow = BotFlow(homespace=_homespace)

# 获取 app (在 uvicorn 启动时会通过 lifespan 初始化)
app = _bot_flow.app


if __name__ == "__main__":
    _bot_flow.run(host="0.0.0.0", port=8000)
