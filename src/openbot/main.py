import sys
from .core.initializer import initialize_environment


def main():
    """
    OpenBot 命令行入口
    """
    if len(sys.argv) < 2:
        print("Usage: openbot [init|start]")
        return

    command = sys.argv[1]

    if command == "init":
        # 执行环境初始化逻辑
        initialize_environment()
        print("Environment initialized successfully.")
    elif command == "start":
        # 启动 Gateway 服务
        from .gateway.main import app
        import uvicorn

        print("Starting OpenBot Gateway...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
