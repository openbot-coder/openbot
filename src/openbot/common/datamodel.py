"""回答类定义"""

import asyncio
import uuid
from typing import Dict, Any, AsyncGenerator
from pydantic import Field
from asyncio import Future
from vxutils import VXDataModel


class ContentType:
    """消息内容类型"""

    TEXT = "text"
    VIDEO = "video"
    IMAGE = "image"
    FILE = "file"
    LINK = "link"


class Question(VXDataModel):
    """问题模型"""

    question_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="问题 ID"
    )
    content: str = Field(default="", description="问题内容")
    content_type: str = Field(default=ContentType.TEXT, description="问题内容类型")
    user_id: str = Field(default="", description="用户 ID")
    channel_id: str = Field(default="", description="通道 ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="问题元数据")


class Answer(VXDataModel):
    """回答模型"""

    answer_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="回答 ID"
    )
    question_id: str = Field(default="", description="问题 ID")
    content: str = Field(default="", description="回答内容")
    content_type: str = Field(default=ContentType.TEXT, description="回答内容类型")
    user_id: str = Field(default="", description="用户 ID")
    channel_id: str = Field(default="", description="通道 ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="回答元数据")


class AnswerDetail(VXDataModel):
    """回答详细模型"""

    step: str = Field(default="", description="步骤")
    method: str = Field(default="", description="方法")
    content: str = Field(default="", description="回答内容")
    content_type: str = Field(default=ContentType.TEXT, description="回答内容类型")
    user_id: str = Field(default="", description="用户 ID")
    channel_id: str = Field(default="", description="通道 ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="回答元数据")


class AnswerFuture(Future):
    """回答基类"""

    def __init__(self, *, loop: asyncio.EventLoop = None):
        super().__init__(loop=loop)
        self._detail_result: asyncio.Queue = asyncio.Queue()
        self._finish_event = asyncio.Event()
        self._new_detail_condition = asyncio.Condition()

    def set_result(self, result: Answer, /) -> None:
        """设置回答结果"""
        super().set_result(result)
        self._finish_event.set()

    def set_exception(self, exc: Exception, /) -> None:
        super().set_exception(exc)
        self._finish_event.set()

    async def set_detail_result(self, detail: AnswerDetail) -> None:
        """设置详细回答结果"""
        async with self._new_detail_condition:
            self._detail_result.put_nowait(detail)
            self._new_detail_condition.notify()

    async def more_details(
        self, timeout: float = 1.0
    ) -> AsyncGenerator[AnswerDetail, None]:
        """获取详细回答结果"""
        async with self._new_detail_condition:
            while not self._finish_event.is_set():
                try:
                    detail = self._detail_result.get_nowait()
                    if detail:
                        yield detail
                except asyncio.queues.QueueEmpty:
                    try:
                        await asyncio.wait_for(
                            self._new_detail_condition.wait(), timeout=timeout
                        )
                    except asyncio.TimeoutError:
                        # 超时后继续循环，检查是否结束
                        pass

            # 处理队列中剩余的消息
            while not self._detail_result.empty():
                try:
                    detail = self._detail_result.get_nowait()
                    if detail:
                        yield detail
                except asyncio.queues.QueueEmpty:
                    break
