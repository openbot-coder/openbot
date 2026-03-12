from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from openbot.agents.tool_manger import ToolKitManager
from openbot.agents.model_manager import ModelManager
from openbot.config import BotFlowConfig


class BotFlow:
    def __init__(self, config: BotFlowConfig):
        self.config = config
        self.model_manager = ModelManager(self.config.model_configs)
        self.toolkit_manager = ToolKitManager()
        self.toolkit_manager.register_buildin_tools()
        self.toolkit_manager.register_db_tools()
        self.toolkit_manager.register_skill_dir("E:\\src\o\penbot\\.trae\\skills")

    def create_agent(self, name: str, system_prompt: str, model_id: str) -> ReActAgent:
        model, formatter = self.model_manager.build_chatmodel(model_id)
        return ReActAgent(
            name=name,
            model=model,
            sys_prompt=system_prompt,
            toolkit=self.toolkit_manager._toolkit,
            memory=InMemoryMemory(),
            formatter=formatter,
        )


if __name__ == "__main__":
    from openbot.config import ConfigManager
    from agentscope.message import Msg

    async def main():
        config_manager = ConfigManager(
            "E:\\src\\openbot\\.openbot\\config\\config.json"
        )
        config = config_manager.config
        bot_flow = BotFlow(config)
        agent = bot_flow.create_agent("test_agent", "你是一个智能助手", "doubao_auto")
        while True:
            user_input = input("用户: ")
            if user_input.lower() in ["exit", "quit"]:
                break
            msg = Msg(
                name="user",
                content=user_input,
                role="user",
            )
            reply = await agent.reply([msg])
            print(reply)

    import asyncio

    asyncio.run(main())
