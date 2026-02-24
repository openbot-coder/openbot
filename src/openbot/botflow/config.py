"""BotFlow 配置模块"""
from typing import List
from pydantic import BaseModel, Field


class ChannelConfig(BaseModel):
    """通道配置"""
    name: str = ""
    enabled: bool = False
    params: dict = Field(default_factory=dict)


class BotFlowConfig(BaseModel):
    """BotFlow 配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "data/botflow.db"
    worker_count: int = 4
    queue_timeout: float = 30.0
    channels: List[ChannelConfig] = Field(default_factory=lambda: [
        ChannelConfig(name="websocket", enabled=True, params={"path": "/ws/chat"}),
        ChannelConfig(name="wechat", enabled=False, params={"path": "/wechat", "token": "", "app_id": "", "app_secret": ""}),
    ])
