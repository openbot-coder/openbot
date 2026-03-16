from typing import Dict, Type, Tuple, Union, List, Any, Sequence, Optional, AsyncGenerator, Literal

from agentscope.model import (
    ChatModelBase,
    ChatResponse,
    OpenAIChatModel,
    AnthropicChatModel,
    DashScopeChatModel,
    GeminiChatModel,
    OllamaChatModel,
)
from agentscope.formatter import (
    FormatterBase,
    OpenAIChatFormatter,
    AnthropicChatFormatter,
    DashScopeChatFormatter,
    GeminiChatFormatter,
    OllamaChatFormatter,
)
from openbot.config import ModelConfig
from openbot.utils.tool_messages_utils import _sanitize_tool_messages


class ModelManager(ChatModelBase):
    """模型管理类 - 同时作为 ChatModelBase 使用

    该类继承自 ChatModelBase，可以直接作为聊天模型实例使用。
    同时保留了管理多个模型配置的能力。

    使用方式：
        1. 作为单个模型使用（推荐）：
            manager = ModelManager(model_configs, default_model_id="gpt-4o")
            response = await manager(messages)

        2. 获取特定模型：
            model, formatter = manager.build_chatmodel("gpt-4o")

    Args:
        model_configs: 模型配置字典，key 为 model_id
        default_model_id: 默认使用的模型 ID，默认为第一个配置的模型
    """

    _MODEL_MAP: Dict[str, Type[ChatModelBase]] = {
        "openai": OpenAIChatModel,
        "anthropic": AnthropicChatModel,
        "dashscope": DashScopeChatModel,
        "gemini": GeminiChatModel,
        "ollama": OllamaChatModel,
    }

    _FORMATTER_MAP: Dict[str, Type[FormatterBase]] = {
        "openai": OpenAIChatFormatter,
        "anthropic": AnthropicChatFormatter,
        "dashscope": DashScopeChatFormatter,
        "gemini": GeminiChatFormatter,
        "ollama": OllamaChatFormatter,
    }

    def __init__(
        self,
        model_configs: Dict[str, ModelConfig],
        default_model_id: Optional[str] = None,
    ):
        # 确定默认模型
        if default_model_id is None and model_configs:
            default_model_id = next(iter(model_configs))
        
        # 获取默认模型配置用于初始化父类
        default_cfg = model_configs.get(default_model_id) if default_model_id else None
        
        # 调用父类初始化
        super().__init__(
            model_name=default_cfg.model if default_cfg else "",
            stream=default_cfg.stream if default_cfg else False,
        )
        
        self._model_configs = model_configs
        self._active_models: Dict[str, ChatModelBase] = {}
        self._formatters: Dict[str, FormatterBase] = {}
        self._default_model_id: Optional[str] = default_model_id
        self._formatter_cache: Dict[Type[FormatterBase], Type[FormatterBase]] = {}

    @property
    def default_model_id(self) -> Optional[str]:
        """获取默认模型 ID"""
        return self._default_model_id

    @property
    def available_models(self) -> List[str]:
        """获取所有可用的模型 ID 列表"""
        return list(self._model_configs.keys())

    def _create_model_and_formatter(
        self, cfg: ModelConfig
    ) -> Tuple[ChatModelBase, FormatterBase]:
        """Create a model instance and its enhanced formatter."""
        provider_type = cfg.provider.lower()
        model_cls = self._MODEL_MAP[provider_type]
        formatter_cls = self._FORMATTER_MAP.get(provider_type, OpenAIChatFormatter)

        # Prepare model configuration
        model_kwargs = {
            "model_name": cfg.model,
            "api_key": cfg.api_key,
            "stream": cfg.stream,
        }

        # Inject optional parameters
        if cfg.base_url:
            model_kwargs["client_kwargs"] = {"base_url": cfg.base_url}

        # Initialize generate_kwargs and client_kwargs
        generate_kwargs = cfg.generate_kwargs.copy() if cfg.generate_kwargs else {}
        client_kwargs = cfg.client_kwargs.copy() if cfg.client_kwargs else {}

        # Merge explicit parameters into generate_kwargs/client_kwargs
        if cfg.max_tokens:
            generate_kwargs["max_tokens"] = cfg.max_tokens
        if cfg.temperature is not None:
            generate_kwargs["temperature"] = cfg.temperature

        if generate_kwargs:
            model_kwargs["generate_kwargs"] = generate_kwargs
        if client_kwargs:
            model_kwargs.setdefault("client_kwargs", {}).update(client_kwargs)

        # Instantiate model
        model = model_cls(**model_kwargs)

        # Create enhanced formatter
        enhanced_formatter_cls = self._get_enhanced_formatter_class(formatter_cls)
        formatter = enhanced_formatter_cls()

        return model, formatter

    def _get_enhanced_formatter_class(
        self, base_cls: Type[FormatterBase]
    ) -> Type[FormatterBase]:
        """Create or retrieve a formatter class enhanced with file block support and sanitization."""
        if base_cls in self._formatter_cache:
            return self._formatter_cache[base_cls]

        class EnhancedFormatter(base_cls):
            """Formatter enhanced with file block support and message sanitization."""

            async def _format(self, msgs: List[Any]) -> Any:
                """Sanitize messages before standard formatting."""
                sanitized_msgs = _sanitize_tool_messages(msgs)
                return await super()._format(sanitized_msgs)

            @staticmethod
            def convert_tool_result_to_string(
                output: Union[str, List[Dict[str, Any]]],
            ) -> Tuple[str, Sequence[Tuple[str, Dict[str, Any]]]]:
                """Extend conversion logic to support 'file' blocks in tool results."""
                if isinstance(output, str):
                    return output, []

                # Proactively check if there are any 'file' blocks
                has_file_block = any(
                    isinstance(block, dict) and block.get("type") == "file"
                    for block in output
                )

                if not has_file_block:
                    try:
                        return base_cls.convert_tool_result_to_string(output)
                    except ValueError:
                        # If base class fails, we still try our custom logic below
                        pass

                # Handle custom 'file' block type and other blocks
                textual_parts = []
                multimodal_data = []

                for block in output:
                    if not isinstance(block, dict) or "type" not in block:
                        if isinstance(block, str):
                            textual_parts.append(block)
                        continue

                    if block["type"] == "file":
                        path = block.get("path") or block.get("url", "unknown")
                        name = block.get("name", path)
                        textual_parts.append(f"File returned: '{name}' at {path}")
                        multimodal_data.append((path, block))
                    else:
                        # Delegate other types back to base class (one by one)
                        try:
                            text, data = base_cls.convert_tool_result_to_string([block])
                            textual_parts.append(text)
                            multimodal_data.extend(data)
                        except Exception:
                            textual_parts.append(str(block))

                final_text = "\n".join(textual_parts) if textual_parts else ""
                return final_text, multimodal_data

        EnhancedFormatter.__name__ = f"Enhanced{base_cls.__name__}"
        self._formatter_cache[base_cls] = EnhancedFormatter
        return EnhancedFormatter

    def build_chatmodel(self, model_id: str) -> Tuple[ChatModelBase, FormatterBase]:
        """获取指定模型配置
        
        Args:
            model_id: 模型配置ID
            
        Returns:
            Tuple[ChatModelBase, FormatterBase]: 模型实例和对应的 formatter
        """
        if model_id in self._active_models:
            return self._active_models[model_id], self._formatters.get(model_id)

        cfg = self._model_configs.get(model_id, None)
        if not cfg:
            raise ValueError(f"Model configuration for {model_id} not found")
        model, formatter = self._create_model_and_formatter(cfg)
        self._active_models[model_id] = model
        self._formatters[model_id] = formatter
        return model, formatter

    async def __call__(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Literal["auto", "none", "required"] | str] = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        """直接调用默认模型进行对话
        
        该方法继承自 ChatModelBase，使 ModelManager 可以直接作为聊天模型使用。
        调用时会自动使用默认模型（default_model_id）进行响应。

        Args:
            messages: 消息列表
            tools: 可用的工具列表
            tool_choice: 工具选择模式
            **kwargs: 其他参数
            
        Returns:
            ChatResponse 或 AsyncGenerator: 模型响应
        """
        if not self._default_model_id:
            raise ValueError("No default model configured")
        
        model, _ = self.build_chatmodel(self._default_model_id)
        return await model(messages, tools=tools, tool_choice=tool_choice, **kwargs)

    def get_model(self, model_id: Optional[str] = None) -> ChatModelBase:
        """获取模型实例
        
        如果未指定 model_id，则返回默认模型。

        Args:
            model_id: 模型配置ID，默认使用 default_model_id
            
        Returns:
            ChatModelBase: 模型实例
        """
        target_model_id = model_id or self._default_model_id
        if not target_model_id:
            raise ValueError("No model ID specified and no default model configured")
        
        model, _ = self.build_chatmodel(target_model_id)
        return model

    def get_formatter(self, model_id: Optional[str] = None) -> FormatterBase:
        """获取模型对应的 formatter
        
        如果未指定 model_id，则返回默认模型的 formatter。

        Args:
            model_id: 模型配置ID，默认使用 default_model_id
            
        Returns:
            FormatterBase: formatter 实例
        """
        target_model_id = model_id or self._default_model_id
        if not target_model_id:
            raise ValueError("No model ID specified and no default model configured")
        
        _, formatter = self.build_chatmodel(target_model_id)
        return formatter


if __name__ == "__main__":
    import asyncio
    from openbot.config import ConfigManager
    from vxutils import timer, loggerConfig

    loggerConfig(level="INFO")

    async def main():
        config_manager = ConfigManager(
            "E:\\src\\openbot\\.openbot\\config\\config.json"
        )
        model_configs = config_manager.config.model_configs
        model_manager = ModelManager(model_configs)
        with timer("build_chatmodel", verbose=True):
            chatmodel, _ = model_manager.build_chatmodel("doubao_auto")
        with timer("chat_with_chatmodel", verbose=True):
            reply = await chatmodel(
                [{"content": "你好,你有那些skills？", "role": "user"}]
            )
        print(reply.content)

        # async for msg in reply:
        #    print(msg.content)

    asyncio.run(main())
