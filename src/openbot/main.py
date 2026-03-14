import sys


def main():
    """
    OpenBot 命令行入口
    """
    import argparse

    parser = argparse.ArgumentParser(description="OpenBot - 多智能体开发框架")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化 OpenBot 环境")

    # start 命令
    start_parser = subparsers.add_parser("start", help="启动 Web 服务")
    start_parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址")
    start_parser.add_argument("--port", type=int, default=8000, help="监听端口")

    # cli 命令
    cli_parser = subparsers.add_parser("cli", help="启动交互式命令行")
    cli_parser.add_argument("--homespace", type=str, default=None, help="Bot配置目录 (默认: ~/.openbot)")
    cli_parser.add_argument("--workspace", "-w", type=str, default=None, help="用户工作目录 (默认: 当前目录)")
    cli_parser.add_argument("--model", "-m", type=str, default="doubao_auto", help="默认使用的模型")

    args = parser.parse_args()

    if args.command == "init":
        print("Initializing OpenBot environment...")
        # 确保homespace目录存在
        from pathlib import Path
        homespace = Path.home() / ".openbot"
        homespace.mkdir(parents=True, exist_ok=True)
        for subdir in ["config", "skills", "memory", "rules", "resources"]:
            (homespace / subdir).mkdir(parents=True, exist_ok=True)
        print("Environment initialized successfully.")
    elif args.command == "start":
        from .gateway.botflow import BotFlow
        print(f"Starting OpenBot Gateway on {args.host}:{args.port}...")
        bot_flow = BotFlow()
        bot_flow.run(host=args.host, port=args.port)
    elif args.command == "cli":
        import asyncio
        from .cli import main as cli_main
        print("Starting OpenBot CLI...")
        # 传递参数给cli.main
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        asyncio.run(cli_main())


if __name__ == "__main__":
    main()
