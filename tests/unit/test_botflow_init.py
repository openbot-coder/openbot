import pytest
from openbot.botflow import (
    BotFlow,
    ChannelRouter,
    Session,
    SessionManager,
    MessageProcessor,
    EvolutionController,
    GitManager,
    ApprovalSystem,
    CodeChange,
)
from openbot.botflow.core import BotFlow as CoreBotFlow
from openbot.botflow.router import ChannelRouter as CoreChannelRouter
from openbot.botflow.session import (
    Session as CoreSession,
    SessionManager as CoreSessionManager,
)
from openbot.botflow.processor import MessageProcessor as CoreMessageProcessor
from openbot.botflow.evolution import (
    EvolutionController as CoreEvolutionController,
    GitManager as CoreGitManager,
    ApprovalSystem as CoreApprovalSystem,
    CodeChange as CoreCodeChange,
)


class TestBotFlowInit:
    """测试 botflow.__init__ 模块的功能"""

    def test_botflow_import(self):
        """测试 BotFlow 导入是否正确"""
        assert BotFlow is not None
        assert BotFlow is CoreBotFlow

    def test_channel_router_import(self):
        """测试 ChannelRouter 导入是否正确"""
        assert ChannelRouter is not None
        assert ChannelRouter is CoreChannelRouter

    def test_session_import(self):
        """测试 Session 导入是否正确"""
        assert Session is not None
        assert Session is CoreSession

    def test_session_manager_import(self):
        """测试 SessionManager 导入是否正确"""
        assert SessionManager is not None
        assert SessionManager is CoreSessionManager

    def test_message_processor_import(self):
        """测试 MessageProcessor 导入是否正确"""
        assert MessageProcessor is not None
        assert MessageProcessor is CoreMessageProcessor

    def test_evolution_controller_import(self):
        """测试 EvolutionController 导入是否正确"""
        assert EvolutionController is not None
        assert EvolutionController is CoreEvolutionController

    def test_git_manager_import(self):
        """测试 GitManager 导入是否正确"""
        assert GitManager is not None
        assert GitManager is CoreGitManager

    def test_approval_system_import(self):
        """测试 ApprovalSystem 导入是否正确"""
        assert ApprovalSystem is not None
        assert ApprovalSystem is CoreApprovalSystem

    def test_code_change_import(self):
        """测试 CodeChange 导入是否正确"""
        assert CodeChange is not None
        assert CodeChange is CoreCodeChange


if __name__ == "__main__":
    pytest.main([__file__])
