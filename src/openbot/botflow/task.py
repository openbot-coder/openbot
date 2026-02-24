import logging
import asyncio
import datetime
import inspect
from typing import Any, Callable, Dict, List, Optional, Union
from openbot.botflow.trigger import Trigger, once


class Task:
    def __init__(self, func: callable, *args: Any, **kwargs: Any) -> None:
        self.func = func
        self.args = args if args is not None else []
        self.kwargs = kwargs if kwargs is not None else {}

    async def run(self) -> None:
        """异步运行任务"""
        if inspect.iscoroutinefunction(self.func):
            return await self.func(*self.args, **self.kwargs)
        else:
            return await asyncio.to_thread(self.func, *self.args, **self.kwargs)


class TaskManager:
    def __init__(self, stop_event: asyncio.Event) -> None:
        self._task_queue = asyncio.PriorityQueue()
        self._new_task_condition = asyncio.Condition()
        self.stop_event = stop_event

    async def submit_task(self, task: Task, trigger: Trigger = None) -> None:
        """提交任务"""
        if trigger is None:
            trigger = once(datetime.datetime.now())

        async with self._new_task_condition:
            try:
                next(trigger)
                self._task_queue.put_nowait((trigger, task))
                self._new_task_condition.notify()
            except StopIteration:
                pass

    async def get_task(self) -> Task:
        """获取任务"""
        async with self._new_task_condition:
            try:
                while True:
                    if self._task_queue.empty():
                        await self._new_task_condition.wait()
                    else:
                        # 使用安全的方式获取队列元素
                        # 注意：这里仍然需要访问内部属性，但添加了异常处理
                        try:
                            # 获取队列中的第一个元素
                            tasks = list(self._task_queue._queue)
                            if not tasks:
                                continue
                            trigger, task = tasks[0]
                            if trigger.trigger_dt <= datetime.datetime.now():
                                break

                            wait_time = max(
                                0,
                                trigger.trigger_dt.timestamp()
                                - datetime.datetime.now().timestamp(),
                            )
                            await asyncio.wait_for(
                                self._new_task_condition.wait(),
                                timeout=wait_time,
                            )
                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            logging.error(f"Error in task queue: {e}")
                            continue

                self._task_queue.get_nowait()
                try:
                    next(trigger)
                    self._task_queue.put_nowait((trigger, task))
                    self._new_task_condition.notify()
                except StopIteration:
                    pass
                return task
            except asyncio.CancelledError:
                pass

    async def run(self) -> None:
        """运行任务队列"""
        while not self.stop_event.is_set():
            try:
                task = await self.get_task()
                await task.run()
            except asyncio.CancelledError:
                break
            except asyncio.TimeoutError:
                logging.error(f"Timeout running task: {task.func.__name__}")
            except Exception as e:
                logging.error(f"Error running task: {task.func.__name__} error: {e}")


if __name__ == "__main__":
    from openbot.botflow.trigger import every
    from vxutils import loggerConfig

    loggerConfig()

    def print_hello():
        logging.info("Hello, World!")

    async def main():
        stop_event = asyncio.Event()
        task_manager = TaskManager(stop_event)
        task = Task(print_hello)
        logging.info("Submitting task: print_hello")
        await task_manager.submit_task(task, every(interval=3))
        await task_manager.run()

    asyncio.run(main())
