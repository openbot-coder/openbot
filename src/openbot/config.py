import json
import os
import logging
from typing import List, Dict
from pydantic import Field
from pydantic_settings import BaseSettings


class ChannelConfig(BaseSettings):
    enabled: bool = True
    init_kwargs: dict = Field(default_factory=dict)


class EvolutionConfig(BaseSettings):
    enabled: bool = True
    auto_test: bool = True
    require_approval: bool = True


class ModelConfig(BaseSettings):
    model_provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str | None = None
    temperature: float = 0.7
    base_url: str = "https://api.openai.com/v1"


class AgentConfig(BaseSettings):
    name: str = "openbot"
    system_prompt: str = "你是一个智能助手，你的任务是回答用户的问题。"
    skills: List[str] = []
    memory: List[str] = []
    tools: List[str] = []
    debug: bool = False


class OpenbotConfig(BaseSettings):
    model_configs: Dict[str, ModelConfig] = {}
    agent_config: AgentConfig = AgentConfig()
    channels: dict[str, ChannelConfig] = {"console": ChannelConfig()}
    evolution: EvolutionConfig = EvolutionConfig()


class ConfigManager:
    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self) -> OpenbotConfig:
        """加载配置文件"""
        if self.config_path and os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
            # 解析环境变量引用
            config_dict = self._resolve_env_vars(config_dict)
            return OpenbotConfig(**config_dict)
        return OpenbotConfig()

    def _validate_config(self) -> None:
        """验证配置完整性"""
        if not self.config.model_configs:
            logging.warning("No model configurations provided, using defaults")
        
        for name, config in self.config.model_configs.items():
            if not config.api_key:
                logging.warning(f"API key not configured for model {name}")
            
            if not config.model:
                raise ValueError(f"Model name not specified for {name}")

    def _resolve_env_vars(self, config_dict: dict) -> dict:
        """解析配置中的环境变量引用"""
        result = {}
        for key, value in config_dict.items():
            if isinstance(value, dict):
                result[key] = self._resolve_env_vars(value)
            elif (
                isinstance(value, str)
                and value.startswith("${")
                and value.endswith("}")
            ):
                env_var = value[2:-1]
                result[key] = os.environ.get(env_var)
            else:
                result[key] = value
        return result

    def get(self) -> OpenbotConfig:
        """获取配置"""
        return self.config
