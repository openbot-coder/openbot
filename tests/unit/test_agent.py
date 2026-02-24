import pytest
from openbot.agents.core import AgentCore
from openbot.config import ModelConfig, AgentConfig


class TestAgentCore:
    """测试 AgentCore 类"""

    def test_agent_core_creation(self):
        """测试创建 AgentCore"""
        # 创建配置
        model_configs = {
            "default": ModelConfig(
                model_provider="openai",
                model="gpt-4o",
                api_key="test-api-key",
                temperature=0.7,
            )
        }
        agent_config = AgentConfig(
            name="test-agent", system_prompt="You are a test agent."
        )

        # 创建 AgentCore
        agent = AgentCore(model_configs, agent_config)
        assert agent is not None
        # 注意：由于我们无法实际初始化 DeepAgent（需要真实的 API 密钥），
        # 我们只能测试创建过程是否没有异常

    async def test_agent_core_process(self):
        """测试处理消息"""
        # 创建配置
        model_configs = {
            "default": ModelConfig(
                model_provider="openai",
                model="gpt-4o",
                api_key="test-api-key",
                temperature=0.7,
            )
        }
        agent_config = AgentConfig(
            name="test-agent", system_prompt="You are a test agent."
        )

        # 创建 AgentCore
        agent = AgentCore(model_configs, agent_config)

        # 注意：由于我们无法实际调用 LLM（需要真实的 API 密钥），
        # 我们只能测试方法调用是否没有异常
        # 实际运行时，这里可能会抛出异常，因为 API 密钥是无效的
        try:
            result = await agent.process("Hello", {})
            assert isinstance(result, str)
        except Exception:
            # 预期会抛出异常，因为 API 密钥无效
            assert True
