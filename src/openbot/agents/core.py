import asyncio
import os
import logging
from pathlib import Path
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph
from langchain.agents.middleware import TodoListMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware

from langgraph.checkpoint.memory import InMemorySaver
from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.middleware.memory import MemoryMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.summarization import SummarizationMiddleware
from deepagents import create_deep_agent
from openbot.agents.model import init_modelselector
from openbot.agents.tools.mcptool import init_mcp_middleware
from openbot.common.config import AgentConfig, ConfigManager
from openbot.common.datamodel import (
    AnswerDetail,
    Question,
    Answer,
    ContentType,
    AnswerFuture,
)
from pydantic import BaseModel
from typing import TypedDict


class OpenBotContext(TypedDict):
    model: str = ""


class OpenBotAgent:
    """OpenBot智能体"""

    def __init__(self, config: AgentConfig) -> None:
        self._workspace = config.workspace
        self._config = config
        self._system_prompt = ""
        self._mcp_middleware = None
        self._default_model = config.default_model
        self._model_selector = None
        self._message_queue = asyncio.Queue()
        self._agent = None
        self._running = False
        self._worker_task = None
        self._ready_event = asyncio.Event()
        os.environ["OPENBOT_WORKSPACE"] = self._workspace

        # 初始化系统提示
        self._initialize_system_prompt()

    def _initialize_system_prompt(self) -> None:
        """初始化系统提示"""
        system_prompt_path = Path(__file__).parent / "prompts/system_prompt.md"
        try:
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
            self._system_prompt = system_prompt.format(
                workspace=self._workspace
            ).strip()
            if self._config.system_prompt:
                self._system_prompt = (
                    self._system_prompt + "\n\n" + self._config.system_prompt.strip()
                )
        except Exception as e:
            logging.error(f"Error initializing system prompt: {e}")

    async def init_agent(self) -> CompiledStateGraph:
        """初始化智能体"""
        try:
            self._mcp_middleware, self._model_selector = await asyncio.gather(
                init_mcp_middleware(self._config.mcp_config),
                init_modelselector(self._config.model_configs, self._default_model),
            )
            if not self._model_selector.list_models():
                raise ValueError("模型选择器未配置任何模型")

            backend = FilesystemBackend(
                root_dir=self._workspace,
                virtual_mode=False,
            )

            middlewares = [
                PatchToolCallsMiddleware(),
                TodoListMiddleware(),
                # FilesystemMiddleware(memory_backend=backend),
                self._mcp_middleware,
                self._model_selector,
                # *SkillsMiddleware(
                # *    backend=backend,
                # *    sources=[
                # *        str((Path(self._workspace) / ".openbot/skills").absolute())
                # *    ],
                # *),
                SummarizationMiddleware(
                    model=self._model_selector.get_model(self._default_model),
                    max_tokens_before_summary=170000,
                    messages_to_keep=6,
                    backend=backend,
                ),
                AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
            ]
            # middlewares.append(PatchToolCallsMiddleware())
            model = self._model_selector.get_model(self._default_model)

            self._agent = create_agent(
                model=model,
                tools=[],
                middleware=middlewares,
                checkpointer=InMemorySaver(),
                name="OpenBotAgent",
            )

            self._ready_event.set()
        except Exception as e:
            logging.error(f"Error initializing agent: {e}", exc_info=True)
            raise

        return self._agent

    async def start(self):
        """启动智能体"""
        if self._running:
            return

        self._running = True
        asyncio.create_task(self.init_agent())
        self._worker_task = asyncio.create_task(self.worker())

    async def stop(self):
        """停止智能体"""
        if not self._running:
            return

        self._ready_event.clear()
        if self._worker_task:
            self._worker_task.cancel()
        self._agent = None
        self._worker_task = None
        self._running = False
        logging.info("智能体已停止")

    def switch_model(self, model_name: str) -> bool:
        """切换模型

        Args:
            model_name: 模型名称

        Returns:
            是否切换成功
        """
        if not self._model_selector:
            return False

        if model_name not in self._model_selector.list_models():
            return False

        self._default_model = model_name
        self._model_selector.set_default_model(model_name)
        return True

    def list_models(self) -> list:
        """列出所有可用模型

        Returns:
            模型名称列表
        """
        if not self._model_selector:
            return []
        return list(self._model_selector.list_models().keys())

    async def ask(self, question: Question) -> AnswerFuture:
        """智能体回答问题"""
        if self._agent is None:
            await self._ready_event.wait()

        answer_future = AnswerFuture()
        self._message_queue.put_nowait((question, answer_future))
        return answer_future

    async def worker(self):
        """智能体工作循环"""
        logging.info("智能体工作循环启动")

        while self._running:
            try:
                question, answer_future = await self._message_queue.get()
                if self._agent is None:
                    await self._ready_event.wait()

                logging.info(f"智能体收到问题: {question.content}")

                final_message = None
                async for chunk in self._agent.astream(
                    {"messages": [{"role": "user", "content": question.content}]},
                    context=None,  # 使用 None 代替 OpenBotContext 对象
                    stream_mode="updates",
                    config={
                        "configurable": {
                            "thread_id": question.channel_id,
                            "model": self._default_model,
                        }
                    },
                ):
                    try:
                        for step, chunk_data in chunk.items():
                            if step == "model":
                                message = chunk_data["messages"][-1]
                                final_message = message
                                await self._process_model_step(
                                    question, answer_future, message
                                )
                            elif step == "tools":
                                function_call = chunk_data["messages"][-1]
                                await self._process_tools_step(
                                    question, answer_future, function_call
                                )
                            elif step.split(".")[1] in [
                                "before_model",
                                "before_agent",
                                "after_agent",
                                "after_model",
                            ]:
                                if chunk_data is not None:
                                    await self._process_middleware_step(
                                        question, answer_future, step, chunk_data
                                    )
                            else:
                                # 处理所有其他步骤，包括思考过程
                                await self._process_unknown_step(
                                    question, answer_future, step, chunk_data
                                )
                    except Exception as e:
                        logging.error(f"Error processing chunk: {e}", exc_info=True)

                # 确保有消息可用
                if final_message:
                    answer_future.set_result(
                        Answer(
                            question_id=question.question_id,
                            user_id=question.user_id,
                            channel_id=question.channel_id,
                            content=final_message.content,
                        )
                    )
                else:
                    # 如果没有模型消息，创建一个默认的回答
                    answer_future.set_result(
                        Answer(
                            question_id=question.question_id,
                            user_id=question.user_id,
                            channel_id=question.channel_id,
                            content="",
                        )
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in worker loop: {e}", exc_info=True)

    async def _process_model_step(
        self, question: Question, answer_future: AnswerFuture, message: dict
    ) -> None:
        """处理模型步骤"""
        try:
            answer_detail = AnswerDetail(
                step="model",
                method="model",
                content=message.content,
                content_type=ContentType.TEXT,
                user_id=question.user_id,
                channel_id=question.channel_id,
                metadata={
                    "chunk_data": message,
                },
            )
            await answer_future.set_detail_result(answer_detail)
        except Exception as e:
            logging.error(f"Error processing model step: {e}", exc_info=True)

    async def _process_middleware_step(
        self,
        question: Question,
        answer_future: AnswerFuture,
        step: str,
        chunk_data: dict,
    ) -> None:
        """处理中间件步骤"""
        try:
            method, step = step.split(".")
            answer_detail = AnswerDetail(
                step=step,
                method=method,
                content=method,
                content_type=ContentType.TEXT,
                user_id=question.user_id,
                channel_id=question.channel_id,
                metadata={
                    "chunk_data": chunk_data,
                },
            )
            await answer_future.set_detail_result(answer_detail)
        except Exception as e:
            logging.error(f"Error processing middleware step: {e}", exc_info=True)

    async def _process_tools_step(
        self, question: Question, answer_future: AnswerFuture, function_call: dict
    ) -> None:
        """处理工具步骤"""
        try:
            # 安全获取 arguments
            arguments = function_call.content[-1] if function_call.content else "{}"
            if "type" in arguments:
                content = arguments.get(arguments["type"], "")
            content = str(arguments)

            answer_detail = AnswerDetail(
                step="tools",
                method=function_call.name,
                content=content,
                content_type=ContentType.TEXT,
                user_id=question.user_id,
                channel_id=question.channel_id,
                metadata={
                    "chunk_data": function_call,
                },
            )
            await answer_future.set_detail_result(answer_detail)
        except Exception as e:
            logging.error(f"Error processing tools step: {e}", exc_info=True)

    async def _process_unknown_step(
        self,
        question: Question,
        answer_future: AnswerFuture,
        step: str,
        chunk_data: dict,
    ) -> None:
        """处理未知步骤"""
        logging.error(f"Unknown step: {step} -- {chunk_data}")
        try:
            # 确保 content 是字符串类型
            content_str = str(chunk_data)
            answer_detail = AnswerDetail(
                step=step,
                method="unknown",
                content=content_str,
                content_type=ContentType.TEXT,
                user_id=question.user_id,
                channel_id=question.channel_id,
                metadata={
                    "chunk_data": chunk_data,
                },
            )
            await answer_future.set_detail_result(answer_detail)
        except Exception as e:
            logging.error(f"Error creating AnswerDetail: {e}", exc_info=True)
            # 创建一个简单的 AnswerDetail 来避免流程中断
            error_detail = AnswerDetail(
                step=step,
                method="error",
                content=f"Error processing step: {str(e)}",
                content_type=ContentType.TEXT,
                user_id=question.user_id,
                channel_id=question.channel_id,
            )
            await answer_future.set_detail_result(error_detail)


async def main():
    """主函数"""
    try:
        import argparse
        import os

        parser = argparse.ArgumentParser(description="OpenBot智能体")
        parser.add_argument(
            "--config",
            type=str,
            default=os.path.join(
                os.path.dirname(__file__), "../../examples/config.json"
            ),
            help="配置文件路径",
        )
        args = parser.parse_args()

        config_manager = ConfigManager(args.config)
        config = config_manager.config
        agent = OpenBotAgent(config.agent_config)
        await agent.start()

        logging.info("OpenBot 启动完成，输入 'exit' 退出")
        while True:
            try:
                prompt = await asyncio.to_thread(input, "openbot > ")
                if prompt == "exit":
                    break
                prompt = prompt.strip()
                if not prompt:
                    continue
                question = Question(content=prompt)
                answer_future: AnswerFuture = await agent.ask(question)
                async for answer_detail in answer_future.more_details():
                    print(f"{answer_detail.step}: {answer_detail.content}")
                answer = answer_future.result()
                print("+" * 60)
                print("question:", question.content)
                print("answer:", answer.content)
                print("+" * 60)
            except KeyboardInterrupt:
                logging.info("收到中断信号，退出...")
                break
            except Exception as e:
                logging.error(f"Error in main loop: {e}", exc_info=True)

    finally:
        if "agent" in locals():
            await agent.stop()


if __name__ == "__main__":
    import asyncio
    from vxutils import loggerConfig

    loggerConfig(level=logging.WARNING)
    asyncio.run(main())
