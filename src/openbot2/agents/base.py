"""回答类定义"""

import asyncio
from abc import ABC, abstractmethod
import uuid
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from asyncio import Future
from vxutils import VXDataModel
from openbot.agents.trigger import Trigger, once


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
    content_type: ContentType = Field(
        default=ContentType.TEXT, description="问题内容类型"
    )
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
    content_type: ContentType = Field(
        default=ContentType.TEXT, description="回答内容类型"
    )
    user_id: str = Field(default="", description="用户 ID")
    channel_id: str = Field(default="", description="通道 ID")
    input_tokens: int = Field(default=0, description="输入 token 数")
    output_tokens: int = Field(default=0, description="输出 token 数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="回答元数据")


class AnswerDetail(VXDataModel):
    """回答详细模型"""

    step: str = Field(default="", description="步骤")
    method: str = Field(default="", description="方法")
    content: str = Field(default="", description="回答内容")
    content_type: ContentType = Field(
        default=ContentType.TEXT, description="回答内容类型"
    )
    user_id: str = Field(default="", description="用户 ID")
    channel_id: str = Field(default="", description="通道 ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="回答元数据")


class AnswerFuture(Future):
    """回答基类"""

    def __init__(self, *, loop: asyncio.EventLoop = None):
        super().__init__(loop=loop)
        self._detail_result: asyncio.Queue = asyncio.Queue()
        self._finish_event = asyncio.Event()

    def set_result(self, result: Answer, /) -> None:
        super().set_result(result)
        self._finish_event.set()
        return

    def set_exception(self, exc: Exception, /) -> None:

        super().set_exception(exc)
        self._finish_event.set()
        return

    def set_detail_result(self, detail: AnswerDetail) -> None:
        """设置详细回答结果"""
        self._detail_result.put_nowait(detail)

    async def more_detail(self, timeout: float = 60.0) -> List[AnswerDetail]:
        """获取详细回答结果"""
        try:
            while not self._finish_event.is_set():
                try:
                    detail = self._detail_result.get_nowait()
                    yield detail
                except asyncio.TimeoutError:
                    pass
                if self._detail_result.empty():
                    await asyncio.wait_for(self._finish_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
