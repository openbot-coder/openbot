import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.abspath('./src'))

print("Running simple test...")

# 测试配置模块
try:
    from openbot.config import ConfigManager
    config = ConfigManager()
    print("✓ ConfigManager works")
except Exception as e:
    print(f"✗ ConfigManager failed: {e}")

# 测试消息模块
try:
    from openbot.channels.base import ChatMessage
    msg = ChatMessage(content="test")
    print("✓ ChatMessage works")
except Exception as e:
    print(f"✗ ChatMessage failed: {e}")

# 测试会话模块
try:
    from openbot.botflow.session import Session
    session = Session(session_id="test")
    print("✓ Session works")
except Exception as e:
    print(f"✗ Session failed: {e}")

# 测试任务模块
try:
    from openbot.botflow.task import Task
    async def test_func():
        pass
    task = Task(task_id="test", func=test_func)
    print("✓ Task works")
except Exception as e:
    print(f"✗ Task failed: {e}")

# 测试代理模块
try:
    from openbot.agents.core import AgentCore
    agent = AgentCore()
    print("✓ AgentCore works")
except Exception as e:
    print(f"✗ AgentCore failed: {e}")

# 测试BotFlow模块
try:
    from openbot.botflow.core import BotFlow
    botflow = BotFlow()
    print("✓ BotFlow works")
except Exception as e:
    print(f"✗ BotFlow failed: {e}")

print("\nSimple test completed!")
