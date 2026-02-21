import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.abspath('./src'))

print("Testing ConfigManager import...")
try:
    from openbot.config import ConfigManager
    print("✓ ConfigManager imported successfully")
    
    # 测试创建实例
    config = ConfigManager()
    print("✓ ConfigManager instance created successfully")
    
    # 测试获取配置
    openbot_config = config.get()
    print("✓ Config obtained successfully")
    print(f"  - Agent name: {openbot_config.agent_config.name}")
    print(f"  - Enabled channels: {list(openbot_config.channels.keys())}")
    
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()

print("\nTest completed!")
