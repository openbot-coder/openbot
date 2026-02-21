print('Test started')

# 测试基本导入
try:
    import sys
    import os
    print('Basic imports ok')
except Exception as e:
    print(f'Basic imports failed: {e}')

# 添加src路径
try:
    sys.path.insert(0, os.path.abspath('./src'))
    print('Added src to path')
except Exception as e:
    print(f'Failed to add src to path: {e}')

# 测试config模块
try:
    from openbot.config import ConfigManager
    print('ConfigManager imported')
    
    # 测试创建实例
    config = ConfigManager()
    print('ConfigManager instance created')
    
    # 测试获取配置
    openbot_config = config.get()
    print('Config obtained')
    print(f'  - Agent name: {openbot_config.agent_config.name}')
except Exception as e:
    print(f'Config module failed: {e}')
    import traceback
    traceback.print_exc()

print('Test completed')
