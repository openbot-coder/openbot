import asyncio
import logging
from openbot.config import ConfigManager

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def test_botflow_simple():
    """简单测试 BotFlow 配置加载"""
    try:
        # 加载配置
        config_path = "examples/config.json"
        config_manager = ConfigManager(config_path)
        config = config_manager.config
        logging.info("Configuration loaded successfully")

        # 打印配置信息
        logging.info(f"Model configs: {list(config.model_configs.keys())}")
        logging.info(f"Agent config: {config.agent_config.name}")
        logging.info(f"Channels: {list(config.channels.keys())}")

        logging.info("Simple test completed successfully!")
        return True
    except Exception as e:
        logging.error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_botflow_simple())
