import asyncio
import argparse
import logging
from .config import ConfigManager
from .botflow.core import BotFlow


async def run_server(config_path: str, console: bool = False):
    """运行服务器模式"""
    logging.info(f"Starting OpenBot server with config: {config_path}")

    config_manager = ConfigManager(config_path)
    config = config_manager.get()
    logging.info("Configuration loaded successfully")

    # 如果指定了console参数，确保控制台通道启用
    if console:
        config.channels["console"].enabled = True

    # 初始化 BotFlow
    botflow = BotFlow(config)
    logging.info("BotFlow initialized successfully")

    try:
        # 运行 BotFlow
        await botflow.run()
    except KeyboardInterrupt:
        logging.info("Interrupted by user.")
    except Exception as e:
        logging.error(f"Error running server: {e}")
    finally:
        # 停止 BotFlow
        await botflow.stop()


async def run_client(url: str, config_path: str, token: str):
    """运行客户端模式"""
    logging.info(f"Starting OpenBot client with URL: {url}")
    logging.info(f"Loading configuration from: {config_path}")

    # 这里可以实现WebSocket客户端
    # 目前MVP版本只支持服务器模式
    logging.warning("Client mode is not implemented in MVP version.")
    logging.warning("Please use server mode instead.")


async def main():
    """CLI 入口点"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="OpenBot CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 服务器模式
    server_parser = subparsers.add_parser("server", help="Run OpenBot in server mode")
    server_parser.add_argument(
        "--config", type=str, default="examples/config.json", help="配置文件路径"
    )
    server_parser.add_argument("--console", action="store_true", help="启用控制台通道")

    # 客户端模式
    client_parser = subparsers.add_parser("client", help="Run OpenBot in client mode")
    client_parser.add_argument("--url", type=str, required=True, help="WebSocket URL")
    client_parser.add_argument(
        "--config", type=str, default="examples/config.json", help="配置文件路径"
    )
    client_parser.add_argument("--token", type=str, help="认证令牌")

    # 直接运行模式（向后兼容）
    parser.add_argument(
        "--config", type=str, default="examples/config.json", help="配置文件路径"
    )
    parser.add_argument("--channel", type=str, default="console", help="启动的 channel")

    args = parser.parse_args()

    try:
        if args.command == "server":
            await run_server(args.config, args.console)
        elif args.command == "client":
            await run_client(args.url, args.config, args.token)
        else:
            # 向后兼容：直接运行
            await run_server(args.config, True)
    except Exception as e:
        logging.error(f"Error: {e}")


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())
