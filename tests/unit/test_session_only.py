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

# 测试session模块
try:
    from openbot.botflow.session import Session, SessionManager
    print('Session and SessionManager imported')
    
    # 测试SessionManager创建实例
    session_manager = SessionManager()
    print('SessionManager instance created')
    
    # 测试创建会话
    session = session_manager.create(user_id='test_user')
    print('Session created via SessionManager')
    print(f'  - Session ID: {session.id}')
    print(f'  - User ID: {session.user_id}')
except Exception as e:
    print(f'Session module failed: {e}')
    import traceback
    traceback.print_exc()

print('Test completed')
