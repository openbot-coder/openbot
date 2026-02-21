import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.abspath('./src'))

print("Checking code health...\n")

# 检查配置模块
try:
    from openbot.config import ConfigManager, OpenbotConfig
    print("✓ Config module imported successfully")
    
    # 测试配置管理器创建
    config_manager = ConfigManager()
    config = config_manager.get()
    print("✓ ConfigManager created successfully")
    print(f"  - Agent config: {config.agent_config.name}")
    print(f"  - Channels: {list(config.channels.keys())}")
except Exception as e:
    print(f"✗ Config module failed: {e}")
    import traceback
    traceback.print_exc()

# 检查通道模块
try:
    from openbot.channels.base import ChatMessage, ChannelBuilder, ChatChannelManager
    print("\n✓ Channels base module imported successfully")
    
    # 测试ChatMessage创建
    msg = ChatMessage(content="Hello", role="user")
    print("✓ ChatMessage created successfully")
    
    # 测试ChannelBuilder
    from openbot.channels.console import ConsoleChannel
    ChannelBuilder.register("console", ConsoleChannel)
    print("✓ ChannelBuilder registered console channel")
    
    # 测试ChatChannelManager
    manager = ChatChannelManager()
    print("✓ ChatChannelManager created successfully")
except Exception as e:
    print(f"\n✗ Channels module failed: {e}")
    import traceback
    traceback.print_exc()

# 检查会话模块
try:
    from openbot.botflow.session import Session, SessionManager
    print("\n✓ Session module imported successfully")
    
    # 测试Session创建
    session = Session(session_id="test")
    print("✓ Session created successfully")
    
    # 测试SessionManager
    session_manager = SessionManager()
    print("✓ SessionManager created successfully")
except Exception as e:
    print(f"\n✗ Session module failed: {e}")
    import traceback
    traceback.print_exc()

# 检查任务模块
try:
    from openbot.botflow.task import Task, TaskManager
    import asyncio
    print("\n✓ Task module imported successfully")
    
    # 测试Task创建
    async def test_task_func():
        pass
    
    task = Task(task_id="test", func=test_task_func, priority=1)
    print("✓ Task created successfully")
    
    # 测试TaskManager
    task_manager = TaskManager(stop_event=asyncio.Event())
    print("✓ TaskManager created successfully")
except Exception as e:
    print(f"\n✗ Task module failed: {e}")
    import traceback
    traceback.print_exc()

# 检查处理器模块
try:
    from openbot.botflow.processor import MessageProcessor
    print("\n✓ Processor module imported successfully")
    
    # 测试MessageProcessor创建
    processor = MessageProcessor()
    print("✓ MessageProcessor created successfully")
except Exception as e:
    print(f"\n✗ Processor module failed: {e}")
    import traceback
    traceback.print_exc()

# 检查代理模块
try:
    from openbot.agents.core import AgentCore
    print("\n✓ Agent module imported successfully")
    
    # 测试AgentCore创建
    agent_core = AgentCore()
    print("✓ AgentCore created successfully")
except Exception as e:
    print(f"\n✗ Agent module failed: {e}")
    import traceback
    traceback.print_exc()

# 检查进化模块
try:
    from openbot.botflow.evolution import CodeChange, GitManager, ApprovalSystem, EvolutionController
    print("\n✓ Evolution module imported successfully")
    
    # 测试CodeChange创建
    code_change = CodeChange(file_path="test.py", changes=[(1, "print('test')")])
    print("✓ CodeChange created successfully")
    
    # 测试GitManager创建
    git_manager = GitManager()
    print("✓ GitManager created successfully")
    
    # 测试ApprovalSystem创建
    approval_system = ApprovalSystem()
    print("✓ ApprovalSystem created successfully")
    
    # 测试EvolutionController创建
    evolution_controller = EvolutionController(git_manager, approval_system)
    print("✓ EvolutionController created successfully")
except Exception as e:
    print(f"\n✗ Evolution module failed: {e}")
    import traceback
    traceback.print_exc()

# 检查BotFlow模块
try:
    from openbot.botflow.core import BotFlow
    print("\n✓ BotFlow module imported successfully")
    
    # 测试BotFlow创建
    botflow = BotFlow()
    print("✓ BotFlow created successfully")
except Exception as e:
    print(f"\n✗ BotFlow module failed: {e}")
    import traceback
    traceback.print_exc()

print("\nCode health check completed!")
