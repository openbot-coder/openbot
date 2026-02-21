import asyncio
import datetime
import inspect
import logging
from typing import Any, Dict, Optional, Union
from langchain_core.messages import AnyMessage
from openbot.agents import AgentCore
from openbot.config import ModelConfig, AgentConfig
from openbot.config import OpenbotConfig
from openbot.config import ConfigManager
from openbot.botflow.trigger import Trigger, once
from openbot.botflow.session import SessionManager
from openbot.botflow.processor import MessageProcessor
from openbot.channels.base import ChannelBuilder, ChatMessage, ContentType
from openbot.botflow.task import Task, TaskManager
from openbot.channels.base import ChatChannelManager



class BotFlow:
    def __init__(self, config: OpenbotConfig):
        self._config = config

        # 初始化核心组件
        self.session_manager = SessionManager()
        self.message_processor = MessageProcessor()
        # 初始化渠道
        self._channel_manager = ChatChannelManager()
        
        
        # 初始化智能体
        self._bot = AgentCore(self._config.model_configs, self._config.agent_config)
        # 初始化运行状态
        self._stop_event = asyncio.Event()
        # 初始化任务队列
        self.task_manager = TaskManager(self._stop_event)

    def channel_manager(self) -> ChatChannelManager:
        """获取 Channel 管理器"""
        return self._channel_manager

    async def initialize(self) -> None:
        """初始化智能体"""
        # 初始化渠道
        for channel_type, channel_config in self._config.channels.items():
            enabled = channel_config.enabled
            if enabled:
                channel = ChannelBuilder.create_channel(
                    channel_type, **channel_config.init_kwargs
                )
                # 设置 botflow 属性
                channel.botflow = self
                self._channel_manager.register(channel.channel_id, channel)
        await self._channel_manager.start()
        
        # 启动消息处理任务
        asyncio.create_task(self._process_messages())
    
    async def _process_messages(self) -> None:
        """处理消息队列"""
        while not self._stop_event.is_set():
            try:
                # 从消息队列获取消息
                message = await self._channel_manager._message_queue.get()
                if message:
                    # 处理消息
                    await self.on_receive(message)
                self._channel_manager._message_queue.task_done()
            except Exception as e:
                logging.error(f"Error processing message queue: {e}")

    async def run(self) -> None:
        """运行智能体"""
        await self.initialize()

        self._stop_event.clear()
        try:
            # 启动任务管理器
            task_manager_task = asyncio.create_task(self.task_manager.run())
            
            # 等待停止事件
            await self._stop_event.wait()
        except KeyboardInterrupt:
            self._stop_event.set()
        except Exception as e:
            logging.error(f"Error running BotFlow: {e}")
        finally:
            self._stop_event.set()
            await self._channel_manager.stop()
    
    async def add_task(self, task: Task, trigger = None) -> None:
        """添加任务"""
        await self.task_manager.submit_task(task, trigger)

    async def stop(self) -> None:
        """停止 BotFlow"""
        self._stop_event.set()
    
    async def on_receive(self, message: AnyMessage) -> None:
        """处理接收消息"""
        # 预处理消息
        processed_message = self.message_processor.preprocess(message)
        
        # 创建任务处理消息
        async def process_message():
            try:
                # 转换为 ChatMessage
                from openbot.channels.base import ChatMessage, ContentType
                
                # 提取原始消息内容
                content = processed_message.content
                # 确保使用正确的 channel_id
                channel_id = getattr(message, 'channel_id', 'console')
                
                # 创建 ChatMessage
                chat_message = ChatMessage(
                    content=content,
                    role=processed_message.role,
                    channel_id=channel_id,
                    content_type=ContentType.TEXT,
                    metadata=processed_message.metadata
                )
                
                # 定义回调函数处理流式响应
                async def callback(reply_message):
                    # 发送响应到对应渠道
                    await self._channel_manager.send(reply_message)
                
                # 调用智能体处理消息
                await self._bot.chat(chat_message, streaming_callback=callback)
            except Exception as e:
                logging.error(f"Error processing message: {e}")
        
        # 添加任务到任务管理器
        task = Task(process_message)
        await self.add_task(task)


if __name__ == "__main__":
    import asyncio
    from vxutils import loggerConfig

    loggerConfig(level=logging.ERROR)

    config_path = "./examples/config.json"
    from openbot.config import ConfigManager

    config = ConfigManager(config_path).config
    botflow = BotFlow(config)
    asyncio.run(botflow.run())
