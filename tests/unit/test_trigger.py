import pytest
from datetime import datetime, timedelta
from openbot.botflow.trigger import (
    Trigger,
    OnceTrigger,
    IntervalTrigger,
    CronTrigger,
    TriggerStatus,
)


class TestOnceTrigger:
    """测试 OnceTrigger 一次性触发器"""

    def test_once_trigger_returns_time(self):
        """测试一次性触发器返回触发时间"""
        trigger_dt = datetime.now() + timedelta(seconds=10)
        trigger = OnceTrigger(trigger_dt=trigger_dt)
        
        result = trigger.next()
        
        assert result == trigger_dt
        assert trigger.status == TriggerStatus.COMPLETED

    def test_once_trigger_returns_none_after_completed(self):
        """测试完成后返回 None"""
        trigger_dt = datetime.now()
        trigger = OnceTrigger(trigger_dt=trigger_dt)
        
        # 第一次触发
        trigger.next()
        
        # 第二次应该返回 None
        result = trigger.next()
        assert result is None


class TestIntervalTrigger:
    """测试 IntervalTrigger 间隔触发器"""

    def test_interval_trigger_returns_next_time(self):
        """测试间隔触发器返回下一次触发时间"""
        trigger_dt = datetime.now()
        trigger = IntervalTrigger(trigger_dt=trigger_dt, interval=60)
        
        result = trigger.next()
        
        assert result == trigger_dt + timedelta(seconds=60)

    def test_interval_trigger_updates_trigger_dt(self):
        """测试触发器更新 trigger_dt"""
        trigger_dt = datetime(2024, 1, 1, 12, 0, 0)
        trigger = IntervalTrigger(trigger_dt=trigger_dt, interval=60)
        
        trigger.next()
        
        assert trigger.trigger_dt == datetime(2024, 1, 1, 12, 1, 0)

    def test_interval_trigger_with_end_dt(self):
        """测试带结束时间的间隔触发器"""
        trigger_dt = datetime(2024, 1, 1, 12, 0, 0)
        end_dt = datetime(2024, 1, 1, 12, 0, 30)
        trigger = IntervalTrigger(trigger_dt=trigger_dt, interval=60, end_dt=end_dt)
        
        # 第一次触发后，next_dt = 12:01:00 > end_dt = 12:00:30
        result = trigger.next()
        
        assert result is None
        assert trigger.status == TriggerStatus.COMPLETED


class TestCronTrigger:
    """测试 CronTrigger"""

    def test_cron_trigger_returns_next_second(self):
        """测试 Cron 触发器每秒触发"""
        trigger_dt = datetime.now()
        trigger = CronTrigger(trigger_dt=trigger_dt)
        
        result = trigger.next()
        
        assert result == trigger_dt + timedelta(seconds=1)


class TestTriggerComparison:
    """测试触发器比较"""

    def test_trigger_comparison(self):
        """测试触发器按时间排序"""
        t1 = OnceTrigger(trigger_dt=datetime(2024, 1, 1, 12, 0, 0))
        t2 = OnceTrigger(trigger_dt=datetime(2024, 1, 1, 12, 0, 1))
        
        assert t1 < t2

    def test_trigger_equality(self):
        """测试触发器相等"""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        t1 = OnceTrigger(trigger_dt=dt)
        t2 = OnceTrigger(trigger_dt=dt)
        
        # 不同实例，可能不相等
        assert t1.trigger_dt == t2.trigger_dt
