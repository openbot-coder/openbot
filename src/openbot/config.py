import re
import os
import json
import getpass
from pathlib import Path
from typing import List, Dict, Optional, Any, Union, Callable
from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings


class ModelConfig(BaseModel):
    """模型配置类"""

    model_id: str = Field(default="")
    provider: str = Field(default="openai")
    model: str = Field(default="gpt-4o")
    api_key: str = Field(default="")
    base_url: str = Field(default="")
    stream: bool = Field(default=False)
    max_tokens: int = Field(default=2048)
    temperature: float = Field(default=0.7)
    stream_tool_parsing: bool = Field(default=True)
    thinking: dict | None = Field(default_factory=dict)
    client_kwargs: dict[str, object] | None = Field(default_factory=dict)
    generate_kwargs: dict[str, object] | None = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)


class BotFlowConfig(BaseModel):
    work_dir: str = Field(default=str(Path("./").absolute()))
    model_configs: Dict[str, ModelConfig] = Field(default_factory=dict)
    mcp_config_path: str = Field(default="{$OPENBOT_HOMESPACE}/config/mcp.json")
    host: str = Field(default="127.0.0.1")
    port: int = int(os.environ.get("PORT", 8000))
    debug: bool = Field(default=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ConfigManager:
    """配置管理类"""

    def __init__(self, config_path: Union[str, Path]):
        self._config_path = Path(config_path)
        self.env_file = self._config_path.parent / ".env"

        config_dict = self._load_config(self._config_path)
        self._raw_config_dict = {}
        self._config = BotFlowConfig(**config_dict)
        self._validate_config()

    @property
    def config(self) -> BotFlowConfig:
        return self._config

    @property
    def raw_config(self) -> dict:
        return self._raw_config_dict

    def add_model_config(self, model_config: ModelConfig) -> None:
        """添加模型配置"""
        self._config.model_configs[model_config.model_id] = model_config

    def _load_config(self, config_path: Path) -> dict:
        """加载配置文件"""
        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
                self._raw_config_dict = dict(**config_dict)
        else:
            config_dict = BotFlowConfig().model_dump()
            self._raw_config_dict = dict(**config_dict)
        # 解析环境变量引用
        env_vars = {}
        config_dict = self._resolve_env_vars(config_dict, env_vars)
        if env_vars:
            # 确保 env 文件所在的目录存在
            self.env_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.env_file, "a", encoding="utf-8") as f:
                f.write("\n")
                f.writelines([f"{key}={value}\n" for key, value in env_vars.items()])
        return config_dict

    def _validate_config(self) -> None:
        """验证配置完整性"""
        pass

    def _resolve_env_vars(self, config_data: Any, env_vars: dict = None) -> Any:
        """解析配置中的环境变量引用 (支持 dict, list 和 str)"""
        if env_vars is None:
            env_vars = {}

        if isinstance(config_data, dict):
            result = {}
            for key, value in config_data.items():
                # 处理 key 中的环境变量
                real_key = self._resolve_string(key, env_vars)
                # 递归处理 value
                result[real_key] = self._resolve_env_vars(value, env_vars)
            return result

        elif isinstance(config_data, list):
            result = []
            for item in config_data:
                result.append(self._resolve_env_vars(item, env_vars))
            return result

        elif isinstance(config_data, str):
            return self._resolve_string(config_data, env_vars)

        return config_data

    def _resolve_string(self, value: str, env_vars: dict) -> str:
        """辅助函数：解析单个字符串中的环境变量引用，支持 ${VAR} 和 {$VAR} 格式"""
        if not isinstance(value, str):
            return value

        pattern = r"(?:\$\{|\{\$)([^}]+)\}"

        def replace_match(match):
            env_var = match.group(1)
            if env_var in env_vars:
                return env_vars[env_var]

            env_value = os.environ.get(env_var, "")
            if not env_value:
                env_value = input(f"环境变量 {env_var} 未设置，请输入值: ")
                env_value = env_value.strip()
                env_vars[env_var] = env_value
            return env_value

        return re.sub(pattern, replace_match, value)


if __name__ == "__main__":
    config_manager = ConfigManager("config.json")
    print(config_manager.config.model_dump_json(indent=4))
    print(config_manager.raw_config)
