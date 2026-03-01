"""OpenBot主应用"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openbot.common.config import ConfigManager
from openbot.agents.core import OpenBotAgent
from openbot.channels.channel_manager import ChannelManager


class OpenBotApp:
    """OpenBot主应用"""

    def __init__(self, config_path: str = None):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        self.agent = OpenBotAgent(self.config.agent_config)
        self.channel_manager = ChannelManager(self.config, self.agent)
        self.app = FastAPI(
            title="OpenBot", description="OpenBot智能体API", version="1.0.0"
        )
        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self):
        """设置中间件"""
        # 启用CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        """设置路由"""

        @self.app.get("/")
        async def root():
            return {"message": "OpenBot is running"}

        @self.app.get("/health")
        async def health():
            return {"status": "healthy"}

    async def start(self):
        """启动应用"""
        # 启动智能体
        await self.agent.start()

        # 等待智能体初始化完成
        await asyncio.sleep(2)  # 给智能体一些时间来初始化

        # 启动通道
        await self.channel_manager.start()

        # 设置通道Webhook
        self.channel_manager.setup_webhooks(self.app)

        logging.info("OpenBot应用已启动")

    async def stop(self):
        """停止应用"""
        # 停止通道
        await self.channel_manager.stop()

        # 停止智能体
        await self.agent.stop()

        logging.info("OpenBot应用已停止")


if __name__ == "__main__":
    import uvicorn
    import asyncio

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 创建应用
    app = OpenBotApp()

    # 启动应用
    async def startup():
        await app.start()

    # 停止应用
    async def shutdown():
        await app.stop()

    # 注册启动和关闭事件
    app.app.add_event_handler("startup", startup)
    app.app.add_event_handler("shutdown", shutdown)

    # 运行应用
    uvicorn.run(app.app, host=app.config.host, port=app.config.port)
