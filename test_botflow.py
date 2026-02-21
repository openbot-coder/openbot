import asyncio
import logging
from openbot.config import ConfigManager
from openbot.botflow import BotFlow

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def test_botflow():
    """测试 BotFlow 初始化"""
    try:
        # 加载配置
        config_path = "examples/config.json"
        config_manager = ConfigManager(config_path)
        config = config_manager.config
        logging.info("Configuration loaded successfully")

        # 初始化 BotFlow
        botflow = BotFlow(config)
        logging.info("BotFlow initialized successfully")

        # 获取渠道
        channels = botflow.get_channels()
        logging.info(f"Channels: {list(channels.keys())}")

        logging.info("Test completed successfully!")
        return True
    except Exception as e:
        logging.error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_botflow())
