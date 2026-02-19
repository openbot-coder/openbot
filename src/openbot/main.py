import asyncio
import argparse
from .config import ConfigManager
from .channels import ConsoleChannel
from .botflow import ChannelRouter, SessionManager, MessageProcessor
from .agents import AgentCore

async def main():
    """CLI 入口点"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="OpenBot CLI")
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--channel", type=str, default="console", help="启动的 channel")
    args = parser.parse_args()
    
    # 加载配置
    config_manager = ConfigManager(args.config)
    config = config_manager.get()
    
    # 初始化组件
    session_manager = SessionManager()
    message_processor = MessageProcessor()
    agent_core = AgentCore(config.llm.model_dump())
    
    # 初始化 Channel Router
    router = ChannelRouter()
    
    # 注册 Console Channel
    if config.channels.get("console", {}).enabled:
        console_channel = ConsoleChannel(
            prompt=config.channels.get("console", {}).prompt
        )
        router.register("console", console_channel)
    
    # 启动所有 Channel
    await router.start_all()
    
    # 创建会话
    session = session_manager.create("default-user")
    
    try:
        # 处理消息
        if "console" in router.channels:
            async for message in router.channels["console"].receive():
                # 预处理消息
                processed_message = message_processor.preprocess(message)
                
                # 调用 AI 处理
                ai_response = await agent_core.process(
                    processed_message.content,
                    session
                )
                
                # 创建响应消息
                response_message = message.__class__(
                    content=ai_response,
                    role="assistant",
                    metadata={"channel": "console"}
                )
                
                # 后处理响应
                processed_response = message_processor.postprocess(response_message)
                
                # 发送响应
                await router.channels["console"].send(processed_response)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        # 停止所有 Channel
        if "console" in router.channels:
            await router.channels["console"].stop()
        
        # 关闭会话
        session_manager.close(session.id)

if __name__ == "__main__":
    asyncio.run(main())