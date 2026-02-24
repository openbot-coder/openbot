import pytest
from openbot.botflow.session import Session, SessionManager


class TestSession:
    """测试 Session 类"""

    def test_session_creation(self):
        """测试创建 Session"""
        session = Session(id="test-id", user_id="test-user", context={"key": "value"})
        assert session.id == "test-id"
        assert session.user_id == "test-user"
        assert session.context == {"key": "value"}


class TestSessionManager:
    """测试 SessionManager 类"""

    def test_create_session(self):
        """测试创建会话"""
        manager = SessionManager()
        session = manager.create(user_id="test-user")
        assert isinstance(session, Session)
        assert session.user_id == "test-user"
        assert session.id is not None
        assert session.context == {}

    def test_get_session(self):
        """测试获取会话"""
        manager = SessionManager()
        session = manager.create(user_id="test-user")
        retrieved_session = manager.get(session.id)
        assert retrieved_session == session

    def test_get_nonexistent_session(self):
        """测试获取不存在的会话"""
        manager = SessionManager()
        assert manager.get("nonexistent-id") is None

    def test_close_session(self):
        """测试关闭会话"""
        manager = SessionManager()
        session = manager.create(user_id="test-user")
        session_id = session.id
        manager.close(session_id)
        assert manager.get(session_id) is None

    def test_multiple_sessions(self):
        """测试管理多个会话"""
        manager = SessionManager()
        session1 = manager.create(user_id="user1")
        session2 = manager.create(user_id="user2")

        assert manager.get(session1.id) == session1
        assert manager.get(session2.id) == session2

        manager.close(session1.id)
        assert manager.get(session1.id) is None
        assert manager.get(session2.id) == session2
