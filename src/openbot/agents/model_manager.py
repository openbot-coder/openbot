from typing import Dict, Type, Tuple, Union, List, Any, Sequence

from agentscope.model import (
    ChatModelBase,
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


class ModelManager:
    """模型管理类"""

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

    def __init__(self, model_configs: Dict[str, ModelConfig]):
        self._model_configs = model_configs
        self._active_models: Dict[str, ChatModelBase] = {}
        self._formatters: Dict[str, FormatterBase] = {}
        self._default_model = None
        self._formatter_cache: Dict[Type[FormatterBase], Type[FormatterBase]] = {}

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
        """获取指定模型配置"""
        if model_id in self._active_models:
            return self._active_models[model_id], self._formatters.get(model_id)

        cfg = self._model_configs.get(model_id, None)
        if not cfg:
            raise ValueError(f"Model configuration for {model_id} not found")
        model, formatter = self._create_model_and_formatter(cfg)
        self._active_models[model_id] = model
        self._formatters[model_id] = formatter
        return model, formatter


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
