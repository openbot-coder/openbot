"""BotFlow 数据库模块 - 使用 aiosqlite"""

import aiosqlite
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from enum import StrEnum


class ContentType(StrEnum):
    TEXT = "text"
    VIDEO = "video"
    IMAGE = "image"
    FILE = "file"
    LINK = "link"


class ChatMessage(BaseModel):
    """消息模型"""

    channel_id: str = Field(default="", description="渠道 ID")
    msg_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="消息 ID"
    )
    content: str = Field(default="", description="消息内容")
    content_type: ContentType = Field(
        default=ContentType.TEXT, description="消息内容类型"
    )
    role: Literal["user", "bot", "system"] = Field(
        default="user", description="消息角色"
    )
    metadata: dict = Field(default_factory=dict, description="消息元数据")
    input_tokens: int = Field(default=0, description="输入 token 数量")
    output_tokens: int = Field(default=0, description="输出 token 数量")
    process_time_ms: int = Field(default=0, description="处理时间（毫秒）")
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="创建时间"
    )


class DatabaseManager:
    """异步数据库管理器"""

    def __init__(self, db_path: str = "data/botflow.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """初始化数据库"""
        conn = await self._get_connection()
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                role TEXT NOT NULL,
                content_type TEXT DEFAULT 'text',
                channel_id TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                process_time_ms INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        await conn.commit()

    async def _get_connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            self._connection = await aiosqlite.connect(str(self.db_path))
            # Enable row factory to return rows as dictionaries
            self._connection.row_factory = aiosqlite.Row
        return self._connection

    async def save_message(self, message: ChatMessage) -> bool:
        """保存消息"""
        conn = await self._get_connection()
        await conn.execute(
            """
            INSERT INTO messages (id, content, role, content_type, channel_id, input_tokens, output_tokens, process_time_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                message.msg_id,
                message.content,
                message.role,
                message.content_type.value,
                message.channel_id,
                message.input_tokens,
                message.output_tokens,
                message.process_time_ms,
                message.created_at,
            ),
        )
        await conn.commit()
        return True

    async def get_messages(self, limit: int = 100) -> List[ChatMessage]:
        """获取消息列表"""
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            # Convert rows to ChatMessage objects, mapping 'id' to 'msg_id'
            messages = []
            for row in rows:
                row_dict = dict(row)
                # Map database column 'id' to ChatMessage field 'msg_id'
                if "id" in row_dict:
                    row_dict["msg_id"] = row_dict.pop("id")
                messages.append(ChatMessage(**row_dict))
            return messages
