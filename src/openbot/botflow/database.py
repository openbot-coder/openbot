"""BotFlow 数据库模块 - 使用 aiosqlite"""
import aiosqlite
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field


class Message(BaseModel):
    """消息模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    role: str = "user"  # user, assistant, system
    content_type: str = "text"  # text, image, file
    channel_id: str = ""  # channel identifier
    input_tokens: int = 0
    output_tokens: int = 0
    process_time_ms: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


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
        return self._connection
    
    async def save_message(self, message: Message) -> bool:
        """保存消息"""
        conn = await self._get_connection()
        await conn.execute("""
            INSERT INTO messages (id, content, role, content_type, channel_id, input_tokens, output_tokens, process_time_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (message.id, message.content, message.role, message.content_type, message.channel_id,
              message.input_tokens, message.output_tokens, message.process_time_ms, message.created_at))
        await conn.commit()
        return True
    
    async def get_messages(self, limit: int = 100) -> List[Message]:
        """获取消息列表"""
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [Message(**dict(row)) for row in rows]
