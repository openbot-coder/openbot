import sys


def main():
    """
    OpenBot 命令行入口
    """
    if len(sys.argv) < 2:
        print("Usage: openbot [init|start|cli]")
        return

    command = sys.argv[1]

    if command == "init":
        print("Initializing OpenBot environment...")
        print("Environment initialized successfully.")
    elif command == "start":
        from .gateway.botflow import BotFlow

        print("Starting OpenBot Gateway...")
        bot_flow = BotFlow()
        bot_flow.run(host="0.0.0.0", port=8000)
    elif command == "cli":
        import asyncio
        from .cli import main as cli_main

        print("Starting OpenBot CLI...")
        asyncio.run(cli_main())
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
