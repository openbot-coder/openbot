import os
import random
from pathlib import Path
from typing import Dict, Any, Union, Literal, Callable, Tuple
from langchain.agents import create_agent

from langchain.chat_models import init_chat_model
from deepagents.middleware import SummarizationMiddleware
from langchain_core.language_models import BaseChatModel
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import (
    wrap_model_call,
    ModelRequest,
    ModelResponse,
    AgentMiddleware,
    TodoListMiddleware,
)
from deepagents.middleware import SkillsMiddleware, MemoryMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from vxutils import timer
from openbot.agents.system_prompt import DEFAULT_SYSTEM_PROMPT_V2
from openbot.config import AgentConfig, ModelConfig
from openbot.agents.tools import get_current_time, run_bash_command, remove_file


class ModelManager:
    """模型管理器核心类"""

    def __init__(
        self, strategy: Literal["auto", "manual"] = "auto", default_model: str = ""
    ):
        """初始化模型管理器"""
        self._default_model = default_model
        self._strategy = strategy
        self._chat_models = {}

    def add_model(
        self,
        name: str,
        model: Union[BaseChatModel, ModelConfig],
        is_default: bool = False,
    ) -> None:
        """添加模型"""
        if isinstance(model, ModelConfig):
            model = init_chat_model(**model.model_dump())
        self._chat_models[name] = model
        if is_default or (not self._default_model):
            self._default_model = name

    def get_model(self, name: str = None) -> BaseChatModel:
        """获取模型"""
        if name is None:
            name = self._default_model
        elif name == "auto":
            name = random.choice(
                list(name for name in self._chat_models if name != self._default_model)
            )
        return self._chat_models.get(name, None)

    def list_models(self) -> Dict[str, Any]:
        """列出所有已加载的模型"""
        return self._chat_models

    def compute_summarization_defaults(self) -> dict:
        """计算总结默认参数"""
        model = self.get_model()
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


def create_bot(
    model_configs: Dict[str, ModelConfig], agent_config: AgentConfig
) -> Tuple[ModelManager, Any]:
    """创建智能代理"""

    model_manager = ModelManager(default_model=agent_config.default_model)
    for name, model in model_configs.items():
        model_manager.add_model(name, model)

    model = model_manager.get_model()
    workspace = agent_config.workspace
    # workspace 现在已经是绝对路径（由 ConfigManager 解析）
    backend = FilesystemBackend(root_dir=workspace, virtual_mode=False)
    skills = agent_config.skills
    summarization_defaults = model_manager.compute_summarization_defaults()

    @wrap_model_call
    def auto_model_selection(
        request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        """自动选择模型"""

        message_count = len(request.state["messages"])
        # 如果消息数量超过10条，随机选择一个模型
        if message_count > 10:
            model = model_manager.get_model("auto")
        else:
            model = model_manager.get_model()
        new_request = request.override(model=model)
        return handler(new_request)

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
        # auto_model_selection,
    ]
    if skills:
        gp_middleware.append(SkillsMiddleware(backend=backend, sources=skills))
    agent = create_agent(
        system_prompt=DEFAULT_SYSTEM_PROMPT_V2.format(workspace=agent_config.workspace),
        model=model_manager.get_model(),
        tools=[get_current_time, run_bash_command],
        middleware=gp_middleware,
        checkpointer=InMemorySaver(),
    )
    return model_manager, agent


if __name__ == "__main__":
    import logging
    from openbot.config import ConfigManager
    from vxutils import loggerConfig

    loggerConfig(level=logging.INFO)

    config_manager = ConfigManager("./config/config.json")
    config = config_manager.get()
    model_manager, agent = create_bot(config.model_configs, config.agent_config)

    while True:
        msg = input("请输入: ")

        if msg:
            for chunk in agent.stream(
                {"messages": [{"role": "user", "content": msg}]},
                {"configurable": {"thread_id": "1"}},
                stream_mode="updates",
            ):
                for step, messages in chunk.items():
                    if not messages:
                        continue
                    if step not in ["model", "tools"]:
                        print(step, "...")
                    else:
                        message = messages["messages"][-1]
                        if message.content:
                            print(step, message.content)

            print("\n")
        else:
            break
