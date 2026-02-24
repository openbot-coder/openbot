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

print("Test completed")
