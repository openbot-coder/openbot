# OpenBot 设计文档

## 一、项目概述

OpenBot 是一个可以通过命令行运行的 AI Bot，具备对话交互、任务执行、工具集成以及自我进化能力。

### 核心特性

- **多渠道交互**：通过 ChatChannel 抽象层支持 Console、WebSocket、微信、钉钉等多种交互渠道
- **智能任务处理**：基于 LangChain DeepAgents 实现任务规划、分解和执行
- **自我进化**：支持代码级自修改，通过版本控制和审批机制确保安全
- **可扩展架构**：模块化设计，支持 Skills 和 MCP 服务扩展

### MVP 版本范围

| 模块 | MVP 支持 | 后续扩展 |
|------|----------|----------|
| ChatChannel | ConsoleChannel | WebSocket, WeChat, DingTalk... |
| DeepAgents | 内置参数创建 | 自定义 planner, subagents |
| Memory | 暂不实现 | 用户画像、关键事实、短期/长期记忆 |
| Evolution | 基础框架 | 完整审批流程、热加载 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI Entry                              │
│                      (openbot command)                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                      ChatChannel Layer                          │
│                      ConsoleChannel (MVP)                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                         BotFlow                                 │
│  ┌────────────────┬──────────────┬──────────────┬──────────────┐  │
│  │ChatChannelMgr  │   Session    │   Message    │  Evolution   │  │
│  │                │   Manager    │   Processor  │   Controller │  │
│  └────────────────┼──────────────┴──────────────┴──────────────┘  │
│                   │                                               │
│                   │  ┌───────────────────────────────┐            │
│                   │  │           TaskManager          │            │
│                   │  └───────────────────────────────┘            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                     DeepAgents Core                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Planning Tools │ SubAgents │ FileSystem │ Prompts      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、核心模块设计

### 3.1 CLI Entry

命令行入口，负责解析参数、初始化配置、启动 BotFlow。

**命令格式**：
```bash
openbot server --config path.json                 # 启动服务器模式，指定配置文件
openbot server --config path.json --console       # 启动服务器模式，指定配置文件并启用控制台
openbot --url ws://127.0.0.1/chat --config client.json --token $OPENBOT_KEY  # 启动客户端模式，指定 WebSocket URL、配置文件和令牌
```

**职责**：
- 解析命令行参数
- 加载配置文件
- 初始化日志系统
- 启动 BotFlow（服务器模式或客户端模式）

---

### 3.2 ChatChannel Layer

**职责**：处理不同渠道的消息输入输出，统一消息格式，将收到的消息放入 message queue 中，由 botflow 统一处理。

**核心接口**：
```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Literal
from enum import StrEnum
from pydantic import BaseModel, Field

class ContentType(StrEnum):
    TEXT = "text"
    VIDEO = "video"
    IMAGE = "image"
    FILE = "file"
    LINK = "link"

class ChatMessage(BaseModel):
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

class ChatChannel(ABC):
    @abstractmethod
    async def start(self) -> None:
        """启动 Channel"""
        pass
    
    @abstractmethod
    async def send(self, message: ChatMessage) -> None:
        """发送完整消息"""
        pass
    
    @abstractmethod
    async def on_receive(self, message: ChatMessage) -> None:
        """处理接收消息"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止 Channel"""
        pass
    
    def set_message_queue(self, message_queue: asyncio.Queue) -> None:
        """设置消息 Queue"""
        self._message_queue = message_queue
    
    @property
    def message_queue(self) -> asyncio.Queue:
        """获取消息 Queue"""
        if hasattr(self, "_message_queue"):
            return self._message_queue
        else:
            raise AttributeError("message_queue not set")
```

**MVP 实现 - ConsoleChannel**：
- 使用 prompt_toolkit 实现增强的命令行交互
- 使用 rich 库实现 Markdown 渲染和美观的终端输出
- 支持命令补全、历史记录、状态提示
- 支持基本命令：exit、help、clear、history
- 支持流式响应显示

---

### 3.3 BotFlow

**职责**：组织和编排 ChatChannels 和 DeepAgents Core 的调度，同时负责自升级流程。

#### 3.3.1 ChatChannelManager

管理多个 ChatChannel 的启停和消息路由。

```python
class ChatChannelManager:
    def __init__(self) -> None:
        self._channels: dict[str, ChatChannel] = {}
        self._message_queue = asyncio.Queue()
    
    async def on_receive(self, message: ChatMessage) -> None:
        """处理接收消息"""
        self._message_queue.put_nowait(message)
    
    async def send(self, message: ChatMessage) -> None:
        """发送消息"""
        if message.channel_id in self._channels:
            await self._channels[message.channel_id].send(message)
        else:
            logging.error(f"Channel {message.channel_id} not found")
    
    def register(self, name: str, channel: ChatChannel) -> None:
        """注册 Channel"""
        channel.set_message_queue(self._message_queue)
        self._channels[name] = channel
    
    def get(self, name: str) -> ChatChannel:
        """获取 Channel"""
        return self._channels.get(name, None)
    
    async def start(self) -> None:
        """启动所有 Channel"""
        for channel in self._channels.values():
            await channel.start()
    
    async def stop(self) -> None:
        """停止所有 Channel"""
        for channel in self._channels.values():
            await channel.stop()
```

#### 3.3.2 TaskManager

管理任务队列和任务执行。

```python
class TaskManager:
    def __init__(self):
        self.task_queue = asyncio.PriorityQueue()
    
    async def add_task(self, task: Task) -> None:
        """添加任务到队列"""
        pass
    
    async def get_task(self) -> Task:
        """获取下一个任务"""
        pass
```

#### 3.3.3 Session Manager

管理用户会话状态。

```python
from pydantic import BaseModel
from datetime import datetime

class Session(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    context: dict

class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
    
    def create(self, user_id: str) -> Session:
        """创建新会话"""
        pass
    
    def get(self, session_id: str) -> Session | None:
        """获取会话"""
        pass
    
    def close(self, session_id: str) -> None:
        """关闭会话"""
        pass
```

#### 3.3.4 Message Processor

消息预处理、后处理、格式转换。

```python
class MessageProcessor:
    def preprocess(self, message: HumanMessage) -> HumanMessage:
        """预处理：清理、格式化用户输入"""
        pass
    
    def postprocess(self, message: AnyMessage) -> AnyMessage:
        """后处理：格式化 AI 输出"""
        pass
```

#### 3.3.5 Evolution Controller

编排自升级流程。

```python
class EvolutionController:
    def __init__(self, git_manager: GitManager, approval_system: ApprovalSystem):
        self._git_manager = git_manager
        self._approval_system = approval_system
    
    async def propose_change(self, change: CodeChange) -> bool:
        """提议代码修改，等待用户审批"""
        pass
    
    async def apply_change(self, change: CodeChange) -> bool:
        """应用已批准的修改"""
        pass
    
    async def rollback(self, commit_hash: str) -> bool:
        """回滚到指定版本"""
        pass
```

#### 3.3.6 BotFlow 核心实现

```python
class BotFlow:
    def __init__(self, config: OpenbotConfig):
        self._config = config
        # 初始化核心组件
        self.session_manager = SessionManager()
        self.message_processor = MessageProcessor()
        # 初始化渠道
        self._channel_manager = ChatChannelManager()
        # 初始化智能体
        self._bot = AgentCore(self._config.model_configs, self._config.agent_config)
        # 初始化任务队列
        self.task_manager = TaskManager()
        # 运行状态
        self._stop_event = asyncio.Event()
    
    def channel_manager(self) -> ChatChannelManager:
        """获取 Channel 管理器"""
        return self._channel_manager
    
    async def initialize(self) -> None:
        """初始化智能体"""
        # 初始化渠道
        for channel_type, channel_config in self._config.channels.items():
            enabled = channel_config.enabled
            if enabled:
                channel = ChannelBuilder.create_channel(
                    channel_type, **channel_config.init_kwargs
                )
                self._channel_manager.register(channel.channel_id, channel)
        await self._channel_manager.start()
    
    async def run(self) -> None:
        """运行智能体"""
        await self.initialize()
        self._stop_event.clear()
        try:
            while not self._stop_event.is_set():
                try:
                    task = await self.task_manager.get_task()
                    await task.run()
                except KeyboardInterrupt:
                    self._stop_event.set()
                except Exception as e:
                    logging.error(f"Error running task: {e}")
        finally:
            await self._channel_manager.stop()
```

---

### 3.4 DeepAgents Core

**职责**：核心 AI 能力，基于 LangChain DeepAgents。

**核心组件**：
- **Planning Tools**：任务规划、分解、进度追踪（write_todos）
- **SubAgents System**：委托子任务给专业子智能体
- **FileSystem Tools**：文件读写、持久化存储
- **Prompts Manager**：系统提示词、角色定义、技能提示

**MVP 实现**：
```python
from langchain_deepagents import create_deep_agent

class AgentCore:
    def __init__(self, model_configs: Dict[str, ModelConfig], agent_config: AgentConfig):
        self.model_configs = model_configs
        self.agent_config = agent_config
        # 初始化 DeepAgent 或其他 Agent 实现
        self._agent = create_deep_agent(
            model_configs=model_configs,
            agent_config=agent_config
        )
    
    async def process(self, message: str, session: Session) -> str:
        """处理用户消息"""
        pass
```

---

## 四、配置文件设计

```json
{
  "model_configs": {
    "default": {
      "model_provider": "openai",
      "model": "gpt-4o",
      "api_key": "${OPENAI_API_KEY}",
      "temperature": 0.7,
      "base_url": "https://api.openai.com/v1"
    }
  },
  "agent_config": {
    "name": "openbot",
    "system_prompt": "你是一个智能助手，你的任务是回答用户的问题。",
    "skills": [],
    "memory": [],
    "tools": [],
    "debug": false
  },
  "channels": {
    "console": {
      "enabled": true,
      "init_kwargs": {
        "prompt": "openbot> "
      }
    }
  },
  "evolution": {
    "enabled": true,
    "auto_test": true,
    "require_approval": true
  }
}
```

---

## 五、项目目录结构

```
openbot/
├── src/openbot/
│   ├── __init__.py
│   ├── config.py               # 配置管理
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── base.py             # ChatChannel 基类
│   │   └── console.py          # ConsoleChannel (MVP)
│   ├── botflow/
│   │   ├── __init__.py
│   │   ├── core.py             # BotFlow 核心
│   │   ├── session.py          # Session Manager
│   │   ├── processor.py        # Message Processor
│   │   ├── evolution.py        # Evolution Controller
│   │   ├── trigger.py          # 触发器
│   │   ├── task.py             # 任务管理
│   └── agents/
│       ├── __init__.py
│       └── core.py             # DeepAgents 核心 (MVP)
├── examples/
│   └── config.json             # 示例配置文件
├── pyproject.toml
└── README.md
```

---

## 六、技术栈

| 组件 | 技术选型 |
|------|----------|
| LLM 抽象层 | LangChain `init_chat_model` |
| Agent 框架 | LangChain `create_deep_agent` |
| 向量存储 | Chroma / FAISS（后续） |
| 配置管理 | JSON + Pydantic Settings |
| 版本控制 | Git |
| 命令行增强 | prompt_toolkit |
| 终端渲染 | rich |

---

## 七、后续扩展规划

### 7.1 Memory System（后续版本）

分层记忆系统：
- **UserProfile**：用户画像
- **KeyFacts**：关键事实
- **ShortMemory**：短期记忆（当前会话）
- **LongMemory**：长期记忆（事件报告 + 向量存储）

遗忘机制：
- 时间衰减
- 访问强化
- 容量触发分层迁移

### 7.2 更多 ChatChannel

- WebSocketChannel
- WeChatChannel（微信公众号）
- DingTalkChannel（钉钉）
- FeishuChannel（飞书）
- EmailChannel（电子邮件）

### 7.3 Skills 和 MCP 服务

- 基于 DeepAgents 扩展自定义 Skills
- 集成 MCP (Model Context Protocol) 服务

---

## 八、安全机制

### 8.1 代码自修改安全

1. **修改前**：生成修改方案，展示 diff
2. **用户确认**：用户审批后才执行
3. **执行修改**：Git commit 记录变更
4. **验证测试**：运行测试确保修改正确
5. **回滚支持**：出问题可快速回滚

### 8.2 API Key 管理

- 通过环境变量注入
- 不在配置文件中硬编码
- 支持 `${VAR_NAME}` 格式引用环境变量
