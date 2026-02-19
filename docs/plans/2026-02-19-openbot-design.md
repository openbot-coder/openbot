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
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │   Channel    │   Session    │   Message    │  Evolution   │  │
│  │   Router     │   Manager    │   Processor  │   Controller │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
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
openbot                    # 启动 REPL 模式
openbot --config path.json # 指定配置文件
openbot --channel console  # 指定启动的 channel
```

**职责**：
- 解析命令行参数
- 加载配置文件
- 初始化日志系统
- 启动 BotFlow

---

### 3.2 ChatChannel Layer

**职责**：处理不同渠道的消息输入输出，统一消息格式。

**核心接口**：
```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass

from pydantic import BaseModel

class Message(BaseModel):
    content: str
    role: str  # "user" | "assistant"
    metadata: dict | None = None

class ChatChannel(ABC):
    @abstractmethod
    async def start(self) -> None:
        """启动 Channel"""
        pass
    
    @abstractmethod
    async def send(self, message: Message) -> None:
        """发送完整消息"""
        pass
    
    @abstractmethod
    async def send_stream(self, stream: AsyncIterator[str]) -> None:
        """发送流式响应"""
        pass
    
    @abstractmethod
    async def receive(self) -> AsyncIterator[Message]:
        """接收消息流"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止 Channel"""
        pass
```

**MVP 实现 - ConsoleChannel**：
- REPL 模式交互
- 支持多行输入
- 支持 Markdown 渲染（可选）

---

### 3.3 BotFlow

**职责**：组织和编排 ChatChannels 和 DeepAgents Core 的调度，同时负责自升级流程。

#### 3.3.1 Channel Router

管理多个 ChatChannel 的启停和消息路由。

```python
class ChannelRouter:
    def __init__(self):
        self.channels: dict[str, ChatChannel] = {}
    
    def register(self, name: str, channel: ChatChannel) -> None:
        """注册 Channel"""
        pass
    
    async def start_all(self) -> None:
        """启动所有 Channel"""
        pass
    
    async def broadcast(self, message: Message) -> None:
        """广播消息到所有 Channel"""
        pass
```

#### 3.3.2 Session Manager

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
        self.sessions: dict[str, Session] = {}
    
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

#### 3.3.3 Message Processor

消息预处理、后处理、格式转换。

```python
class MessageProcessor:
    def preprocess(self, message: Message) -> Message:
        """预处理：清理、格式化用户输入"""
        pass
    
    def postprocess(self, message: Message) -> Message:
        """后处理：格式化 AI 输出"""
        pass
```

#### 3.3.4 Evolution Controller

编排自升级流程。

```python
class EvolutionController:
    def __init__(self, git_manager: GitManager, approval_system: ApprovalSystem):
        self.git_manager = git_manager
        self.approval_system = approval_system
    
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
from langchain_deepagents import DeepAgent

class AgentCore:
    def __init__(self, config: dict):
        self.agent = DeepAgent(
            model=config["llm"]["model"],
            api_key=config["llm"]["api_key"],
            temperature=config["llm"]["temperature"],
        )
    
    async def process(self, message: str, session: Session) -> str:
        """处理用户消息"""
        pass
```

---

## 四、配置文件设计

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key": "${OPENAI_API_KEY}",
    "temperature": 0.7
  },
  "channels": {
    "console": {
      "enabled": true,
      "prompt": "openbot> "
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
│   ├── main.py                 # CLI 入口
│   ├── config.py               # 配置管理
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── base.py             # ChatChannel 基类
│   │   └── console.py          # ConsoleChannel (MVP)
│   ├── botflow/
│   │   ├── __init__.py
│   │   ├── router.py           # Channel Router
│   │   ├── session.py          # Session Manager
│   │   ├── processor.py        # Message Processor
│   │   └── evolution.py        # Evolution Controller
│   └── agents/
│       ├── __init__.py
│       └── core.py             # DeepAgents 核心 (MVP)
├── examples/
│   ├── memory/                 # 示例记忆存储
│   ├── events/                 # 示例事件报告
│   └── config.json             # 示例配置文件
├── pyproject.toml
└── README.md
```

---

## 六、技术栈

| 组件 | 技术选型 |
|------|----------|
| LLM 抽象层 | LangChain `init_chat_model` |
| Agent 框架 | LangChain DeepAgents |
| 向量存储 | Chroma / FAISS（后续） |
| 配置管理 | JSON |
| 版本控制 | Git |

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
