from pydantic import BaseModel
from datetime import datetime
import uuid

class Session(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    context: dict

class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}
    
    def create(self, user_id: str) -> Session:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = Session(
            id=session_id,
            user_id=user_id,
            created_at=datetime.now(),
            context={}
        )
        self.sessions[session_id] = session
        return session
    
    def get(self, session_id: str) -> Session | None:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def close(self, session_id: str) -> None:
        """关闭会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]