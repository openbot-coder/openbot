"""
执行器
"""

import asyncio
from typing import Optional, List, Dict
from langchain_core.messages import HumanMessage
from openbot.agents.base import Answer, AnswerDetail, AnswerFuture, Question
from openbot.config import ModelConfig, AgentConfig




class OpenbotExecutor:
    """OpenBot 执行器"""

    def __init__(self, model_configs: List[ModelConfig], agent_config: AgentConfig):
        self._model_configs = {config.model: config for config in model_configs}
        self._agent_config = agent_config
        self._stop_event = asyncio.Event()
        self._stop_event.set()
        self._question_queue = asyncio.Queue()
        self._core_executor = None
        self._bot_worker = asyncio.create_task(self._run())

    async def ask(self, question: Question) -> AnswerFuture:
        """提问"""
        answer_future = AnswerFuture()
        await self._question_queue.put((question, answer_future))
        return answer_future

    @property
    def question_queue(self) -> asyncio.Queue:
        """问题队列"""
        return self._question_queue

    def _init_agent(self):
        """初始化智能体"""
        if not self._core_executor:
            self._core_executor = CoreExecutor(self._model_configs, self._agent_config)
        return self._core_executor

    async def _run(self) -> None:
        """运行执行器"""
        # 初始化核心执行器
        core_executor = self._init_agent()
        await core_executor.init_agent()

        while not self._stop_event.is_set():
            try:
                question, answer_future = await self._question_queue.get()
                try:
                    # 处理消息
                    await self._process_message(question, answer_future)
                finally:
                    self._question_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # 处理错误
                try:
                    if 'answer_future' in locals():
                        answer_future.set_exception(e)
                except:
                    pass
                finally:
                    self._question_queue.task_done()

    async def _process_message(
        self, question: Question, answer_future: AnswerFuture
    ) -> None:
        """处理消息"""
        try:
            # 使用核心执行器处理问题
            answer = await self._core_executor.ask(
                question=question.content,
                stream=False,
                channel_id=question.channel_id
            )
            # 转换为Answer对象
            answer_obj = Answer(
                question_id=question.question_id,
                content=answer.content,
                content_type='text',
                user_id=question.user_id,
                channel_id=question.channel_id
            )
            # 设置回答
            answer_future.set_result(answer_obj)
        except Exception as e:
            # 设置异常
            answer_future.set_exception(e)

    def start(self):
        """启动执行器"""
        if not self._stop_event.is_set():
            return
        self._stop_event.clear()
        self._bot_worker = asyncio.create_task(self._run())

    def stop(self):
        """停止执行器"""
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        if not self._bot_worker.done():
            self._bot_worker.cancel()

    async def wait_until_stopped(self):
        """等待执行器停止"""
        if not self._bot_worker.done():
            await self._bot_worker

