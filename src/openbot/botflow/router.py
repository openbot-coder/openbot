from ..channels import ChatChannel, Message

class ChannelRouter:
    def __init__(self):
        self.channels: dict[str, ChatChannel] = {}
    
    def register(self, name: str, channel: ChatChannel) -> None:
        """注册 Channel"""
        self.channels[name] = channel
    
    async def start_all(self) -> None:
        """启动所有 Channel"""
        for channel_name, channel in self.channels.items():
            await channel.start()
    
    async def broadcast(self, message: Message) -> None:
        """广播消息到所有 Channel"""
        for channel_name, channel in self.channels.items():
            await channel.send(message)