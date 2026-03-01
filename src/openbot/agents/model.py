import logging
import asyncio
import random
from typing import Dict, Any, Union, Callable, Optional
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain.agents.middleware import (
    ModelRequest,
    ModelResponse,
    AgentMiddleware,
)
from langchain_core.callbacks import UsageMetadataCallbackHandler
from openbot.common.config import ModelConfig


class DynamicModelSelector(AgentMiddleware):
    """动态模型选择器"""

    def __init__(self):
        """初始化模型管理器"""
        self._default_model = ""
        self._chat_models = {}
        self._usage_callback = UsageMetadataCallbackHandler()

    def set_default_model(self, name: str) -> None:
        """设置默认模型"""
        self._default_model = name

    async def add_model(
        self,
        name: str,
        model: Union[BaseChatModel, ModelConfig],
        is_default: bool = False,
    ) -> None:
        """添加模型"""
        if isinstance(model, ModelConfig):
            try:
                model = await asyncio.to_thread(init_chat_model, **model.model_dump())
            except Exception as e:
                logging.error(f"Error loading model {name}: {e}")
                return

        if model is None or not isinstance(model, BaseChatModel):
            logging.error(f"Invalid model {name}")
            return

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

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        model_name = request.runtime.context.model or self._default_model
        model = self.get_model(name=model_name)
        return handler(request.override(model=model))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        # 安全获取模型名称，处理 context 为 None 的情况
        model_name = None
        if request.runtime.context:
            model_name = getattr(request.runtime.context, "model", None)
        model_name = model_name or self._default_model
        model = self.get_model(name=model_name)
        return await handler(request.override(model=model))


async def init_modelselector(
    model_configs: Dict[str, ModelConfig], default_model: str
) -> DynamicModelSelector:
    """初始化模型选择器"""
    model_selector = DynamicModelSelector()
    tasks = []
    for name, model_config in model_configs.items():
        task = asyncio.create_task(model_selector.add_model(name, model_config))
        tasks.append(task)
    await asyncio.gather(*tasks)
    model_selector.set_default_model(default_model)
    return model_selector


if __name__ == "__main__":
    from vxutils import timer, loggerConfig
    import os

    loggerConfig()

    # 从环境变量获取 API 密钥，或使用占位符
    model_configs = {
        "doubao-seed": ModelConfig(
            **{
                "model_provider": "openai",
                "model": "ark-code-latest",
                "api_key": os.environ.get("DOUBAO_SEED_API_KEY", "your-api-key-here"),
                "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
                "temperature": 0.7,
            }
        ),
        "mimo-v2-flash": ModelConfig(
            **{
                "model_provider": "openai",
                "model": "mimo-v2-flash",
                "api_key": os.environ.get("MIMO_V2_FLASH_API_KEY", "your-api-key-here"),
                "base_url": "https://api.xiaomimimo.com/v1",
                "temperature": 0.5,
            }
        ),
        "glm-4.7-flash": ModelConfig(
            **{
                "model_provider": "openai",
                "model": "glm-4.7-flash",
                "api_key": os.environ.get("GLM_4_7_FLASH_API_KEY", "your-api-key-here"),
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "temperature": 0.1,
            }
        ),
    }

    with timer(verbose=True):
        model_selector = asyncio.run(init_modelselector(model_configs))
    print(list(model_selector.list_models().keys()))
