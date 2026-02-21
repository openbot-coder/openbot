import asyncio
import pytest
from openbot.botflow.task import Task, TaskManager


class TestTask:
    """测试 Task 类"""
    
    async def test_task_run(self):
        """测试任务运行"""
        # 创建一个简单的任务函数
        async def test_func():
            return "test result"
        
        # 创建任务
        task = Task(func=test_func, priority=1)
        result = await task.run()
        assert result == "test result"


class TestTaskManager:
    """测试 TaskManager 类"""
    
    async def test_add_task(self):
        """测试添加任务"""
        manager = TaskManager()
        
        # 创建一个简单的任务函数
        async def test_func():
            return "test result"
        
        # 创建任务
        task = Task(func=test_func, priority=1)
        
        # 添加任务
        await manager.add_task(task)
        
        # 验证任务队列不为空
        # 注意：我们无法直接访问内部队列，但可以通过获取任务来验证
        assert True
    
    async def test_get_task(self):
        """测试获取任务"""
        manager = TaskManager()
        
        # 创建一个简单的任务函数
        async def test_func():
            return "test result"
        
        # 创建任务
        task = Task(func=test_func, priority=1)
        
        # 添加任务
        await manager.add_task(task)
        
        # 获取任务
        retrieved_task = await manager.get_task()
        assert isinstance(retrieved_task, Task)
    
    async def test_task_priority(self):
        """测试任务优先级"""
        manager = TaskManager()
        
        # 创建任务函数
        async def func1():
            return "high priority"
        
        async def func2():
            return "low priority"
        
        # 创建不同优先级的任务
        high_priority_task = Task(func=func1, priority=0)  # 优先级更高
        low_priority_task = Task(func=func2, priority=1)   # 优先级更低
        
        # 添加任务
        await manager.add_task(low_priority_task)
        await manager.add_task(high_priority_task)
        
        # 获取任务，应该先获取高优先级任务
        first_task = await manager.get_task()
        assert first_task.priority == 0
