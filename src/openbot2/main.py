import asyncio
import argparse
import logging
from openbot.config import ConfigManager
from openbot.botflow.core import BotFlow
import uvicorn


def run_server(config_path: str, console: bool = False):
    """运行服务器模式"""
    print(f"Starting OpenBot server with config: {config_path}")
    logging.info(f"Starting OpenBot server with config: {config_path}")

    try:
        config_manager = ConfigManager(config_path)
        print("Config manager created")
        config = config_manager.get()
        print(f"Configuration loaded successfully: {config}")
        logging.info("Configuration loaded successfully")

        # 初始化 BotFlow
        print("Initializing BotFlow...")
        botflow = BotFlow(config)
        print("BotFlow initialized successfully")
        print(f"Registered channels: {list(botflow.channels.keys())}")
        # 打印所有注册的路由
        print("\nRegistered routes:")
        for route in botflow.app.routes:
            print(
                f"  - {route.path} ({route.methods if hasattr(route, 'methods') else 'N/A'})"
            )
        logging.info("BotFlow initialized successfully")

        # 打印微信通道的配置
        for channel_config in config.channels:
            if channel_config.name == "wechat":
                print(f"\nWeChat channel configuration:")
                print(f"  Name: {channel_config.name}")
                print(f"  Enabled: {channel_config.enabled}")
                print(f"  Path: {channel_config.path}")
                print(f"  Params: {channel_config.params}")

        # 运行 BotFlow
        print(f"\nStarting uvicorn server at {config.host}:{config.port}...")
        uvicorn.run(botflow.app, host=config.host, port=config.port, log_level="info")
    except KeyboardInterrupt:
        print("Interrupted by user.")
        logging.info("Interrupted by user.")
    except Exception as e:
        print(f"Error running server: {e}")
        import traceback

        traceback.print_exc()
        logging.error(f"Error running server: {e}")


def run_client(url: str, config_path: str, token: str):
    """运行客户端模式"""
    logging.info(f"Starting OpenBot client with URL: {url}")
    logging.info(f"Loading configuration from: {config_path}")

    # 客户端模式已移除
    logging.warning("Client mode is not available.")


def main():
    """CLI 入口点"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="OpenBot CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 服务器模式
    server_parser = subparsers.add_parser("server", help="Run OpenBot in server mode")
    server_parser.add_argument(
        "--config", type=str, default="config/config.json", help="配置文件路径"
    )
    server_parser.add_argument("--console", action="store_true", help="启用控制台通道")

    # 客户端模式
    client_parser = subparsers.add_parser("client", help="Run OpenBot in client mode")
    client_parser.add_argument("--url", type=str, required=True, help="WebSocket URL")
    client_parser.add_argument(
        "--config", type=str, default="config/config.json", help="配置文件路径"
    )
    client_parser.add_argument("--token", type=str, help="认证令牌")

    # 直接运行模式（向后兼容）
    parser.add_argument(
        "--config", type=str, default="config/config.json", help="配置文件路径"
    )
    parser.add_argument("--channel", type=str, default="console", help="启动的 channel")

    args = parser.parse_args()

    try:
        if args.command == "server":
            run_server(args.config, args.console)
        elif args.command == "client":
            run_client(args.url, args.config, args.token)
        else:
            # 向后兼容：直接运行
            run_server(args.config, True)
    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    from vxutils import loggerConfig

    loggerConfig()

    main()
