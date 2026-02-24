import pytest
import asyncio
from datetime import datetime, timedelta
from openbot.botflow.task import Task, TaskManager
from openbot.botflow.trigger import OnceTrigger, IntervalTrigger


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class TestTask:
    """测试 Task 类"""

    def test_task_creation(self):
        """测试任务创建"""
        
        def test_func(a, b):
            return a + b
        
        task = Task(name="test_task", func=test_func, args=(1, 2))
        
        assert task.name == "test_task"
        assert task.func == test_func
        assert task.args == (1, 2)
        assert task.trigger is None
        assert task.trigger_dt is None

    @pytest.mark.asyncio
    async def test_task_run_async(self):
        """测试异步任务运行"""
        results = []
        
        async def test_func():
            results.append("executed")
        
        task = Task(name="test", func=test_func)
        await task.run()
        
        assert results == ["executed"]

    @pytest.mark.asyncio
    async def test_task_run_sync(self):
        """测试同步任务运行"""
        results = []
        
        def test_func():
            results.append("executed")
        
        task = Task(name="test", func=test_func)
        await task.run()
        
        assert results == ["executed"]

    @pytest.mark.asyncio
    async def test_task_with_trigger(self):
        """测试带触发器的任务"""
        trigger_dt = datetime.now() + timedelta(seconds=1)
        trigger = OnceTrigger(trigger_dt=trigger_dt)
        
        async def test_func():
            pass
        
        task = Task(name="test", func=test_func)
        task.set_trigger(trigger)
        
        assert task.trigger is trigger
        assert task.trigger_dt is not None


class TestTaskManager:
    """测试 TaskManager 类"""

    @pytest.mark.asyncio
    async def test_task_manager_submit(self):
        """测试提交任务"""
        manager = TaskManager()
        
        async def test_func():
            return "done"
        
        task = Task(name="test", func=test_func)
        manager.submit(task)
        
        assert len(manager.list_tasks()) == 1
        assert len(manager.list_coroutines()) == 1

    @pytest.mark.asyncio
    async def test_task_manager_close(self):
        """测试关闭任务管理器"""
        manager = TaskManager()
        
        async def test_func():
            await asyncio.sleep(10)
        
        task = Task(name="test", func=test_func)
        manager.submit(task)
        
        manager.close()
        
        assert len(manager.list_tasks()) == 0

    @pytest.mark.asyncio
    async def test_task_manager_start(self):
        """测试启动任务管理器"""
        manager = TaskManager()
        
        await manager.start()
        
        assert manager._running is True
