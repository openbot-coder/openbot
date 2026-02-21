#!/usr/bin/env python3
"""测试系统功能"""
import asyncio
import logging
import sys
from openbot.config import ConfigManager
from openbot.botflow.core import BotFlow


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)


async def test_system():
    """测试系统功能"""
    print("Starting system test...")
    
    # 加载配置
    config_path = "examples/config.json"
    print(f"Loading configuration from: {config_path}")
    
    try:
        config_manager = ConfigManager(config_path)
        config = config_manager.get()
        print(f"Configuration loaded successfully")
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return

    # 初始化 BotFlow
    print("Initializing BotFlow...")
    try:
        botflow = BotFlow(config)
        print("BotFlow initialized successfully")
    except Exception as e:
        print(f"Error initializing BotFlow: {e}")
        return

    try:
        # 初始化系统
        print("Initializing system...")
        await botflow.initialize()
        print("System initialized successfully")
        
        # 等待一段时间
        print("System is running... Press Ctrl+C to stop")
        await asyncio.sleep(5)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print(f"Error running system: {e}")
    finally:
        # 停止系统
        print("Stopping system...")
        try:
            await botflow.stop()
            print("System stopped successfully")
        except Exception as e:
            print(f"Error stopping system: {e}")


if __name__ == "__main__":
    asyncio.run(test_system())
    print("System test completed")

