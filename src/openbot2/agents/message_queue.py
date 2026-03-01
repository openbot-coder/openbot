"""消息队列系统"""

import asyncio
import uuid
from typing import Dict, Any, Optional, Callable


class MessageQueue:
    """消息队列"""

    def __init__(self):
        self._queue = asyncio.Queue()
        self._tasks: Dict[str, asyncio.Future] = {}

    async def put(self, task: Dict[str, Any]) -> str:
        """放入任务，返回任务ID"""
        task_id = str(uuid.uuid4())
        task["task_id"] = task_id
        await self._queue.put(task)
        return task_id

    async def get(self) -> Dict[str, Any]:
        """获取任务"""
        return await self._queue.get()

    def task_done(self):
        """标记任务完成"""
        self._queue.task_done()

    def create_task_future(self, task_id: str) -> asyncio.Future:
        """创建任务的Future"""
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._tasks[task_id] = future
        return future

    def set_task_result(self, task_id: str, result: Any):
        """设置任务结果"""
        if task_id in self._tasks:
            future = self._tasks[task_id]
            if not future.done():
                future.set_result(result)
            del self._tasks[task_id]

    def set_task_exception(self, task_id: str, exception: Exception):
        """设置任务异常"""
        if task_id in self._tasks:
            future = self._tasks[task_id]
            if not future.done():
                future.set_exception(exception)
            del self._tasks[task_id]
