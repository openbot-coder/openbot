"""智能代理核心类"""

import os
import logging
import asyncio

import inspect
from pathlib import Path
from typing import Dict, Literal, List, Any, Callable, Optional
from langchain_core.messages import HumanMessage
from langchain.agents.middleware import (
    wrap_model_call,
    ModelRequest,
    ModelResponse,
    AgentMiddleware,
    TodoListMiddleware,
)
from langchain.chat_models import BaseChatModel
from langchain.agents import create_agent
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware

from langgraph.checkpoint.memory import InMemorySaver

from deepagents.backends import FilesystemBackend
from deepagents.middleware import (
    SkillsMiddleware,
    MemoryMiddleware,
    SummarizationMiddleware,
)
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware

from openbot.config import AgentConfig
from openbot.channels.base import ChatMessage, ContentType
from openbot.agents.tools import ToolsManager
from openbot.agents.system_prompt import DEFAULT_SYSTEM_PROMPT_V2
from openbot.agents.models import (
    ModelManager,
    get_current_time,
    remove_file,
    run_bash_command,
)


def get_summarization_defaults(model: BaseChatModel) -> Dict[str, Any]:
    """获取总结中间件默认参数"""

    has_profile = (
        model.profile is not None
        and isinstance(model.profile, dict)
        and "max_input_tokens" in model.profile
        and isinstance(model.profile["max_input_tokens"], int)
    )

    if has_profile:
        return {
            "trigger": ("fraction", 0.85),
            "keep": ("fraction", 0.10),
            "truncate_args_settings": {
                "trigger": ("fraction", 0.85),
                "keep": ("fraction", 0.10),
            },
        }
    return {
        "trigger": ("tokens", 170000),
        "keep": ("messages", 6),
        "truncate_args_settings": {
            "trigger": ("messages", 20),
            "keep": ("messages", 20),
        },
    }


class OpenBotExecutor:
    """OpenBot 智能体执行类 - 支持懒加载"""

    def __init__(self, model_configs: Dict[str, Any], agent_config: AgentConfig):
        self._agent_config = agent_config
        self._model_configs = model_configs
        self._model_manager = ModelManager(self._model_configs)
        self._tools_manager = ToolsManager()
        # 移除这里的同步加载，改为懒加载
        # self._tools_manager.load_tools_from_config(self._agent_config.mcp_config)
        self._agent = None
        self._initialized = False
        self._initializing = False
        self._init_error: Optional[Exception] = None

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    @property
    def is_initializing(self) -> bool:
        """检查是否正在初始化"""
        return self._initializing

    @property
    def init_error(self) -> Optional[Exception]:
        """获取初始化错误"""
        return self._init_error

    async def init_agent(self) -> None:
        """初始化智能体 - 懒加载方式"""
        if self._initialized:
            return

        if self._initializing:
            # 等待初始化完成
            while self._initializing:
                await asyncio.sleep(0.1)
            return

        self._initializing = True
        self._init_error = None

        try:
            await self._do_init()
            self._initialized = True
        except Exception as e:
            self._init_error = e
            logging.error(f"Agent initialization failed: {e}", exc_info=True)
            raise
        finally:
            self._initializing = False

    async def _do_init(self) -> None:
        """实际初始化逻辑"""
        # 获取默认模型
        try:
            futures = [
                asyncio.to_thread(self._model_manager.add_model, name, model_config)
                for name, model_config in self._model_configs.items()
            ]
            await asyncio.gather(*futures)
            model = self._model_manager.get_model(self._agent_config.default_model)
            if model is None:
                raise ValueError(
                    f"Model {self._agent_config.default_model} not found in model_configs"
                )

            logging.info(f"☑️ Using model: {self._agent_config.default_model}")
        except Exception as e:
            logging.error(
                f"❌ Failed to get model: {self._agent_config.default_model}, {str(e)}"
            )
            raise e

        try:
            # 初始化工具管理器
            self._tools_manager.load_tools_from_config(self._agent_config.mcp_config)
            tools = await self._tools_manager.get_tools()
            tools.extend([get_current_time, remove_file, run_bash_command])
            logging.info(f"☑️ Using tools: {len(tools)}")
        except Exception as e:
            logging.error(
                f"❌ Failed to load tools from config: {self._agent_config.mcp_config}, {str(e)}"
            )
            raise e

        try:
            # 设置 OPENBOT_WORKSPACE 环境变量，供工具使用
            os.environ["OPENBOT_WORKSPACE"] = self._agent_config.workspace

            # 初始化backend - workspace 现在已经是绝对路径
            backend = FilesystemBackend(
                root_dir=self._agent_config.workspace,
                virtual_mode=False,
            )
            logging.info(
                f"☑️ Using backend({self._agent_config.workspace}):  {backend}"
            )
        except Exception as e:
            logging.error(
                f"❌ Failed to create backend: {self._agent_config.workspace}, {str(e)}"
            )
            raise e

        try:
            summarization_defaults = get_summarization_defaults(model)
            gp_middleware: list[AgentMiddleware[Any, Any, Any]] = [
                TodoListMiddleware(),
                FilesystemMiddleware(backend=backend),
                SummarizationMiddleware(
                    model=model,
                    backend=backend,
                    trigger=summarization_defaults["trigger"],
                    keep=summarization_defaults["keep"],
                    trim_tokens_to_summarize=None,
                    truncate_args_settings=summarization_defaults[
                        "truncate_args_settings"
                    ],
                ),
                SkillsMiddleware(backend=backend, sources=self._agent_config.skills),
                AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
                PatchToolCallsMiddleware(),
                MemoryMiddleware(
                    backend=backend,
                    sources=[
                        "memory/USER.MD",
                        "memory/AGENT.md",
                        "memory/progress.md",
                        "memory/memory.md",
                    ],
                ),
            ]
        except Exception as e:
            logging.error(f"❌ Failed to create gp middleware: {str(e)}")
            raise e

        try:
            self._agent = create_agent(
                model=model,
                tools=tools,
                middleware=gp_middleware,
                system_prompt=DEFAULT_SYSTEM_PROMPT_V2.format(
                    workspace=self._agent_config.workspace
                ),
                checkpointer=InMemorySaver(),
                debug=self._agent_config.debug,
            )
        except Exception as e:
            logging.error(f"❌ Failed to create agent: {str(e)}")
            raise e

    async def ensure_initialized(self) -> None:
        """确保已初始化，如未初始化则自动初始化"""
        if not self._initialized:
            await self.init_agent()

    @property
    def model_manager(self) -> ModelManager:
        """获取模型管理器"""
        return self._model_manager

    @property
    def agent(self) -> Any:
        """获取智能代理"""
        return self._agent

    def chat(
        self,
        message: ChatMessage,
        streaming_callback: Callable[[ChatMessage], None] | None = None,
    ) -> List[ChatMessage]:
        """与用户进行对话(同步) - 自动初始化"""
        # 同步方式需要运行异步初始化
        if not self._initialized:
            asyncio.run(self.ensure_initialized())

        message.content = message.content.strip()
        reply_messages = []
        for chunk in self.agent.stream(
            {"messages": [{"role": message.role, "content": message.content}]},
            config={"configurable": {"thread_id": message.channel_id}},
            stream_mode="updates",
            debug=self._agent_config.debug,
        ):
            chunk_reply_messages = self._handle_message_chunk(
                chunk, message, streaming_callback
            )
            if chunk_reply_messages:
                reply_messages.extend(chunk_reply_messages)
        return reply_messages

    def _handle_message_chunk(
        self,
        chunk: dict,
        message: ChatMessage,
        streaming_callback: Callable[[ChatMessage], None] | None = None,
    ) -> List[ChatMessage]:
        """处理消息块"""
        reply_messages = []
        for step, data in chunk.items():

            if step in ["model", "tools"] and "messages" in data:
                raw_reply_message = data["messages"][-1]
                if isinstance(raw_reply_message, HumanMessage):
                    continue

                # 对于工具调用，添加更清晰的标识
                content = raw_reply_message.content
                if step == "tools" and content:
                    content = f"CallTools [{content}]"

                reply_message = ChatMessage(
                    channel_id=message.channel_id,
                    msg_id=raw_reply_message.id,
                    content=content,
                    role="bot",
                    content_type=ContentType.TEXT,
                    metadata={"step": step},
                )
                if callable(streaming_callback):
                    streaming_callback(reply_message)
                reply_messages.append(reply_message)

            else:
                # 只显示重要的中间步骤
                if not any(
                    skip in step
                    for skip in [
                        "TodoList",
                        "PatchToolCalls",
                        "Filesystem",
                        "Summarization",
                    ]
                ):
                    stepmessage = ChatMessage(
                        channel_id=message.channel_id,
                        content=f"processing step: {step}...",
                        role="bot",
                        content_type=ContentType.TEXT,
                        metadata={"step": step},
                    )
                    if callable(streaming_callback):
                        streaming_callback(stepmessage)
        return reply_messages

    async def achat(
        self,
        message: ChatMessage,
        streaming_callback: Callable[[ChatMessage], None] | None = None,
        max_retries: int = 3,
    ) -> List[ChatMessage]:
        """与用户进行对话 - 自动初始化，支持工具调用重试"""
        # 确保已初始化
        await self.ensure_initialized()

        message.content = message.content.strip()
        reply_messages = []

        last_exception = None
        delay = 1.0

        for attempt in range(max_retries + 1):
            try:
                async for chunk in self.agent.astream(
                    {"messages": [{"role": message.role, "content": message.content}]},
                    config={"configurable": {"thread_id": message.channel_id}},
                    stream_mode="updates",
                    debug=self._agent_config.debug,
                ):
                    chunk_reply_messages = self._handle_message_chunk(
                        chunk, message, streaming_callback
                    )
                    if chunk_reply_messages:
                        reply_messages.extend(chunk_reply_messages)

                # 成功完成，返回结果
                return reply_messages

            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()

                # 检查是否是工具调用错误
                is_tool_error = any(
                    err in error_msg
                    for err in [
                        "error executing tool",
                        "tool",
                        "fetch_content",
                        "httpx",
                    ]
                )

                if is_tool_error and attempt < max_retries:
                    logging.warning(
                        f"Tool call failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    # 通知用户正在重试
                    if callable(streaming_callback):
                        retry_message = ChatMessage(
                            channel_id=message.channel_id,
                            content=f"工具调用失败，正在重试 ({attempt + 1}/{max_retries})...",
                            role="bot",
                            content_type=ContentType.TEXT,
                            metadata={"step": "retry"},
                        )
                        streaming_callback(retry_message)

                    await asyncio.sleep(delay)
                    delay *= 2.0  # 指数退避
                else:
                    # 非工具错误或已达到最大重试次数
                    logging.error(f"Chat failed after {attempt + 1} attempts: {e}")
                    raise

        # 所有重试都失败了
        raise last_exception


if __name__ == "__main__":
    import asyncio
    import os
    from openbot.config import ConfigManager
    from vxutils import loggerConfig

    loggerConfig(level=logging.INFO)
    config_path = os.environ.get("OPENBOT_CONFIG_PATH", "config/config.json")
    config_manager = ConfigManager(config_path)
    config = config_manager.config
    agent_config = config.agent_config
    model_configs = config.model_configs
    print(model_configs)
    agent_core = OpenBotExecutor(model_configs, agent_config)

    def on_message(message: ChatMessage) -> ChatMessage | None:
        step = message.metadata.get("step", "")
        if step == "model":
            print(f"bot   > {message.content}")
        elif step == "tools":
            print(f"tools > {message.content}")
        else:
            print(f"system > {message.content}")
        return message

    while True:
        message = input("请输入: ")

        chatmessage = ChatMessage(
            channel_id="123",
            content=message,
            role="user",
            content_type=ContentType.TEXT,
        )
        reply_messages = agent_core.chat(
            chatmessage,
            streaming_callback=on_message,
        )
