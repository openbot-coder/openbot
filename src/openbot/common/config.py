import json
import os
import logging
from typing import List, Dict
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class ChannelConfig(BaseSettings):
    """通道配置类"""

    name: str = ""
    enabled: bool = True
    path: str = ""
    params: dict = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class ModelConfig(BaseSettings):
    """模型配置类"""

    model_provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str | None = None
    temperature: float = 0.7
    base_url: str = "https://api.openai.com/v1"


class AgentConfig(BaseSettings):
    """智能体配置类"""

    name: str = "openbot"
    system_prompt: str = "你是一个智能助手，你的任务是回答用户的问题。"
    model_configs: Dict[str, ModelConfig] = {}
    skills: List[str] = [".openbot/skills"]
    memory: List[str] = [".openbot/memory"]
    mcp_config: str = "mcp.json"
    default_model: str = ""
    workspace: str = "."
    debug: bool = False

    model_config = {"extra": "allow"}


class OpenbotConfig(BaseSettings):
    """Openbot 配置类"""

    agent_config: AgentConfig = AgentConfig()
    channels: List[ChannelConfig] = Field(
        default_factory=lambda: [
            ChannelConfig(
                name="feishu",
                enabled=True,
                path="/feishu/webhook",
                params={"app_id": "", "app_secret": "", "verification_token": ""},
            ),
        ]
    )
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "data/botflow.db"
    worker_count: int = 4
    queue_timeout: float = 30.0

    model_config = {"extra": "allow"}


class ConfigManager:
    """配置管理类"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        # 如果配置文件在 config/ 子目录中，则使用其父目录作为项目根目录
        config_path_obj = Path(config_path) if config_path else None
        if config_path_obj and config_path_obj.parent.name == "config":
            self.config_dir = config_path_obj.parent.parent
        else:
            self.config_dir = Path.cwd()
        self.config = self._load_config()
        self._validate_config()
        self._resolve_relative_paths()

    def _load_config(self) -> OpenbotConfig:
        """加载配置文件"""
        if self.config_path and os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
            # 解析环境变量引用
            config_dict = self._resolve_env_vars(config_dict)
            return OpenbotConfig(**config_dict)
        return OpenbotConfig()

    def _resolve_relative_paths(self) -> None:
        """将相对路径转换为基于配置文件目录的绝对路径"""
        # 解析 workspace
        if self.config.agent_config.workspace:
            workspace_path = Path(self.config.agent_config.workspace)
            if not workspace_path.is_absolute():
                self.config.agent_config.workspace = str(
                    (self.config_dir / workspace_path).resolve()
                )

        # 解析 mcp_config
        if self.config.agent_config.mcp_config:
            mcp_path = Path(self.config.agent_config.mcp_config)
            if not mcp_path.is_absolute():
                self.config.agent_config.mcp_config = str(
                    (self.config_dir / mcp_path).resolve()
                )

        # 解析 skills 路径
        resolved_skills = []
        for skill_path in self.config.agent_config.skills:
            skill_p = Path(skill_path)
            if not skill_p.is_absolute():
                resolved_skills.append(str((self.config_dir / skill_p).resolve()))
            else:
                resolved_skills.append(skill_path)
        self.config.agent_config.skills = resolved_skills

        # 解析 memory 路径
        resolved_memory = []
        for memory_path in self.config.agent_config.memory:
            memory_p = Path(memory_path)
            if not memory_p.is_absolute():
                resolved_memory.append(str((self.config_dir / memory_p).resolve()))
            else:
                resolved_memory.append(memory_path)
        self.config.agent_config.memory = resolved_memory

    def _validate_config(self) -> None:
        """验证配置完整性"""

    def get_model_configs(self) -> Dict[str, ModelConfig]:
        """获取模型配置"""
        return self.config.agent_config.model_configs

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
