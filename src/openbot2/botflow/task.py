"""BotFlow 任务模块 - 统一的任务系统"""

import asyncio
import uuid
import logging
import inspect
from datetime import datetime
from enum import Enum
from heapq import heappush, heappop
from typing import Any, Callable, Dict, List, Optional

# 导入 Trigger（从 trigger.py）
from openbot.botflow.trigger import Trigger


class Task:
    """任务类（函数式设计）"""

    def __init__(
        self,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
    ) -> None:
        if kwargs is None:
            kwargs = {}
        self.id = str(uuid.uuid4())
        self.name = name
        self.trigger = None
        self.trigger_dt = None
        self.created_at = datetime.now()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def set_trigger(self, trigger: Trigger):
        try:
            self.trigger = trigger
            next(self.trigger)
            self.trigger_dt = self.trigger.trigger_dt
        except StopIteration:
            self.trigger_dt = None
            logging.error(f"任务 {self.name} 触发器 {trigger} 已过期")
            return

    async def run(self):
        """执行任务"""
        # 如果没有触发器，执行一次
        if not self.trigger:
            if inspect.iscoroutinefunction(self.func):
                await self.func(*self.args, **self.kwargs)
            else:
                await asyncio.to_thread(self.func, *self.args, **self.kwargs)
            return

        # 有触发器，循环执行
        try:
            while self.trigger_dt:
                now = datetime.now()
                if self.trigger_dt > now:
                    await asyncio.sleep((self.trigger_dt - now).total_seconds())

                # 执行任务（无论是否等待，都执行）
                if inspect.iscoroutinefunction(self.func):
                    await self.func(*self.args, **self.kwargs)
                else:
                    await asyncio.to_thread(self.func, *self.args, **self.kwargs)

                # 获取下次触发时间
                next(self.trigger)
                self.trigger_dt = self.trigger.trigger_dt
        except StopIteration:
            pass
        except Exception as e:
            logging.error(f"任务 {self.name} 执行时出错: {e}")


class TaskManager:
    """任务管理器"""

    def __init__(self):
        self._tasks: List[Task] = []
        self._coroutines: List[asyncio.Task] = []
        self._running = False

    async def start(self):
        self._running = True

    def submit(self, task: Task):
        self._tasks.append(task)
        self._coroutines.append(asyncio.create_task(task.run()))

    def list_tasks(self):
        """列出所有任务"""
        return self._tasks

    def list_coroutines(self):
        """列出所有任务的协程"""
        return self._coroutines

    def close(self):
        for coroutine in self._coroutines:
            coroutine.cancel()
        self._coroutines.clear()
        self._tasks.clear()


if __name__ == "__main__":
    from openbot.botflow.trigger import every
    from datetime import timedelta

    async def test_task():
        print("Hello, world!")

    task = Task("test_task", test_task)
    task.set_trigger(every(1, end_dt=datetime.now() + timedelta(seconds=10)))
    print(task.trigger_dt)
    asyncio.run(task.run())
