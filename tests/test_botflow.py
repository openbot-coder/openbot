import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from openbot.gateway.botflow import BotFlow, MessageRequest, MessageResponse, ConnectionManager
from openbot.config import BotFlowConfig


class TestBotFlowConfig:
    """测试 BotFlow 配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = BotFlowConfig()
        assert config.model_configs == {}
        assert config.mcp_config_path is not None

    def test_config_with_models(self):
        """测试带模型配置"""
        config = BotFlowConfig(
            model_configs={
                "test_model": {
                    "model_type": "dashscope",
                    "model_name": "qwen-turbo",
                }
            }
        )
        assert "test_model" in config.model_configs


class TestConnectionManager:
    """测试 WebSocket 连接管理器"""

    @pytest.mark.asyncio
    async def test_connection_manager_init(self):
        """测试连接管理器初始化"""
        manager = ConnectionManager()
        assert manager.active_connections == {}

    def test_connection_manager_dict(self):
        """测试连接管理器字典结构"""
        manager = ConnectionManager()
        assert isinstance(manager.active_connections, dict)


class TestBotFlow:
    """测试 BotFlow 类"""

    def test_botflow_init(self):
        """测试 BotFlow 初始化"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))
        assert bot_flow.homespace == Path("E:\\src\\openbot\\.openbot").expanduser()
        assert bot_flow._initialized is False
        assert bot_flow._app is not None

    def test_botflow_app_property(self):
        """测试 app 属性"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))
        assert bot_flow.app is not None

    def test_botflow_toolkit_property(self):
        """测试 toolkit 属性"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))
        assert bot_flow.toolkit is not None

    def test_botflow_ensure_homespace(self):
        """测试 homespace 确保创建"""
        import os
        os.environ["OPENBOT_HOMESPACE"] = "E:\\src\\openbot\\.openbot"
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "test_home"
            bot_flow = BotFlow(homespace=test_path)
            assert test_path.exists()
            assert (test_path / "config").exists()
            assert (test_path / "skills").exists()


class TestMessageModels:
    """测试消息模型"""

    def test_message_request_defaults(self):
        """测试 MessageRequest 默认值"""
        req = MessageRequest(message="Hello")
        assert req.message == "Hello"
        assert req.agent_name == "assistant"
        assert req.model_id == "doubao_auto"
        assert req.session_id == "default"
        assert req.user_id == "user"

    def test_message_request_custom(self):
        """测试 MessageRequest 自定义值"""
        req = MessageRequest(
            message="Hello",
            agent_name="custom_agent",
            model_id="gpt-4",
            session_id="session123",
            user_id="user456"
        )
        assert req.agent_name == "custom_agent"
        assert req.model_id == "gpt-4"
        assert req.session_id == "session123"
        assert req.user_id == "user456"

    def test_message_response(self):
        """测试 MessageResponse"""
        resp = MessageResponse(
            response="Hi there",
            agent_name="assistant",
            session_id="default"
        )
        assert resp.response == "Hi there"
        assert resp.agent_name == "assistant"
        assert resp.session_id == "default"


class TestBotFlowMethods:
    """测试 BotFlow 方法"""

    @pytest.mark.asyncio
    async def test_initialize(self):
        """测试 initialize 方法"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))
        await bot_flow.initialize()
        assert bot_flow._initialized is True

    def test_create_agent_without_init(self):
        """测试在未初始化时创建 agent"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))
        try:
            agent = bot_flow.create_agent(
                name="test",
                system_prompt="You are a test",
                model_id="doubao_auto"
            )
            assert agent is not None
        except Exception:
            pytest.skip("Model not available or initialization needed")


class TestBotFlowRoutes:
    """测试 BotFlow 路由注册"""

    def test_routes_registered(self):
        """测试路由是否注册"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))
        app = bot_flow.app

        routes = [r.path for r in app.routes]
        assert "/" in routes
        assert "/health" in routes
        assert "/process" in routes
        assert "/process/stream" in routes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
