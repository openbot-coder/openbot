import asyncio
from typing import AsyncIterator
from .base import ChatChannel, Message

class ConsoleChannel(ChatChannel):
    def __init__(self, prompt: str = "openbot> "):
        self.prompt = prompt
        self.running = False
    
    async def start(self) -> None:
        self.running = True
        print("OpenBot Console Channel started. Type 'exit' to quit.")
    
    async def send(self, message: Message) -> None:
        if message.role == "assistant":
            print(f"\n{message.content}\n")
    
    async def send_stream(self, stream: AsyncIterator[str]) -> None:
        content = ""
        async for chunk in stream:
            content += chunk
            print(chunk, end="", flush=True)
        print()
    
    async def receive(self) -> AsyncIterator[Message]:
        while self.running:
            try:
                user_input = await asyncio.to_thread(input, self.prompt)
                if user_input.lower() == "exit":
                    self.running = False
                    break
                yield Message(
                    content=user_input,
                    role="user",
                    metadata={"channel": "console"}
                )
            except EOFError:
                self.running = False
                break
    
    async def stop(self) -> None:
        self.running = False
        print("OpenBot Console Channel stopped.")