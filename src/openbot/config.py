import json
import os
from pydantic_settings import BaseSettings

class ChannelConfig(BaseSettings):
    enabled: bool = True
    prompt: str = "openbot> "

class EvolutionConfig(BaseSettings):
    enabled: bool = True
    auto_test: bool = True
    require_approval: bool = True

class LLMConfig(BaseSettings):
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str | None = None
    temperature: float = 0.7

class Config(BaseSettings):
    llm: LLMConfig = LLMConfig()
    channels: dict[str, ChannelConfig] = {"console": ChannelConfig()}
    evolution: EvolutionConfig = EvolutionConfig()

class ConfigManager:
    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Config:
        """加载配置文件"""
        if self.config_path and os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
            # 解析环境变量引用
            config_dict = self._resolve_env_vars(config_dict)
            return Config(**config_dict)
        return Config()
    
    def _resolve_env_vars(self, config_dict: dict) -> dict:
        """解析配置中的环境变量引用"""
        result = {}
        for key, value in config_dict.items():
            if isinstance(value, dict):
                result[key] = self._resolve_env_vars(value)
            elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                result[key] = os.environ.get(env_var)
            else:
                result[key] = value
        return result
    
    def get(self) -> Config:
        """获取配置"""
        return self.config