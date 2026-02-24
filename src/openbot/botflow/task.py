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
from .trigger import Trigger


class Task:
    """任务类（函数式设计）"""
    
    def __init__(self, name: str, func: Callable, *args: Any, **kwargs: Any) -> None:
        self.id = str(uuid.uuid4())
        self.name = name
        self.trigger = None
        self.trigger_dt = None  # 添加 trigger_dt 属性
        self.created_at = datetime.now()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def set_trigger(self, trigger: Trigger):
        self.trigger = trigger
        self.trigger_dt = self.trigger.next()

    async def run(self):
        """执行任务"""
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
            if self.trigger:
                self.trigger_dt = self.trigger.next()
            else:
                self.trigger_dt = None


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
        return self._tasks
    
    def list_coroutines(self):
        return self._coroutines
    
    def close(self):
        for coroutine in self._coroutines:
            coroutine.cancel()
        self._coroutines.clear()
        self._tasks.clear()
