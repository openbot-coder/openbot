# BotFlow Implementation Plan (v2)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于 FastAPI 实现 BotFlow 框架，支持 WebSocket 和 WeChat 通道，内置基于触发时间的优先队列和定时任务

**Architecture:** 使用 FastAPI 作为核心框架。Channels 接收消息后放入优先队列，队列按触发时间（nearest fire time）排序，Worker 按时间顺序处理

**Tech Stack:** FastAPI, aiosqlite, aiohttp, uvicorn

**参考设计:** vxsched.py - 基于触发时间的优先队列实现

---

## 目录结构

```
src/openbot/
├── botflow/
│   ├── __init__.py          # 模块导出
│   ├── config.py            # 配置模型
│   ├── database.py         # 数据库 (aiosqlite)
│   ├── trigger.py          # 触发器 (参考 vxsched)
│   ├── event.py            # 事件模型 (参考 vxsched)
│   ├── scheduler.py        # 定时任务 (参考 vxsched)
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── base.py         # 通道基类
│   │   ├── websocket.py    # WebSocket 通道
│   │   └── wechat.py      # 微信公众号通道
│   └── main.py             # FastBotFlow 主应用
```

---

## Task 1: 配置模块

**Files:**
- Create: `src/openbot/botflow/config.py`

**Step 1: 创建配置模块**

```python
"""BotFlow 配置"""
from pydantic import BaseModel, Field
from typing import List


class ChannelConfig(BaseModel):
    """通道配置"""
    name: str = ""  # channel name: websocket, wechat, etc.
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
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/config.py
git commit -m "feat(botflow): add config module"
```

---

## Task 2: 数据库模块

**Files:**
- Create: `src/openbot/botflow/database.py`

**Step 1: 创建数据库模块**

```python
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
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/database.py
git commit -m "feat(botflow): add database module with aiosqlite"
```

---

## Task 3: 触发器模块 (参考 vxsched)

**Files:**
- Create: `src/openbot/botflow/trigger.py`

**Step 1: 创建触发器模块**

```python
"""BotFlow 触发器 - 基于 vxsched 设计"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Tuple
from pydantic import BaseModel, Field
from enum import Enum


class TriggerStatus(str, Enum):
    READY = "Ready"
    RUNNING = "Running"
    COMPLETED = "Completed"


class Trigger(BaseModel):
    """触发器基类"""
    trigger_dt: datetime = Field(default_factory=datetime.now)
    interval: float = Field(default=0.0)
    status: TriggerStatus = Field(default=TriggerStatus.READY)

    @abstractmethod
    def next(self) -> Optional[datetime]:
        """获取下次触发时间"""
        pass

    def __lt__(self, other: "Trigger") -> bool:
        if isinstance(other, Trigger):
            return self.trigger_dt < other.trigger_dt
        return NotImplemented


class OnceTrigger(Trigger):
    """一次性触发器"""
    
    def next(self) -> Optional[datetime]:
        if self.status == TriggerStatus.COMPLETED:
            return None
        self.status = TriggerStatus.COMPLETED
        return self.trigger_dt


class IntervalTrigger(Trigger):
    """间隔触发器"""
    
    def next(self) -> Optional[datetime]:
        if self.status == TriggerStatus.COMPLETED:
            return None
        
        next_dt = self.trigger_dt + timedelta(seconds=self.interval)
        
        # 检查是否超过结束时间（如果有）
        if hasattr(self, 'end_dt') and next_dt > self.end_dt:
            self.status = TriggerStatus.COMPLETED
            return None
        
        self.trigger_dt = next_dt
        return next_dt


class CronTrigger(Trigger):
    """Cron 触发器（简化版）"""
    cron_expression: str = "* * * * * *"
    
    def next(self) -> Optional[datetime]:
        # 简化实现：每秒触发
        if self.status == TriggerStatus.COMPLETED:
            return None
        next_dt = self.trigger_dt + timedelta(seconds=1)
        self.trigger_dt = next_dt
        return next_dt
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/trigger.py
git commit -m "feat(botflow): add trigger module based on vxsched"
```

---

## Task 4: 任务模块 (Task, TaskQueue, TaskManager)

**Files:**
- Create: `src/openbot/botflow/task.py`

**Step 1: 创建任务模块**

```python
"""BotFlow 任务模块 - 统一的任务系统"""
import asyncio
import uuid
import logging
import inspect
from datetime import datetime
from enum import Enum
from heapq import heappush, heappop
from typing import Any, Callable, Dict, List, Optional

# 导入 Trigger（从 trigger.py）
from .trigger import Trigger


class Task:
    """任务类（函数式设计）"""
    
    def __init__(self, name: str, func: Callable, *args: Any, **kwargs: Any) -> None:
        self.id = str(uuid.uuid4())
        self.name = name
        self.trigger = None
        self.trigger_dt = None  # 添加 trigger_dt 属性
        self.created_at = datetime.now()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def set_trigger(self, trigger: Trigger):
        self.trigger = trigger
        self.trigger_dt = self.trigger.next()

    async def run(self):
        """执行任务"""
        while self.trigger_dt:
            now = datetime.now()
            if self.trigger_dt > now:
                await asyncio.sleep((self.trigger_dt - now).total_seconds())
            
            # 执行任务（无论是否等待，都执行）
            if inspect.iscoroutinefunction(self.func):
                await self.func(*self.args, **self.kwargs)
            else:
                await asyncio.to_thread(self.func, *self.args, **self.kwargs)
            
            # 获取下次触发时间
            if self.trigger:
                self.trigger_dt = self.trigger.next()
            else:
                self.trigger_dt = None


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self._tasks: List[Task] = []
        self._coroutines: List[asyncio.Task] = []
        self._running = False
   
    def submit(self, task: Task):
        self._tasks.append(task)
        self._coroutines.append(asyncio.create_task(task.run()))
    
    def list_tasks(self):
        return self._tasks
    
    def list_coroutines(self):
        return self._coroutines
    
    def close(self):
        for coroutine in self._coroutines:
            coroutine.cancel()
        self._coroutines.clear()
        self._tasks.clear()
```
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/event.py
git commit -m "feat(botflow): add event module based on vxsched"
```

---

## Task 5: 通道基类

**Files:**
- Create: `src/openbot/botflow/channels/__init__.py`
- Create: `src/openbot/botflow/channels/base.py`

**Step 1: 创建通道基类**

```python
"""BotFlow 通道基类"""
from abc import ABC, abstractmethod
from typing import Optional, Callable


class ChatChannel(ABC):
    """聊天通道基类"""
    
    def __init__(self, channel_id: str):
        self.channel_id = channel_id
    
    @abstractmethod
    async def start(self):
        pass
    
    @abstractmethod
    async def stop(self):
        pass
    
    @abstractmethod
    async def send(self, content: str, reply_to: str = ""):
        pass
    
    def set_message_handler(self, handler: Callable):
        self._message_handler = handler
    
    async def on_message(self, content: str, reply_to: str = ""):
        if self._message_handler:
            await self._message_handler(content, self.channel_id, reply_to)
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/channels/base.py src/openbot/botflow/channels/__init__.py
git commit -m "feat(botflow): add channel base class"
```

---

## Task 6: WebSocket 通道

**Files:**
- Create: `src/openbot/botflow/channels/websocket.py`

**Step 1: 创建 WebSocket 通道**

```python
"""BotFlow WebSocket 通道"""
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from .base import ChatChannel


class WebSocketChannel(ChatChannel):
    def __init__(self, path: str = "/ws/chat"):
        super().__init__("websocket")
        self.path = path
        self._connections: list[WebSocket] = []
    
    async def start(self):
        pass
    
    async def stop(self):
        self._connections.clear()
    
    async def send(self, content: str, reply_to: str = ""):
        message = {"type": "message", "content": content, "reply_to": reply_to}
        disconnected = []
        for conn in self._connections:
            try:
                await conn.send_json(message)
            except:
                disconnected.append(conn)
        for conn in disconnected:
            self._connections.remove(conn)
    
    async def handle_connection(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.append(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    content = message.get("content", data)
                except:
                    content = data
                await self.on_message(content)
        except WebSocketDisconnect:
            self._connections.remove(websocket)
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/channels/websocket.py
git commit -m "feat(botflow): add websocket channel"
```

---

## Task 7: WeChat 通道

**Files:**
- Create: `src/openbot/botflow/channels/wechat.py`

**Step 1: 创建 WeChat 通道**

```python
"""BotFlow WeChat 通道"""
import hashlib
import logging
import xml.etree.ElementTree as ET
from typing import Optional
from aiohttp import web
from .base import ChatChannel


class WeChatChannel(ChatChannel):
    def __init__(self, app_id: str = "", app_secret: str = "", 
                 token: str = "", path: str = "/wechat"):
        super().__init__("wechat")
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = token
        self.path = path
    
    async def start(self):
        pass
    
    async def stop(self):
        pass
    
    async def send(self, content: str, reply_to: str = ""):
        # 实现客服消息发送
        pass
    
    async def handle_verify(self, request) -> web.Response:
        signature = request.query.get("signature", "")
        timestamp = request.query.get("timestamp", "")
        nonce = request.query.get("nonce", "")
        echostr = request.query.get("echostr", "")
        
        if self._verify_signature(signature, timestamp, nonce):
            return web.Response(text=echostr)
        return web.Response(text="", status=403)
    
    async def handle_message(self, request) -> web.Response:
        body = await request.text()
        try:
            root = ET.fromstring(body)
            msg_type = root.find("MsgType").text
            content = root.find("Content").text or ""
            
            if msg_type == "text":
                await self.on_message(content, root.find("FromUserName").text)
        except:
            pass
        return web.Response(text="success")
    
    def _verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        tmp_list = sorted([self.token, timestamp, nonce])
        tmp_str = "".join(tmp_list)
        return hashlib.sha1(tmp_str.encode()).hexdigest() == signature
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/channels/wechat.py
git commit -m "feat(botflow): add wechat channel"
```

---

## Task 8: FastBotFlow 主应用

**Files:**
- Create: `src/openbot/botflow/main.py`

**Step 1: 创建主应用**

```python
"""BotFlow 主应用 - FastAPI"""
import logging
import time
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Request

from .config import BotFlowConfig, ChannelConfig
from .database import DatabaseManager, Message
from .task import Task, TaskManager
from .channels import ChatChannel
from .channels.websocket import WebSocketChannel
from .channels.wechat import WeChatChannel

# OpenBotExecutor - 从 agents 导入
from openbot.agents.core import OpenBotExecutor


class FastBotFlow(FastAPI):
    def __init__(
        self,
        config: BotFlowConfig,
        agent_config: dict,
    ):
        super().__init__(title="BotFlow", version="0.3.0")
        
        self.config = config
        
        # 初始化组件
        self.db = DatabaseManager(config.db_path)
        self.task_manager = TaskManager()
        
        # Agent
        self.agent = OpenBotExecutor(**agent_config)
        
        # 通道
        self.channels: dict[str, ChatChannel] = {}
        
        # 生命周期
        self.add_event_handler("startup", self._on_startup)
        self.add_event_handler("shutdown", self._on_shutdown)
    
    def _register_routes(self):
        @self.get("/")
        async def root():
            return {"name": "BotFlow", "version": "0.3.0"}
        
        @self.get("/health")
        async def health():
            return {"status": "healthy", "task_count": len(self.task_manager.list_tasks())}
        
        # 动态注册通道路由
        for channel_config in self.config.channels:
            if not channel_config.enabled:
                continue
            
            if channel_config.name == "websocket":
                @self.websocket(channel_config.params.get("path", "/ws/chat"))
                async def websocket_chat(websocket: WebSocket):
                    ws_channel = self.channels.get("websocket")
                    if ws_channel:
                        await ws_channel.handle_connection(websocket)
            
            elif channel_config.name == "wechat":
                path = channel_config.params.get("path", "/wechat")
                
                @self.get(path)
                async def wechat_verify(request: Request):
                    wc = self.channels.get("wechat")
                    if wc:
                        return await wc.handle_verify(request)
                
                @self.post(path)
                async def wechat_message(request: Request):
                    wc = self.channels.get("wechat")
                    if wc:
                        return await wc.handle_message(request)
    
    async def _on_startup(self):
        await self.db.initialize()
        
        # 初始化通道
        for channel_config in self.config.channels:
            if not channel_config.enabled:
                continue
            
            if channel_config.name == "websocket":
                ws_channel = WebSocketChannel(channel_config.params.get("path", "/ws/chat"))
                ws_channel.set_message_handler(self._handle_message)
                self.channels["websocket"] = ws_channel
            
            elif channel_config.name == "wechat":
                wc_channel = WeChatChannel(
                    app_id=channel_config.params.get("app_id", ""),
                    app_secret=channel_config.params.get("app_secret", ""),
                    token=channel_config.params.get("token", ""),
                    path=channel_config.params.get("path", "/wechat")
                )
                wc_channel.set_message_handler(self._handle_message)
                self.channels["wechat"] = wc_channel
    
    async def _on_shutdown(self):
        for channel in self.channels.values():
            await channel.stop()
        await self.task_manager.close()
    
    async def _handle_message(self, content: str, channel_id: str, reply_to: str = ""):
        # 保存用户消息
        user_message = Message(content=content, role="user", channel_id=channel_id)
        await self.db.save_message(user_message)
        
        # 放入任务队列
        task = Task(
            name="bot_task",
            func=self._process_message,
            args=(content, channel_id, reply_to)
        )
        await self.task_manager.submit(task)
    
    async def _process_message(self, content: str, channel_id: str, reply_to: str = ""):
        """处理消息事件"""
        start_time = time.time()
        
        # 调用 Agent
        from langchain_core.messages import HumanMessage
        response_content = ""
        async for chunk in self.agent.astream(
            {"messages": [HumanMessage(content=content)]}
        ):
            if "messages" in chunk:
                for msg in chunk["messages"]:
                    if hasattr(msg, "content"):
                        response_content += msg.content
        
        process_time = int((time.time() - start_time) * 1000)
        
        # 保存响应
        bot_message = Message(
            content=response_content,
            role="assistant",
            channel_id=channel_id,
            process_time_ms=process_time
        )
        await self.db.save_message(bot_message)
        
        # 发送回通道
        channel = self.channels.get(channel_id)
        if channel:
            await channel.send(response_content, reply_to)
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/main.py
git commit -m "feat(botflow): add FastBotFlow main application"
```

---

## Task 9: 模块导出

**Files:**
- Modify: `src/openbot/botflow/__init__.py`

**Step 1: 更新导出**

```python
"""BotFlow 模块"""
from .config import BotFlowConfig, ChannelConfig
from .database import DatabaseManager, Message
from .trigger import Trigger, OnceTrigger, IntervalTrigger, CronTrigger
from .task import Task, TaskManager
from .channels import ChatChannel
from .main import FastBotFlow

__all__ = [
    "FastBotFlow",
    "BotFlowConfig",
    "ChannelConfig",
    "DatabaseManager",
    "Message",
    "Task",
    "TaskManager",
    "Trigger",
    "OnceTrigger",
    "IntervalTrigger", 
    "CronTrigger",
    "ChatChannel",
]
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/__init__.py
git commit -m "feat(botflow): update module exports"
```

---

## 计划完成

**Plan complete and saved to `docs/plans/2026-02-24-botflow-implementation-plan-v2.md`**

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
