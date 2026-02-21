import pytest
from openbot.agents import AgentCore
from openbot.agents.core import AgentCore as CoreAgentCore


class TestAgentsInit:
    """测试 agents.__init__ 模块的功能"""

    def test_agent_core_import(self):
        """测试 AgentCore 导入是否正确"""
        assert AgentCore is not None
        assert AgentCore is CoreAgentCore


if __name__ == "__main__":
    pytest.main([__file__])
