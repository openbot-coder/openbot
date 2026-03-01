"""通道管理器"""

import logging
from typing import Dict, List
from openbot.common.config import OpenbotConfig
from openbot.channels.base import Channel
from openbot.channels.feishu import FeishuChannel
from openbot.agents.core import OpenBotAgent


class ChannelManager:
    """通道管理器"""

    def __init__(self, config: OpenbotConfig, agent: OpenBotAgent):
        self.config = config
        self.agent = agent
        self.channels: Dict[str, Channel] = {}

    async def start(self):
        """启动所有通道"""
        for channel_config in self.config.channels:
            if channel_config.enabled:
                channel = self._create_channel(channel_config)
                if channel:
                    await channel.start()
                    self.channels[channel.name] = channel

    async def stop(self):
        """停止所有通道"""
        for channel in self.channels.values():
            await channel.stop()
        self.channels.clear()

    def _create_channel(self, channel_config):
        """创建通道

        Args:
            channel_config: 通道配置

        Returns:
            通道实例
        """
        try:
            if channel_config.name == "feishu":
                return FeishuChannel(channel_config, self.agent)
            else:
                logging.warning(f"未知的通道类型: {channel_config.name}")
                return None
        except Exception as e:
            logging.error(f"创建通道 {channel_config.name} 出错: {e}", exc_info=True)
            return None

    def get_channel(self, name: str) -> Channel:
        """获取通道

        Args:
            name: 通道名称

        Returns:
            通道实例
        """
        return self.channels.get(name)

    def get_all_channels(self) -> List[Channel]:
        """获取所有通道

        Returns:
            通道实例列表
        """
        return list(self.channels.values())

    def setup_webhooks(self, app):
        """设置Webhook

        Args:
            app: FastAPI应用
        """
        for channel in self.channels.values():
            if channel.path:
                handler = channel.get_webhook_handler()
                if handler:
                    app.post(channel.path)(handler)
                    logging.info(
                        f"设置通道 {channel.name} 的Webhook路径: {channel.path}"
                    )
