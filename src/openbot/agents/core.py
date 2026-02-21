import logging
import pathlib
from datetime import datetime
from typing import Dict, Literal, List, Union, Any, Callable
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
    SystemMessage,
    AnyMessage,
)
from deepagents.backends import FilesystemBackend
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent
from openbot.config import ModelConfig, AgentConfig
from openbot.channels.base import ChatMessage, ContentType


def get_current_time() -> str:
    """获取当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class AgentCore:
    def __init__(self, model_configs: Dict[str, Any], agent_config: AgentConfig):
        self._agent_config = agent_config
        # self._agent_config.tools.append(get_current_time)
        self._model_configs = model_configs
        self._chat_models = {}
        self._agent = None
        self._init_agent()

    def _init_agent(self):
        """初始化 LLM 代理"""
        self._chat_models = {}
        model_items = list(self._model_configs.items())
        logging.info(f"Initializing {len(model_items)} LLM Models...")

        for name, model_config in model_items:
            try:
                chat_model = init_chat_model(**model_config.model_dump())
                if chat_model:
                    reply = chat_model.invoke("hello,my name is OpenBot,I'm on it now")
                    logging.info(f"Successfully initialized model {name}: {reply}")
                    self._chat_models[name] = chat_model
                else:
                    logging.error(f"Error initializing model {name}: {model_config}")
            except Exception as e:
                logging.error(
                    f"Error initializing model {name}: {model_config}, error: {e}"
                )
        model = self.get_chat_models("auto")
        tools = [get_current_time]
        memory = self._agent_config.memory
        skills = self._agent_config.skills
        backend = FilesystemBackend(root_dir=pathlib.Path("./.trae").absolute())

        self._agent = create_deep_agent(
            model,
            tools=tools,
            memory=memory,
            skills=skills,
            backend=backend,
        )
        return self._agent

    def get_chat_models(
        self, strategy: Literal["auto", "manual"], name: str = ""
    ) -> BaseChatModel | None:
        """获取 LLM 模型"""
        if strategy == "auto":
            return list(self._chat_models.values())[0]
        elif strategy == "manual" and name:
            return self._chat_models.get(name, None)
        else:
            return None

    async def chat(
        self,
        message: ChatMessage,
        streaming_callback: Callable[[ChatMessage], None] | None = None,
    ) -> List[ChatMessage]:
        """与用户进行对话"""
        message.content = message.content.strip()
        reply_messages = []
        async for chunk in self._agent.astream(
            {"messages": [{"role": message.role, "content": message.content}]},
            config={"configurable": {"thread_id": message.channel_id}},
            stream_mode="updates",
            debug=self._agent_config.debug,
        ):
            for step, data in chunk.items():
                if step in ["model", "tool"] and "messages" in data:
                    raw_reply_message = data["messages"][-1]
                    if isinstance(raw_reply_message, HumanMessage):
                        continue

                    reply_message = ChatMessage(
                        channel_id=message.channel_id,
                        msg_id=raw_reply_message.id,
                        content=raw_reply_message.content,
                        role="bot",
                        content_type=ContentType.TEXT,
                        metadata={"step": step},
                    )
                    if callable(streaming_callback):
                        await streaming_callback(reply_message)
                    reply_messages.append(reply_message)
        return reply_messages


if __name__ == "__main__":
    import asyncio
    from openbot.config import ConfigManager
    from vxutils import loggerConfig

    loggerConfig(level=logging.WARNING)
    config_path = (
        "C:\\Users\\shale\\Documents\\trae_projects\\openbot\\examples\\config.json"
    )
    config_manager = ConfigManager(config_path)
    config = config_manager.config
    agent_config = config.agent_config
    model_configs = config.model_configs
    agent_core = AgentCore(model_configs, agent_config)

    async def callback(msg: ChatMessage):
        if msg:
            print(f"{msg.content}")
        else:
            print(f"None")

    while True:
        message = input("请输入: ")
        chatmessage = ChatMessage(
            channel_id="123",
            content=message,
            role="user",
            content_type=ContentType.TEXT,
        )
        reply_messages = asyncio.run(
            agent_core.chat(
                chatmessage,
                streaming_callback=callback,
            )
        )

        # print(reply_messages)
        # for reply_message in reply_messages:
        #    print(reply_message.content)
