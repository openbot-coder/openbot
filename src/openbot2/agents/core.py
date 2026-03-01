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
from openbot.botflow.database import ChatMessage, ContentType
from openbot.agents.tools import ToolsManager
from openbot.agents.system_prompt import DEFAULT_SYSTEM_PROMPT_V2
from openbot.agents.models import (
    ModelManager,
    get_current_time,
    remove_file,
    run_bash_command,
)
from openbot.agents.base import Answer, DetailAnswer, SimpleAnswer
from openbot.agents.message_queue import MessageQueue

import sys

# 确保当前目录在Python路径中
sys.path.append(".")


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


class Worker:
    """Worker类，用于处理任务"""

    def __init__(
        self,
        worker_id: str,
        message_queue: MessageQueue,
        model_manager: ModelManager,
        tools_manager: ToolsManager,
        agent_config: AgentConfig,
    ):
        self.worker_id = worker_id
        self.message_queue = message_queue
        self.model_manager = model_manager
        self.tools_manager = tools_manager
        self.agent_config = agent_config
        self._agent = None
        self._running = False

    async def initialize(self):
        """初始化worker"""
        # 加载工具
        self.tools_manager.load_tools_from_config(self.agent_config.mcp_config)

        # 获取默认模型
        model = self.model_manager.get_model(self.agent_config.default_model)
        if model is None:
            raise ValueError(
                f"Model {self.agent_config.default_model} not found in model_configs"
            )

        # 初始化工具
        tools = await self.tools_manager.get_tools()
        tools.extend([get_current_time, remove_file, run_bash_command])

        # 设置 OPENBOT_WORKSPACE 环境变量，供工具使用
        os.environ["OPENBOT_WORKSPACE"] = self.agent_config.workspace

        # 初始化backend - workspace 现在已经是绝对路径
        backend = FilesystemBackend(
            root_dir=self.agent_config.workspace,
            virtual_mode=False,
        )

        # 初始化中间件
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
                truncate_args_settings=summarization_defaults["truncate_args_settings"],
            ),
            SkillsMiddleware(backend=backend, sources=self.agent_config.skills),
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

        # 创建智能体
        self._agent = create_agent(
            model=model,
            tools=tools,
            middleware=gp_middleware,
            system_prompt=DEFAULT_SYSTEM_PROMPT_V2.format(
                workspace=self.agent_config.workspace
            ),
            checkpointer=InMemorySaver(),
            debug=self.agent_config.debug,
        )

    async def start(self):
        """启动worker"""
        self._running = True
        await self.initialize()
        asyncio.create_task(self._process_tasks())

    async def stop(self):
        """停止worker"""
        self._running = False

    async def _process_tasks(self):
        """处理任务"""
        while self._running:
            try:
                task = await self.message_queue.get()
                try:
                    # 处理任务
                    result = await self._handle_task(task)
                    # 设置任务结果
                    self.message_queue.set_task_result(task["task_id"], result)
                except Exception as e:
                    # 设置任务异常
                    self.message_queue.set_task_exception(task["task_id"], e)
                finally:
                    # 标记任务完成
                    self.message_queue.task_done()
            except Exception as e:
                logging.error(f"Worker {self.worker_id} error: {e}")
                await asyncio.sleep(1)

    async def _handle_task(self, task: Dict[str, Any]) -> Answer:
        """处理单个任务"""
        question = task.get("question")
        stream = task.get("stream", False)
        trigger = task.get("trigger")

        # 创建ChatMessage
        message = ChatMessage(
            channel_id=task.get("channel_id", "default"),
            content=question,
            role="user",
            content_type=ContentType.TEXT,
        )

        # 处理消息
        if stream:
            # 流式处理
            reply_messages = []
            async for chunk in self._agent.astream(
                {"messages": [{"role": message.role, "content": message.content}]},
                config={"configurable": {"thread_id": message.channel_id}},
                stream_mode="updates",
                debug=self.agent_config.debug,
            ):
                chunk_reply_messages = self._handle_message_chunk(chunk, message, None)
                if chunk_reply_messages:
                    reply_messages.extend(chunk_reply_messages)
        else:
            # 非流式处理
            result = await self._agent.ainvoke(
                {"messages": [{"role": message.role, "content": message.content}]},
                config={"configurable": {"thread_id": message.channel_id}},
                debug=self.agent_config.debug,
            )
            # 处理结果
            reply_messages = []
            if "messages" in result:
                for msg in result["messages"]:
                    if not isinstance(msg, HumanMessage):
                        reply_message = ChatMessage(
                            channel_id=message.channel_id,
                            content=msg.content,
                            role="bot",
                            content_type=ContentType.TEXT,
                            metadata={"finish": True},
                        )
                        reply_messages.append(reply_message)

        # 生成回答
        if reply_messages:
            final_message = reply_messages[-1]
            # 根据内容长度决定返回DetailAnswer还是SimpleAnswer
            if len(final_message.content) > 500:
                return DetailAnswer(
                    content=final_message.content, metadata=final_message.metadata
                )
            else:
                return SimpleAnswer(content=final_message.content)
        else:
            return SimpleAnswer(content="抱歉，我无法生成回复。")


class OpenBotExecutor:
    """OpenBot 智能体执行类 - 支持懒加载和消息队列"""

    def __init__(self, model_configs: Dict[str, Any], agent_config: AgentConfig):
        self._agent_config = agent_config
        self._model_configs = model_configs
        self._model_manager = ModelManager(self._model_configs)
        self._tools_manager = ToolsManager()
        self._message_queue = MessageQueue()
        self._workers: List[Worker] = []
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

        # 初始化worker
        try:
            # 创建worker
            worker_count = 3  # 默认3个worker
            for i in range(worker_count):
                worker = Worker(
                    worker_id=f"worker-{i + 1}",
                    message_queue=self._message_queue,
                    model_manager=self._model_manager,
                    tools_manager=self._tools_manager,
                    agent_config=self._agent_config,
                )
                self._workers.append(worker)
                await worker.start()
            logging.info(f"☑️ Started {len(self._workers)} workers")
        except Exception as e:
            logging.error(f"❌ Failed to start workers: {str(e)}")
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
        return None  # 不再直接暴露agent，而是通过worker处理

    async def ask(
        self,
        question: str,
        stream: bool = False,
        trigger: Optional[Any] = None,
        channel_id: str = "default",
    ) -> Answer:
        """向智能体提问 - 主要外部接口"""
        # 确保已初始化
        await self.ensure_initialized()

        # 创建任务
        task = {
            "question": question,
            "stream": stream,
            "trigger": trigger,
            "channel_id": channel_id,
        }

        # 放入消息队列
        task_id = await self._message_queue.put(task)

        # 创建任务的Future
        future = self._message_queue.create_task_future(task_id)

        # 等待任务完成
        try:
            result = await future
            return result
        except Exception as e:
            logging.error(f"Ask failed: {e}")
            # 返回错误回答
            return SimpleAnswer(content=f"抱歉，处理您的请求时出错：{str(e)}")

    def chat(
        self,
        message: ChatMessage,
        streaming_callback: Callable[[ChatMessage], None] | None = None,
    ) -> List[ChatMessage]:
        """与用户进行对话(同步) - 自动初始化"""
        # 同步方式需要运行异步初始化
        if not self._initialized:
            asyncio.run(self.ensure_initialized())

        # 转换为ask方法调用
        async def _chat():
            answer = await self.ask(
                question=message.content, stream=True, channel_id=message.channel_id
            )
            # 转换Answer为ChatMessage
            chat_message = ChatMessage(
                channel_id=message.channel_id,
                content=answer.to_dict()["content"],
                role="bot",
                content_type=ContentType.TEXT,
                metadata={"finish": True},
            )
            return [chat_message]

        return asyncio.run(_chat())

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

                # 检查是否是最终回复
                is_finish = step == "model" and not any(
                    chunk for chunk in chunk.values() if "tools" in chunk
                )
                reply_message = ChatMessage(
                    channel_id=message.channel_id,
                    msg_id=raw_reply_message.id,
                    content=content,
                    role="bot",
                    content_type=ContentType.TEXT,
                    metadata={
                        "step": step,
                        "is_finish": is_finish,
                        "finish": is_finish,
                    },
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
                    reply_messages.append(stepmessage)
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

        # 使用新的ask方法
        answer = await self.ask(
            question=message.content, stream=True, channel_id=message.channel_id
        )

        # 转换Answer为ChatMessage
        chat_message = ChatMessage(
            channel_id=message.channel_id,
            content=answer.to_dict()["content"],
            role="bot",
            content_type=ContentType.TEXT,
            metadata={"finish": True},
        )

        return [chat_message]

    async def get_full_response(
        self,
        message: ChatMessage,
        max_retries: int = 3,
    ) -> ChatMessage:
        """获取完整的回复消息 - 适合微信等需要一次性发送完整消息的场景"""
        # 确保已初始化
        await self.ensure_initialized()

        message.content = message.content.strip()

        # 使用新的ask方法
        answer = await self.ask(
            question=message.content, stream=False, channel_id=message.channel_id
        )

        # 转换Answer为ChatMessage
        chat_message = ChatMessage(
            channel_id=message.channel_id,
            content=answer.to_dict()["content"],
            role="bot",
            content_type=ContentType.TEXT,
            metadata={"finish": True},
        )

        return chat_message


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

    async def main():
        # 初始化智能体
        await agent_core.init_agent()
        print("Agent initialized successfully")

        while True:
            message = input("请输入: ")
            if message.lower() == "exit":
                break

            # 使用新的ask方法
            print("Processing...")
            answer = await agent_core.ask(question=message, stream=False)
            print(f"Bot: {answer.to_dict()['content']}")
            print(f"Answer type: {answer.to_dict()['type']}")

    asyncio.run(main())
