# OpenBot MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a command-line AI bot with ConsoleChannel, BotFlow orchestration, and DeepAgents core.

**Architecture:** Four-layer architecture - CLI Entry → ChatChannel → BotFlow → DeepAgents Core. MVP focuses on ConsoleChannel REPL interaction with DeepAgents handling AI tasks.

**Tech Stack:** Python 3.13, LangChain, LangChain DeepAgents, asyncio

---

## Task 1: Project Setup and Dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `examples/config.json`

**Step 1: Update pyproject.toml with dependencies**

```toml
[project]
name = "openbot"
version = "0.1.0"
description = "A command-line AI bot with self-evolution capabilities"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "langchain>=0.3.0",
    "langchain-openai>=0.3.0",
    "langchain-community>=0.3.0",
    "pydantic>=2.0.0",
]

[project.scripts]
openbot = "openbot.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "black>=26.1.0",
    "mypy>=1.19.1",
    "pytest>=9.0.2",
    "pytest-cov>=7.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.15.1",
]
```

**Step 2: Create example config file**

Create `examples/config.json`:

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

**Step 3: Install dependencies**

Run: `uv sync`

Expected: Dependencies installed successfully

**Step 4: Commit**

```bash
git add pyproject.toml examples/config.json
git commit -m "chore: add dependencies and example config"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `src/openbot/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import os
import pytest
from openbot.config import Config, load_config


def test_load_config_from_dict():
    config_dict = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "test-key",
            "temperature": 0.7
        },
        "channels": {
            "console": {"enabled": True, "prompt": "> "}
        }
    }
    config = load_config(config_dict)
    assert config.llm.provider == "openai"
    assert config.llm.model == "gpt-4o"
    assert config.channels.console.enabled is True


def test_config_env_var_substitution():
    os.environ["TEST_API_KEY"] = "secret-key"
    config_dict = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "${TEST_API_KEY}",
            "temperature": 0.7
        }
    }
    config = load_config(config_dict)
    assert config.llm.api_key == "secret-key"
    del os.environ["TEST_API_KEY"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'openbot.config'"

**Step 3: Write minimal implementation**

Create `src/openbot/config.py`:

```python
import json
import os
import re
from pathlib import Path
from typing import Any
from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    temperature: float = 0.7


class ConsoleChannelConfig(BaseModel):
    enabled: bool = True
    prompt: str = "openbot> "


class ChannelsConfig(BaseModel):
    console: ConsoleChannelConfig = ConsoleChannelConfig()


class EvolutionConfig(BaseModel):
    enabled: bool = True
    auto_test: bool = True
    require_approval: bool = True


class Config(BaseModel):
    llm: LLMConfig = LLMConfig()
    channels: ChannelsConfig = ChannelsConfig()
    evolution: EvolutionConfig = EvolutionConfig()


def _substitute_env_vars(value: str) -> str:
    pattern = r"\$\{([^}]+)\}"
    
    def replace(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    
    return re.sub(pattern, replace, value)


def _process_dict(d: dict) -> dict:
    result = {}
    for key, value in d.items():
        if isinstance(value, str):
            result[key] = _substitute_env_vars(value)
        elif isinstance(value, dict):
            result[key] = _process_dict(value)
        else:
            result[key] = value
    return result


def load_config(config_dict: dict) -> Config:
    processed = _process_dict(config_dict)
    
    llm_data = processed.get("llm", {})
    llm_config = LLMConfig(
        provider=llm_data.get("provider", "openai"),
        model=llm_data.get("model", "gpt-4o"),
        api_key=llm_data.get("api_key", ""),
        temperature=llm_data.get("temperature", 0.7),
    )
    
    channels_data = processed.get("channels", {})
    console_data = channels_data.get("console", {})
    console_config = ConsoleChannelConfig(
        enabled=console_data.get("enabled", True),
        prompt=console_data.get("prompt", "openbot> "),
    )
    channels_config = ChannelsConfig(console=console_config)
    
    evolution_data = processed.get("evolution", {})
    evolution_config = EvolutionConfig(
        enabled=evolution_data.get("enabled", True),
        auto_test=evolution_data.get("auto_test", True),
        require_approval=evolution_data.get("require_approval", True),
    )
    
    return Config(llm=llm_config, channels=channels_config, evolution=evolution_config)


def load_config_from_file(path: str | Path) -> Config:
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        config_dict = json.load(f)
    return load_config(config_dict)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/openbot/config.py tests/test_config.py
git commit -m "feat: add configuration module"
```

---

## Task 3: ChatChannel Base Module

**Files:**
- Create: `src/openbot/channels/__init__.py`
- Create: `src/openbot/channels/base.py`
- Create: `tests/channels/test_base.py`

**Step 1: Write the failing test**

Create `tests/channels/test_base.py`:

```python
import pytest
from openbot.channels.base import Message


def test_message_creation():
    msg = Message(content="Hello", role="user")
    assert msg.content == "Hello"
    assert msg.role == "user"
    assert msg.metadata is None


def test_message_with_metadata():
    msg = Message(content="Hi", role="assistant", metadata={"key": "value"})
    assert msg.metadata == {"key": "value"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/channels/test_base.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/openbot/channels/__init__.py`:

```python
from openbot.channels.base import ChatChannel, Message

__all__ = ["ChatChannel", "Message"]
```

Create `src/openbot/channels/base.py`:

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any
from pydantic import BaseModel


class Message(BaseModel):
    content: str
    role: str
    metadata: dict[str, Any] | None = None


class ChatChannel(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Start the channel and begin listening for messages."""
        pass
    
    @abstractmethod
    async def send(self, message: Message) -> None:
        """Send a complete message through this channel."""
        pass
    
    @abstractmethod
    async def send_stream(self, stream: AsyncIterator[str]) -> None:
        """Send a streaming response through this channel."""
        pass
    
    @abstractmethod
    async def receive(self) -> AsyncIterator[Message]:
        """Receive messages from this channel."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
        pass
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/channels/test_base.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/openbot/channels/ tests/channels/
git commit -m "feat: add ChatChannel base module"
```

---

## Task 4: ConsoleChannel Implementation

**Files:**
- Create: `src/openbot/channels/console.py`
- Create: `tests/channels/test_console.py`

**Step 1: Write the failing test**

Create `tests/channels/test_console.py`:

```python
import pytest
from openbot.channels.console import ConsoleChannel
from openbot.channels.base import Message


@pytest.mark.asyncio
async def test_console_channel_creation():
    channel = ConsoleChannel(prompt="test> ")
    assert channel.prompt == "test> "


@pytest.mark.asyncio
async def test_console_send_message(capsys):
    channel = ConsoleChannel()
    await channel.send(Message(content="Hello World", role="assistant"))
    captured = capsys.readouterr()
    assert "Hello World" in captured.out
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/channels/test_console.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/openbot/channels/console.py`:

```python
import asyncio
import sys
from typing import AsyncIterator

from openbot.channels.base import ChatChannel, Message


class ConsoleChannel(ChatChannel):
    def __init__(self, prompt: str = "openbot> "):
        self.prompt = prompt
        self._running = False
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
    
    async def start(self) -> None:
        """Start the console channel."""
        self._running = True
        print("OpenBot started. Type 'exit' or 'quit' to exit.\n")
    
    async def send(self, message: Message) -> None:
        """Send a message to the console."""
        if message.role == "assistant":
            print(f"\n{message.content}\n")
        else:
            print(f"[{message.role}]: {message.content}")
    
    async def send_stream(self, stream: AsyncIterator[str]) -> None:
        """Send a streaming response to the console."""
        print("\n", end="")
        async for chunk in stream:
            print(chunk, end="", flush=True)
        print("\n")
    
    async def receive(self) -> AsyncIterator[Message]:
        """Receive messages from console input."""
        while self._running:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, self._get_input
                )
                if user_input is None:
                    continue
                
                user_input = user_input.strip()
                if user_input.lower() in ("exit", "quit"):
                    self._running = False
                    break
                
                if user_input:
                    yield Message(content=user_input, role="user")
            except (KeyboardInterrupt, EOFError):
                self._running = False
                break
    
    def _get_input(self) -> str | None:
        try:
            return input(self.prompt)
        except (KeyboardInterrupt, EOFError):
            return None
    
    async def stop(self) -> None:
        """Stop the console channel."""
        self._running = False
        print("\nGoodbye!")
```

**Step 4: Update __init__.py**

Update `src/openbot/channels/__init__.py`:

```python
from openbot.channels.base import ChatChannel, Message
from openbot.channels.console import ConsoleChannel

__all__ = ["ChatChannel", "Message", "ConsoleChannel"]
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/channels/test_console.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/openbot/channels/ tests/channels/
git commit -m "feat: add ConsoleChannel implementation"
```

---

## Task 5: BotFlow Session Manager

**Files:**
- Create: `src/openbot/botflow/__init__.py`
- Create: `src/openbot/botflow/session.py`
- Create: `tests/botflow/test_session.py`

**Step 1: Write the failing test**

Create `tests/botflow/test_session.py`:

```python
import pytest
from openbot.botflow.session import Session, SessionManager


def test_session_creation():
    manager = SessionManager()
    session = manager.create(user_id="test-user")
    
    assert session.user_id == "test-user"
    assert session.id is not None
    assert session.context == {}


def test_session_get():
    manager = SessionManager()
    session = manager.create(user_id="test-user")
    
    retrieved = manager.get(session.id)
    assert retrieved is session


def test_session_close():
    manager = SessionManager()
    session = manager.create(user_id="test-user")
    
    manager.close(session.id)
    assert manager.get(session.id) is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/botflow/test_session.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/openbot/botflow/__init__.py`:

```python
from openbot.botflow.session import Session, SessionManager

__all__ = ["Session", "SessionManager"]
```

Create `src/openbot/botflow/session.py`:

```python
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class Session(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    context: dict[str, Any] = {}


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
    
    def create(self, user_id: str) -> Session:
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,
            created_at=datetime.now(),
            context={},
        )
        self._sessions[session.id] = session
        return session
    
    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)
    
    def close(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
    
    def get_all(self) -> list[Session]:
        return list(self._sessions.values())
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/botflow/test_session.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/openbot/botflow/ tests/botflow/
git commit -m "feat: add SessionManager for BotFlow"
```

---

## Task 6: BotFlow Message Processor

**Files:**
- Create: `src/openbot/botflow/processor.py`
- Create: `tests/botflow/test_processor.py`

**Step 1: Write the failing test**

Create `tests/botflow/test_processor.py`:

```python
import pytest
from openbot.botflow.processor import MessageProcessor
from openbot.channels.base import Message


def test_preprocess_strips_whitespace():
    processor = MessageProcessor()
    msg = Message(content="  hello world  ", role="user")
    
    result = processor.preprocess(msg)
    assert result.content == "hello world"


def test_postprocess_adds_formatting():
    processor = MessageProcessor()
    msg = Message(content="Hello", role="assistant")
    
    result = processor.postprocess(msg)
    assert result.content == "Hello"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/botflow/test_processor.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/openbot/botflow/processor.py`:

```python
from openbot.channels.base import Message


class MessageProcessor:
    def preprocess(self, message: Message) -> Message:
        """Preprocess user input: clean and format."""
        content = message.content.strip()
        return Message(
            content=content,
            role=message.role,
            metadata=message.metadata,
        )
    
    def postprocess(self, message: Message) -> Message:
        """Postprocess AI output: format for display."""
        return Message(
            content=message.content,
            role=message.role,
            metadata=message.metadata,
        )
```

**Step 4: Update __init__.py**

Update `src/openbot/botflow/__init__.py`:

```python
from openbot.botflow.session import Session, SessionManager
from openbot.botflow.processor import MessageProcessor

__all__ = ["Session", "SessionManager", "MessageProcessor"]
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/botflow/test_processor.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/openbot/botflow/ tests/botflow/
git commit -m "feat: add MessageProcessor for BotFlow"
```

---

## Task 7: BotFlow Channel Router

**Files:**
- Create: `src/openbot/botflow/router.py`
- Create: `tests/botflow/test_router.py`

**Step 1: Write the failing test**

Create `tests/botflow/test_router.py`:

```python
import pytest
from openbot.botflow.router import ChannelRouter
from openbot.channels.base import ChatChannel, Message
from typing import AsyncIterator


class MockChannel(ChatChannel):
    def __init__(self, name: str):
        self.name = name
        self.started = False
        self.messages: list[Message] = []
    
    async def start(self) -> None:
        self.started = True
    
    async def send(self, message: Message) -> None:
        self.messages.append(message)
    
    async def receive(self) -> AsyncIterator[Message]:
        yield Message(content="test", role="user")
    
    async def stop(self) -> None:
        self.started = False


@pytest.mark.asyncio
async def test_router_register():
    router = ChannelRouter()
    channel = MockChannel("test")
    
    router.register("test", channel)
    assert "test" in router.channels


@pytest.mark.asyncio
async def test_router_start_all():
    router = ChannelRouter()
    channel = MockChannel("test")
    router.register("test", channel)
    
    await router.start_all()
    assert channel.started is True


@pytest.mark.asyncio
async def test_router_broadcast():
    router = ChannelRouter()
    channel1 = MockChannel("ch1")
    channel2 = MockChannel("ch2")
    router.register("ch1", channel1)
    router.register("ch2", channel2)
    
    msg = Message(content="hello", role="assistant")
    await router.broadcast(msg)
    
    assert len(channel1.messages) == 1
    assert len(channel2.messages) == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/botflow/test_router.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/openbot/botflow/router.py`:

```python
import asyncio
from openbot.channels.base import ChatChannel, Message


class ChannelRouter:
    def __init__(self):
        self.channels: dict[str, ChatChannel] = {}
    
    def register(self, name: str, channel: ChatChannel) -> None:
        """Register a channel with the router."""
        self.channels[name] = channel
    
    def unregister(self, name: str) -> None:
        """Unregister a channel from the router."""
        if name in self.channels:
            del self.channels[name]
    
    async def start_all(self) -> None:
        """Start all registered channels."""
        await asyncio.gather(*[ch.start() for ch in self.channels.values()])
    
    async def stop_all(self) -> None:
        """Stop all registered channels."""
        await asyncio.gather(*[ch.stop() for ch in self.channels.values()])
    
    async def broadcast(self, message: Message) -> None:
        """Broadcast a message to all channels."""
        await asyncio.gather(*[ch.send(message) for ch in self.channels.values()])
    
    def get_channel(self, name: str) -> ChatChannel | None:
        """Get a specific channel by name."""
        return self.channels.get(name)
```

**Step 4: Update __init__.py**

Update `src/openbot/botflow/__init__.py`:

```python
from openbot.botflow.session import Session, SessionManager
from openbot.botflow.processor import MessageProcessor
from openbot.botflow.router import ChannelRouter

__all__ = ["Session", "SessionManager", "MessageProcessor", "ChannelRouter"]
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/botflow/test_router.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/openbot/botflow/ tests/botflow/
git commit -m "feat: add ChannelRouter for BotFlow"
```

---

## Task 8: DeepAgents Core

**Files:**
- Create: `src/openbot/agents/__init__.py`
- Create: `src/openbot/agents/core.py`
- Create: `tests/agents/test_core.py`

**Step 1: Write the failing test**

Create `tests/agents/test_core.py`:

```python
import pytest
from openbot.agents.core import AgentCore
from openbot.config import LLMConfig


def test_agent_core_creation():
    config = LLMConfig(
        provider="openai",
        model="gpt-4o",
        api_key="test-key",
        temperature=0.7,
    )
    core = AgentCore(config)
    assert core.config == config
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents/test_core.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/openbot/agents/__init__.py`:

```python
from openbot.agents.core import AgentCore

__all__ = ["AgentCore"]
```

Create `src/openbot/agents/core.py`:

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from openbot.config import LLMConfig


class AgentCore:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._llm = self._create_llm()
        self._history: list[HumanMessage | AIMessage] = []
        self._system_prompt = "You are OpenBot, a helpful AI assistant."
    
    def _create_llm(self):
        if self.config.provider == "openai":
            return ChatOpenAI(
                model=self.config.model,
                api_key=self.config.api_key,
                temperature=self.config.temperature,
            )
        raise ValueError(f"Unsupported provider: {self.config.provider}")
    
    async def process(self, message: str) -> str:
        """Process a user message and return the complete response."""
        messages = [SystemMessage(content=self._system_prompt)]
        messages.extend(self._history)
        messages.append(HumanMessage(content=message))
        
        response = await self._llm.ainvoke(messages)
        
        self._history.append(HumanMessage(content=message))
        self._history.append(AIMessage(content=response.content))
        
        return response.content
    
    async def process_stream(self, message: str) -> AsyncIterator[str]:
        """Process a user message and return a streaming response."""
        messages = [SystemMessage(content=self._system_prompt)]
        messages.extend(self._history)
        messages.append(HumanMessage(content=message))
        
        # 保存完整响应的缓冲区
        full_response = []
        
        async for chunk in self._llm.astream(messages):
            content = chunk.content
            if content:
                full_response.append(content)
                yield content
        
        # 保存完整历史
        self._history.append(HumanMessage(content=message))
        self._history.append(AIMessage(content="".join(full_response)))
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history.clear()
    
    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt."""
        self._system_prompt = prompt
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents/test_core.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/openbot/agents/ tests/agents/
git commit -m "feat: add AgentCore with LangChain integration"
```

---

## Task 9: BotFlow Evolution Controller (Skeleton)

**Files:**
- Create: `src/openbot/botflow/evolution.py`
- Create: `tests/botflow/test_evolution.py`

**Step 1: Write the failing test**

Create `tests/botflow/test_evolution.py`:

```python
import pytest
from openbot.botflow.evolution import EvolutionController
from openbot.config import EvolutionConfig


def test_evolution_controller_creation():
    config = EvolutionConfig(enabled=True, require_approval=True)
    controller = EvolutionController(config)
    assert controller.enabled is True
    assert controller.require_approval is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/botflow/test_evolution.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/openbot/botflow/evolution.py`:

```python
from openbot.config import EvolutionConfig
from pydantic import BaseModel


class CodeChange(BaseModel):
    file_path: str
    old_content: str
    new_content: str
    description: str
    approved: bool = False


class EvolutionController:
    def __init__(self, config: EvolutionConfig):
        self.config = config
        self.enabled = config.enabled
        self.require_approval = config.require_approval
        self._pending_changes: list[CodeChange] = []
    
    def propose_change(self, change: CodeChange) -> bool:
        """Propose a code change for approval."""
        if not self.enabled:
            return False
        
        if not self.require_approval:
            change.approved = True
            return True
        
        self._pending_changes.append(change)
        return False
    
    def approve_change(self, change_id: int) -> bool:
        """Approve a pending change."""
        if 0 <= change_id < len(self._pending_changes):
            self._pending_changes[change_id].approved = True
            return True
        return False
    
    def get_pending_changes(self) -> list[CodeChange]:
        """Get all pending changes."""
        return [c for c in self._pending_changes if not c.approved]
```

**Step 4: Update __init__.py**

Update `src/openbot/botflow/__init__.py`:

```python
from openbot.botflow.session import Session, SessionManager
from openbot.botflow.processor import MessageProcessor
from openbot.botflow.router import ChannelRouter
from openbot.botflow.evolution import EvolutionController, CodeChange

__all__ = [
    "Session",
    "SessionManager",
    "MessageProcessor",
    "ChannelRouter",
    "EvolutionController",
    "CodeChange",
]
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/botflow/test_evolution.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/openbot/botflow/ tests/botflow/
git commit -m "feat: add EvolutionController skeleton for BotFlow"
```

---

## Task 10: CLI Main Entry Point

**Files:**
- Create: `src/openbot/main.py`
- Update: `src/openbot/__init__.py`

**Step 1: Write minimal implementation**

Create `src/openbot/main.py`:

```python
import argparse
import asyncio
import sys
from pathlib import Path

from openbot.config import Config, load_config, load_config_from_file
from openbot.channels.console import ConsoleChannel
from openbot.botflow import (
    ChannelRouter,
    MessageProcessor,
    SessionManager,
    EvolutionController,
)
from openbot.agents.core import AgentCore


class BotFlow:
    def __init__(self, config: Config):
        self.config = config
        self.router = ChannelRouter()
        self.session_manager = SessionManager()
        self.processor = MessageProcessor()
        self.agent = AgentCore(config.llm)
        self.evolution = EvolutionController(config.evolution)
    
    async def run(self) -> None:
        """Run the bot flow."""
        if self.config.channels.console.enabled:
            channel = ConsoleChannel(prompt=self.config.channels.console.prompt)
            self.router.register("console", channel)
        
        await self.router.start_all()
        
        session = self.session_manager.create(user_id="console-user")
        
        try:
            channel = self.router.get_channel("console")
            if channel:
                async for message in channel.receive():
                    processed = self.processor.preprocess(message)
                    # 使用流式处理
                    stream = self.agent.process_stream(processed.content)
                    await channel.send_stream(stream)
        finally:
            await self.router.stop_all()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OpenBot - A command-line AI bot with self-evolution capabilities"
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to configuration file (default: ./config.json)",
    )
    parser.add_argument(
        "--channel",
        type=str,
        default="console",
        help="Channel to use (default: console)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    config_path = Path(args.config) if args.config else Path("config.json")
    
    if config_path.exists():
        config = load_config_from_file(config_path)
    else:
        example_path = Path("examples/config.json")
        if example_path.exists():
            config = load_config_from_file(example_path)
        else:
            config = Config()
    
    botflow = BotFlow(config)
    
    try:
        asyncio.run(botflow.run())
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
```

**Step 2: Update __init__.py**

Update `src/openbot/__init__.py`:

```python
from openbot.config import Config, load_config, load_config_from_file
from openbot.channels import ChatChannel, Message, ConsoleChannel
from openbot.botflow import (
    Session,
    SessionManager,
    MessageProcessor,
    ChannelRouter,
    EvolutionController,
    CodeChange,
)
from openbot.agents import AgentCore

__all__ = [
    "Config",
    "load_config",
    "load_config_from_file",
    "ChatChannel",
    "Message",
    "ConsoleChannel",
    "Session",
    "SessionManager",
    "MessageProcessor",
    "ChannelRouter",
    "EvolutionController",
    "CodeChange",
    "AgentCore",
]

__version__ = "0.1.0"
```

**Step 3: Run type check**

Run: `mypy src/openbot/`

Expected: No errors (or only minor warnings)

**Step 4: Run all tests**

Run: `pytest tests/ -v`

Expected: All tests pass

**Step 5: Commit**

```bash
git add src/openbot/
git commit -m "feat: add CLI main entry point and integrate all modules"
```

---

## Task 11: Final Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

Create `tests/test_integration.py`:

```python
import pytest
from openbot import (
    Config,
    load_config,
    ConsoleChannel,
    ChannelRouter,
    SessionManager,
    MessageProcessor,
    AgentCore,
    LLMConfig,
)


@pytest.mark.asyncio
async def test_full_flow_setup():
    config = Config(
        llm=LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key="test-key",
        )
    )
    
    router = ChannelRouter()
    channel = ConsoleChannel(prompt="test> ")
    router.register("console", channel)
    
    session_manager = SessionManager()
    session = session_manager.create(user_id="test-user")
    
    processor = MessageProcessor()
    agent = AgentCore(config.llm)
    
    assert router.get_channel("console") is channel
    assert session.user_id == "test-user"
    assert agent.config.model == "gpt-4o"
```

**Step 2: Run integration test**

Run: `pytest tests/test_integration.py -v`

Expected: PASS

**Step 3: Run full test suite with coverage**

Run: `pytest tests/ -v --cov=src/openbot --cov-report=term-missing`

Expected: All tests pass with coverage report

**Step 4: Final commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for full flow"
```

---

## Summary

This plan implements the MVP version of OpenBot with:

1. **Configuration Module** - JSON config with environment variable substitution
2. **ChatChannel Layer** - Base class + ConsoleChannel for REPL
3. **BotFlow** - Router, Session, Processor, Evolution Controller
4. **AgentCore** - LangChain integration for LLM interaction
5. **CLI Entry** - Command-line interface with argument parsing

**Total: 11 tasks, ~30 steps**

---

**Plan complete and saved to `docs/plans/2026-02-19-openbot-implementation.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
