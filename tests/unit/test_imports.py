print("Testing imports...")

# 测试基本导入
try:
    import sys
    import os
    print("✓ Basic imports work")
except Exception as e:
    print(f"✗ Basic imports failed: {e}")

# 添加src目录到Python路径
try:
    sys.path.insert(0, os.path.abspath('./src'))
    print("✓ Added src to path")
except Exception as e:
    print(f"✗ Failed to add src to path: {e}")

# 测试配置模块
try:
    from openbot.config import ConfigManager
    print("✓ ConfigManager imported")
except Exception as e:
    print(f"✗ ConfigManager import failed: {e}")

# 测试消息模块
try:
    from openbot.channels.base import ChatMessage
    print("✓ ChatMessage imported")
except Exception as e:
    print(f"✗ ChatMessage import failed: {e}")

print("Import test completed!")
