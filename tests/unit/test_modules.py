print("Test started")

# 测试基本导入
try:
    import sys
    import os

    print("Basic imports ok")
except Exception as e:
    print(f"Basic imports failed: {e}")

# 添加src路径
try:
    sys.path.insert(0, os.path.abspath("./src"))
    print("Added src to path")
except Exception as e:
    print(f"Failed to add src to path: {e}")

# 测试openbot包导入
try:
    import openbot

    print("Openbot package imported")
except Exception as e:
    print(f"Openbot import failed: {e}")
    import traceback

    traceback.print_exc()
    exit(1)

# 测试config模块
try:
    from openbot.config import ConfigManager

    print("ConfigManager imported")

    # 测试创建实例
    config = ConfigManager()
    print("ConfigManager instance created")

    # 测试获取配置
    openbot_config = config.get()
    print("Config obtained")
    print(f"  - Agent name: {openbot_config.agent_config.name}")
except Exception as e:
    print(f"Config module failed: {e}")
    import traceback

    traceback.print_exc()

# 测试channels模块
try:
    from openbot.channels.base import ChatMessage

    print("ChatMessage imported")

    # 测试创建实例
    msg = ChatMessage(content="test", role="user")
    print("ChatMessage instance created")
    print(f"  - Content: {msg.content}")
    print(f"  - Role: {msg.role}")
except Exception as e:
    print(f"Channels module failed: {e}")
    import traceback

    traceback.print_exc()

# 测试session模块
try:
    from openbot.botflow.session import Session

    print("Session imported")

    # 测试创建实例
    session = Session(session_id="test")
    print("Session instance created")
    print(f"  - Session ID: {session.session_id}")
except Exception as e:
    print(f"Session module failed: {e}")
    import traceback

    traceback.print_exc()

# 测试task模块
try:
    from openbot.botflow.task import Task

    print("Task imported")

    # 测试创建实例
    async def test_func():
        pass

    task = Task(task_id="test", func=test_func)
    print("Task instance created")
    print(f"  - Task ID: {task.task_id}")
except Exception as e:
    print(f"Task module failed: {e}")
    import traceback

    traceback.print_exc()

print("Test completed")
