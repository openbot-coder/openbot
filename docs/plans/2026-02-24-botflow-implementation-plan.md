# BotFlow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于 FastAPI 实现 BotFlow 框架，支持 WebSocket 和 WeChat 通道，内置消息队列和定时任务

**Architecture:** 使用 FastAPI 作为核心框架，继承其最佳实践。Channels 作为依赖注入，消息通过队列异步处理，结果路由回对应通道

**Tech Stack:** FastAPI, aiosqlite, aiohttp, uvicorn

---

## 目录结构

```
src/openbot/
├── botflow/
│   ├── __init__.py          # 模块导出
│   ├── config.py            # 配置模型
│   ├── database.py         # 数据库 (aiosqlite)
│   ├── queue.py            # 消息队列
│   ├── scheduler.py         # 定时任务
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── base.py         # 通道基类
│   │   ├── websocket.py     # WebSocket 通道
│   │   └── wechat.py       # 微信公众号通道
│   └── main.py             # FastBotFlow 主应用
```

---

## Task 1: 配置模块

**Files:**
- Create: `src/openbot/botflow/config.py`

**Step 1: 创建配置模块**

```python
"""BotFlow 配置"""
from pydantic import BaseModel
from typing import Optional


class BotFlowConfig(BaseModel):
    """BotFlow 配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "data/botflow.db"
    worker_count: int = 4
    queue_timeout: float = 30.0


class WeChatConfig(BaseModel):
    """微信公众号配置"""
    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""
    token: str = ""
    port: int = 8080
    path: str = "/wechat"


class WebSocketConfig(BaseModel):
    """WebSocket 配置"""
    enabled: bool = True
    path: str = "/ws/chat"


class SchedulerConfig(BaseModel):
    """定时任务配置"""
    enabled: bool = True
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
    channel_type: str = ""
    token_count: int = 0
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
                channel_type TEXT NOT NULL,
                token_count INTEGER DEFAULT 0,
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
            INSERT INTO messages (id, content, role, channel_type, token_count, process_time_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (message.id, message.content, message.role, message.channel_type,
              message.token_count, message.process_time_ms, message.created_at))
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

## Task 3: 消息队列模块

**Files:**
- Create: `src/openbot/botflow/queue.py`

**Step 1: 创建消息队列模块**

```python
"""BotFlow 消息队列 - 使用 asyncio.PriorityQueue"""
import asyncio
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Callable, Optional, Any, Dict


class MessagePriority(IntEnum):
    HIGH = 0
    NORMAL = 10
    LOW = 20


@dataclass
class QueuedMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: MessagePriority = MessagePriority.NORMAL
    content: str = ""
    channel_type: str = ""
    reply_to: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


class MessageQueue:
    """异步优先消息队列"""
    
    def __init__(self, worker_count: int = 4, timeout: float = 30.0):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._workers: list[asyncio.Task] = []
        self._worker_count = worker_count
        self._timeout = timeout
        self._handlers: Dict[str, Callable] = {}
        self._running = False
    
    async def start(self):
        """启动队列"""
        self._running = True
        for i in range(self._worker_count):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
    
    async def stop(self):
        """停止队列"""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()
    
    def set_handler(self, channel_type: str, handler: Callable):
        """设置消息处理器"""
        self._handlers[channel_type] = handler
    
    async def put(self, message: QueuedMessage):
        """放入消息"""
        await self._queue.put(message)
    
    async def _worker(self, worker_id: int):
        """Worker 协程"""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                handler = self._handlers.get(message.channel_type)
                if handler:
                    try:
                        await handler(message)
                    except Exception as e:
                        logging.error(f"Handler error: {e}")
            except asyncio.TimeoutError:
                continue
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/queue.py
git commit -m "feat(botflow): add message queue module"
```

---

## Task 4: 定时任务模块

**Files:**
- Create: `src/openbot/botflow/scheduler.py`

**Step 1: 创建定时任务模块**

```python
"""BotFlow 定时任务模块"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional, List
from enum import Enum


class TaskType(Enum):
    INTERVAL = "interval"
    CRON = "cron"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScheduledTask:
    id: str
    name: str
    task_type: TaskType
    func: Callable
    interval_seconds: Optional[int] = None
    status: TaskStatus = TaskStatus.PENDING
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动调度器"""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._run())
    
    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
    
    def add_interval_task(
        self,
        name: str,
        func: Callable,
        interval_seconds: int
    ) -> str:
        """添加间隔任务"""
        task_id = f"task_{len(self._tasks)}"
        task = ScheduledTask(
            id=task_id,
            name=name,
            task_type=TaskType.INTERVAL,
            func=func,
            interval_seconds=interval_seconds,
            next_run=datetime.now()
        )
        self._tasks[task_id] = task
        return task_id
    
    async def _run(self):
        """调度循环"""
        while self._running:
            now = datetime.now()
            for task in self._tasks.values():
                if task.next_run and now >= task.next_run:
                    asyncio.create_task(self._execute(task))
            await asyncio.sleep(1)
    
    async def _execute(self, task: ScheduledTask):
        """执行任务"""
        task.status = TaskStatus.RUNNING
        try:
            if asyncio.iscoroutinefunction(task.func):
                await task.func()
            else:
                task.func()
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            logging.error(f"Task {task.name} failed: {e}")
            task.status = TaskStatus.FAILED
        
        if task.interval_seconds:
            task.next_run = datetime.now() + timedelta(seconds=task.interval_seconds)
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/scheduler.py
git commit -m "feat(botflow): add scheduler module"
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
from typing import Optional, Callable, Any


class ChatChannel(ABC):
    """聊天通道基类"""
    
    def __init__(self, channel_type: str):
        self.channel_type = channel_type
        self._message_handler: Optional[Callable] = None
    
    @abstractmethod
    async def start(self):
        """启动通道"""
        pass
    
    @abstractmethod
    async def stop(self):
        """停止通道"""
        pass
    
    @abstractmethod
    async def send(self, content: str, reply_to: str = ""):
        """发送消息"""
        pass
    
    def set_message_handler(self, handler: Callable):
        """设置消息处理器"""
        self._message_handler = handler
    
    async def on_message(self, content: str, reply_to: str = ""):
        """收到消息回调"""
        if self._message_handler:
            await self._message_handler(content, self.channel_type, reply_to)
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
    """WebSocket 通道"""
    
    def __init__(self, path: str = "/ws/chat"):
        super().__init__("websocket")
        self.path = path
        self._connections: list[WebSocket] = []
    
    async def start(self):
        """启动（WebSocket 由 FastAPI 路由管理）"""
        pass
    
    async def stop(self):
        """停止"""
        self._connections.clear()
    
    async def send(self, content: str, reply_to: str = ""):
        """广播消息到所有连接"""
        message = {
            "type": "message",
            "content": content,
            "reply_to": reply_to
        }
        disconnected = []
        for conn in self._connections:
            try:
                await conn.send_json(message)
            except:
                disconnected.append(conn)
        for conn in disconnected:
            self._connections.remove(conn)
    
    async def handle_connection(self, websocket: WebSocket):
        """处理 WebSocket 连接"""
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
    """微信公众号通道"""
    
    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        token: str = "",
        path: str = "/wechat"
    ):
        super().__init__("wechat")
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = token
        self.path = path
        self._app: Optional[web.Application] = None
    
    async def start(self):
        """启动 WeChat 服务器"""
        self._app = web.Application()
        self._app.router.add_get(self.path, self._handle_verify)
        self._app.router.add_post(self.path, self._handle_message)
    
    async def stop(self):
        """停止"""
        if self._app:
            await self._app.cleanup()
    
    async def _handle_verify(self, request: web.Request) -> web.Response:
        """处理验证请求"""
        signature = request.query.get("signature", "")
        timestamp = request.query.get("timestamp", "")
        nonce = request.query.get("nonce", "")
        echostr = request.query.get("echostr", "")
        
        if self._verify_signature(signature, timestamp, nonce):
            return web.Response(text=echostr)
        return web.Response(text="", status=403)
    
    async def _handle_message(self, request: web.Request) -> web.Response:
        """处理消息请求"""
        body = await request.text()
        try:
            root = ET.fromstring(body)
            msg_type = root.find("MsgType").text
            from_user = root.find("FromUserName").text
            content = root.find("Content").text or ""
            
            if msg_type == "text":
                await self.on_message(content, from_user)
        except:
            pass
        return web.Response(text="success")
    
    def _verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        """验证签名"""
        tmp_list = sorted([self.token, timestamp, nonce])
        tmp_str = "".join(tmp_list)
        return hashlib.sha1(tmp_str.encode()).hexdigest() == signature
    
    async def send(self, content: str, reply_to: str = ""):
        """发送客服消息（需要 access_token）"""
        # 实现发送客服消息逻辑
        pass
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
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse

from .config import BotFlowConfig, WeChatConfig, WebSocketConfig, SchedulerConfig
from .database import DatabaseManager, Message
from .queue import MessageQueue, QueuedMessage, MessagePriority
from .scheduler import TaskScheduler
from .channels import ChatChannel
from .channels.websocket import WebSocketChannel
from .channels.wechat import WeChatChannel

# OpenBotExecutor - 从 agents 导入
from openbot.agents.core import OpenBotExecutor


class FastBotFlow(FastAPI):
    """BotFlow 主应用"""
    
    def __init__(
        self,
        config: BotFlowConfig,
        wechat_config: WeChatConfig,
        websocket_config: WebSocketConfig,
        scheduler_config: SchedulerConfig,
        agent_config: dict,
    ):
        super().__init__(title="BotFlow", version="0.3.0")
        
        self.config = config
        self.wechat_config = wechat_config
        self.websocket_config = websocket_config
        self.scheduler_config = scheduler_config
        
        # 初始化组件
        self.db = DatabaseManager(config.db_path)
        self.queue = MessageQueue(config.worker_count, config.queue_timeout)
        self.scheduler = TaskScheduler()
        
        # Agent
        self.agent = OpenBotExecutor(**agent_config)
        
        # 通道
        self.channels: dict[str, ChatChannel] = {}
        
        # 注册路由
        self._register_routes()
        
        # 生命周期
        self.add_event_handler("startup", self._on_startup)
        self.add_event_handler("shutdown", self._on_shutdown)
    
    def _register_routes(self):
        """注册路由"""
        
        @self.get("/")
        async def root():
            return {"name": "BotFlow", "version": "0.3.0", "status": "running"}
        
        @self.get("/health")
        async def health():
            return {"status": "healthy", "queue_size": self.queue._queue.qsize()}
        
        @self.websocket(self.websocket_config.path)
        async def websocket_chat(websocket: WebSocket):
            ws_channel = self.channels.get("websocket")
            if ws_channel:
                await ws_channel.handle_connection(websocket)
        
        if self.wechat_config.enabled:
            @self.get(self.wechat_config.path)
            async def wechat_verify(request: Request):
                wc = self.channels.get("wechat")
                if wc:
                    return await wc._handle_verify(request)
            
            @self.post(self.wechat_config.path)
            async def wechat_message(request: Request):
                wc = self.channels.get("wechat")
                if wc:
                    return await wc._handle_message(request)
    
    async def _on_startup(self):
        """启动"""
        await self.db.initialize()
        await self.queue.start()
        
        # 初始化通道
        if self.websocket_config.enabled:
            ws_channel = WebSocketChannel(self.websocket_config.path)
            ws_channel.set_message_handler(self._handle_message)
            self.channels["websocket"] = ws_channel
            await ws_channel.start()
        
        if self.wechat_config.enabled:
            wc_channel = WeChatChannel(
                self.wechat_config.app_id,
                self.wechat_config.app_secret,
                self.wechat_config.token,
                self.wechat_config.path
            )
            wc_channel.set_message_handler(self._handle_message)
            self.channels["wechat"] = wc_channel
            await wc_channel.start()
        
        # 启动调度器
        if self.scheduler_config.enabled:
            await self.scheduler.start()
    
    async def _on_shutdown(self):
        """关闭"""
        for channel in self.channels.values():
            await channel.stop()
        await self.queue.stop()
        await self.scheduler.stop()
        await self.db.close()
    
    async def _handle_message(self, content: str, channel_type: str, reply_to: str = ""):
        """处理收到的消息"""
        start_time = datetime.now()
        
        # 保存用户消息
        user_message = Message(content=content, role="user", channel_type=channel_type)
        await self.db.save_message(user_message)
        
        # 放入队列
        queued = QueuedMessage(
            content=content,
            channel_type=channel_type,
            reply_to=reply_to
        )
        await self.queue.put(queued)
    
    async def _process_message(self, message: QueuedMessage):
        """处理队列消息"""
        from langchain_core.messages import HumanMessage
        import time
        
        start_time = time.time()
        
        # 调用 Agent
        response_content = ""
        async for chunk in self.agent.astream(
            {"messages": [HumanMessage(content=message.content)]}
        ):
            if "messages" in chunk:
                for msg in chunk["messages"]:
                    if hasattr(msg, "content"):
                        response_content += msg.content
        
        process_time = int((time.time() - start_time) * 1000)
        
        # 保存响应消息
        bot_message = Message(
            content=response_content,
            role="assistant",
            channel_type=message.channel_type,
            process_time_ms=process_time
        )
        await self.db.save_message(bot_message)
        
        # 发送回通道
        channel = self.channels.get(message.channel_type)
        if channel:
            await channel.send(response_content, message.reply_to)
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
from .config import BotFlowConfig, WeChatConfig, WebSocketConfig, SchedulerConfig
from .database import DatabaseManager, Message
from .queue import MessageQueue, QueuedMessage, MessagePriority
from .scheduler import TaskScheduler
from .channels import ChatChannel
from .main import FastBotFlow

__all__ = [
    "FastBotFlow",
    "BotFlowConfig",
    "WeChatConfig", 
    "WebSocketConfig",
    "SchedulerConfig",
    "DatabaseManager",
    "Message",
    "MessageQueue",
    "QueuedMessage",
    "MessagePriority",
    "TaskScheduler",
    "ChatChannel",
]
```

**Step 2: Commit**

```bash
git add src/openbot/botflow/__init__.py
git commit -m "feat(botflow): update module exports"
```

---

## Task 10: 测试运行

**Step 1: 创建测试文件**

```bash
mkdir -p tests/botflow
touch tests/botflow/__init__.py
```

**Step 2: 运行测试**

```bash
# 安装依赖
uv add aiosqlite aiohttp

# 启动服务
uv run python -m uvicorn src.openbot.botflow.main:app --host 0.0.0.0 --port 8000
```

---

## 计划完成

**Plan complete and saved to `docs/plans/2026-02-24-botflow-implementation-plan.md`**

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
