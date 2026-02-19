from langchain_core.chat_models import ChatModel
from langchain_openai import ChatOpenAI
from pydantic_settings import BaseSettings
from ..botflow import Session

class AgentConfig(BaseSettings):
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str | None = None
    temperature: float = 0.7

class AgentCore:
    def __init__(self, config: dict):
        self.config = AgentConfig(**config)
        self.agent = self._init_agent()
    
    def _init_agent(self) -> ChatModel:
        """初始化 LLM 代理"""
        if self.config.provider == "openai":
            return ChatOpenAI(
                model=self.config.model,
                api_key=self.config.api_key,
                temperature=self.config.temperature,
            )
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")
    
    async def process(self, message: str, session: Session) -> str:
        """处理用户消息"""
        # 构建消息历史
        messages = [
            {"role": "system", "content": "You are OpenBot, an AI assistant with multi-channel support and self-evolution capabilities."},
            {"role": "user", "content": message}
        ]
        
        # 调用 LLM
        response = await self.agent.ainvoke(messages)
        return response.content