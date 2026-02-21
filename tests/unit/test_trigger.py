import pytest
from datetime import datetime, timedelta
from openbot.botflow.trigger import (
    _CronField,
    _Cron,
    Trigger,
    OnceTrigger,
    IntervalTrigger,
    CronTrigger,
    once,
    daily,
    weekly,
    every,
    crontab
)


class TestCronField:
    """测试 _CronField 类的功能"""

    def test_parse_star_field(self):
        """测试解析 '*' 字段"""
        field = _CronField("*", 0, 59)
        assert len(field.values) == 60
        assert field.values[0] == 0
        assert field.values[-1] == 59

    def test_parse_range_field(self):
        """测试解析范围字段"""
        field = _CronField("1-5", 0, 59)
        assert field.values == [1, 2, 3, 4, 5]

    def test_parse_step_field(self):
        """测试解析步长字段"""
        field = _CronField("*/5", 0, 59)
        assert field.values == [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]

    def test_parse_list_field(self):
        """测试解析列表字段"""
        field = _CronField("1,3,5", 0, 59)
        assert field.values == [1, 3, 5]

    def test_contains_method(self):
        """测试 __contains__ 方法"""
        field = _CronField("1,3,5", 0, 59)
        assert 3 in field
        assert 4 not in field

    def test_iter_method(self):
        """测试 __iter__ 方法"""
        field = _CronField("1,3,5", 0, 59)
        values = list(field)
        assert values == [1, 3, 5]
        # 测试迭代后索引重置
        values2 = list(field)
        assert values2 == [1, 3, 5]

    def test_reset_method(self):
        """测试 reset 方法"""
        field = _CronField("1,3,5,7,9", 0, 9)
        field.reset(4)
        values = list(field)
        assert values == [5, 7, 9]


class TestCron:
    """测试 _Cron 类的功能"""

    def test_cron_basic(self):
        """测试基本的 cron 表达式"""
        start_dt = datetime(2023, 1, 1, 0, 0, 0)
        end_dt = datetime(2023, 1, 1, 0, 0, 5)
        cron = _Cron("* * * * * *", start_dt, end_dt)
        times = list(cron())
        assert len(times) > 0

    def test_cron_specific_time(self):
        """测试特定时间的 cron 表达式"""
        start_dt = datetime(2023, 1, 1, 0, 0, 0)
        end_dt = datetime(2023, 1, 1, 0, 0, 10)
        cron = _Cron("5 * * * * *", start_dt, end_dt)
        times = list(cron())
        assert any(t.second == 5 for t in times)


class TestOnceTrigger:
    """测试 OnceTrigger 类的功能"""

    def test_once_trigger_initialization(self):
        """测试 OnceTrigger 初始化"""
        fire_time = datetime.now() + timedelta(seconds=10)
        trigger = OnceTrigger(fire_time)
        assert trigger.trigger_dt == fire_time
        assert trigger.status == "Ready"

    def test_once_trigger_get_first_fire_time(self):
        """测试 OnceTrigger 获取第一次触发时间"""
        fire_time = datetime.now() + timedelta(seconds=10)
        trigger = OnceTrigger(fire_time)
        fire_time_result, status = trigger.get_first_fire_time()
        assert fire_time_result == fire_time
        assert status == "Running"

    def test_once_trigger_get_next_fire_time(self):
        """测试 OnceTrigger 获取下一次触发时间"""
        fire_time = datetime.now() + timedelta(seconds=10)
        trigger = OnceTrigger(fire_time)
        fire_time_result, status = trigger.get_next_fire_time()
        assert status == "Completed"

    def test_once_trigger_skip_past(self):
        """测试 OnceTrigger 跳过过去的时间"""
        fire_time = datetime.now() - timedelta(seconds=10)
        trigger = OnceTrigger(fire_time, skip_past=True)
        fire_time_result, status = trigger.get_first_fire_time()
        assert status == "Completed"


class TestIntervalTrigger:
    """测试 IntervalTrigger 类的功能"""

    def test_interval_trigger_initialization(self):
        """测试 IntervalTrigger 初始化"""
        start_dt = datetime.now()
        interval = 5.0
        trigger = IntervalTrigger(interval, start_dt)
        assert trigger.interval == interval
        assert trigger.start_dt == start_dt
        assert trigger.status == "Ready"

    def test_interval_trigger_get_first_fire_time(self):
        """测试 IntervalTrigger 获取第一次触发时间"""
        start_dt = datetime.now()
        interval = 5.0
        trigger = IntervalTrigger(interval, start_dt)
        fire_time_result, status = trigger.get_first_fire_time()
        assert fire_time_result == start_dt
        assert status == "Running"

    def test_interval_trigger_get_next_fire_time(self):
        """测试 IntervalTrigger 获取下一次触发时间"""
        start_dt = datetime.now()
        interval = 5.0
        trigger = IntervalTrigger(interval, start_dt)
        # 先获取第一次触发时间
        trigger.get_first_fire_time()
        # 再获取下一次触发时间
        fire_time_result, status = trigger.get_next_fire_time()
        expected_time = start_dt + timedelta(seconds=interval)
        assert abs((fire_time_result - expected_time).total_seconds()) < 0.1
        assert status == "Running"

    def test_interval_trigger_completed(self):
        """测试 IntervalTrigger 完成状态"""
        start_dt = datetime.now()
        end_dt = start_dt + timedelta(seconds=8)
        interval = 5.0
        trigger = IntervalTrigger(interval, start_dt, end_dt)
        # 第一次触发
        trigger.get_first_fire_time()
        # 第二次触发
        trigger.get_next_fire_time()
        # 第三次触发应该完成
        fire_time_result, status = trigger.get_next_fire_time()
        assert status == "Completed"

    def test_interval_trigger_skip_past(self):
        """测试 IntervalTrigger 跳过过去的时间"""
        start_dt = datetime.now() - timedelta(seconds=20)
        interval = 5.0
        trigger = IntervalTrigger(interval, start_dt, skip_past=True)
        fire_time_result, status = trigger.get_first_fire_time()
        assert fire_time_result > datetime.now()
        assert status == "Running"


class TestCronTrigger:
    """测试 CronTrigger 类的功能"""

    def test_cron_trigger_initialization(self):
        """测试 CronTrigger 初始化"""
        cron_expr = "0 0 * * * *"
        start_dt = datetime.now()
        trigger = CronTrigger(cron_expr, start_dt)
        assert trigger.cron_expression == cron_expr
        assert trigger.start_dt == start_dt
        assert trigger.status == "Ready"

    def test_cron_trigger_get_first_fire_time(self):
        """测试 CronTrigger 获取第一次触发时间"""
        # 创建一个将在未来几秒内触发的 cron 表达式
        now = datetime.now()
        cron_expr = f"{now.second + 2} {now.minute} {now.hour} * * *"
        start_dt = now
        end_dt = now + timedelta(minutes=1)
        trigger = CronTrigger(cron_expr, start_dt, end_dt)
        fire_time_result, status = trigger.get_first_fire_time()
        assert status == "Running"

    def test_cron_trigger_get_next_fire_time(self):
        """测试 CronTrigger 获取下一次触发时间"""
        # 创建一个每分钟触发一次的 cron 表达式
        cron_expr = "0 * * * * *"
        start_dt = datetime.now()
        end_dt = start_dt + timedelta(minutes=2)
        trigger = CronTrigger(cron_expr, start_dt, end_dt)
        # 先获取第一次触发时间
        trigger.get_first_fire_time()
        # 再获取下一次触发时间
        fire_time_result, status = trigger.get_next_fire_time()
        assert status == "Running"

    def test_cron_trigger_completed(self):
        """测试 CronTrigger 完成状态"""
        # 创建一个在过去触发的 cron 表达式
        now = datetime.now()
        cron_expr = f"{now.second - 10} {now.minute} {now.hour} * * *"
        start_dt = now - timedelta(minutes=1)
        end_dt = now - timedelta(seconds=5)
        trigger = CronTrigger(cron_expr, start_dt, end_dt)
        fire_time_result, status = trigger.get_first_fire_time()
        assert status == "Completed"


class TestTriggerHelpers:
    """测试触发器辅助函数"""

    def test_once_helper(self):
        """测试 once 辅助函数"""
        fire_time = datetime.now() + timedelta(seconds=10)
        trigger = once(fire_time)
        assert isinstance(trigger, OnceTrigger)
        assert trigger.trigger_dt == fire_time

    def test_daily_helper(self):
        """测试 daily 辅助函数"""
        time_str = "12:00:00"
        trigger = daily(time_str)
        assert isinstance(trigger, CronTrigger)
        assert trigger.cron_expression == "0 0 12 * * *"

    def test_weekly_helper(self):
        """测试 weekly 辅助函数"""
        time_str = "12:00:00"
        day_of_week = 1  # 周一
        trigger = weekly(time_str, day_of_week)
        assert isinstance(trigger, CronTrigger)
        assert trigger.cron_expression == "0 0 12 * * 1"

    def test_every_helper(self):
        """测试 every 辅助函数"""
        interval = 60.0
        trigger = every(interval)
        assert isinstance(trigger, IntervalTrigger)
        assert trigger.interval == interval

    def test_crontab_helper(self):
        """测试 crontab 辅助函数"""
        cron_expr = "0 0 * * * *"
        trigger = crontab(cron_expr)
        assert isinstance(trigger, CronTrigger)
        assert trigger.cron_expression == cron_expr


class TestTriggerComparison:
    """测试触发器的比较功能"""

    def test_trigger_comparison(self):
        """测试触发器的比较操作"""
        now = datetime.now()
        trigger1 = OnceTrigger(now + timedelta(seconds=10))
        trigger2 = OnceTrigger(now + timedelta(seconds=20))
        assert trigger1 < trigger2
        assert trigger2 > trigger1
        assert trigger1 <= trigger2
        assert trigger2 >= trigger1

    def test_trigger_equality(self):
        """测试触发器的相等性"""
        now = datetime.now()
        trigger1 = OnceTrigger(now + timedelta(seconds=10))
        trigger2 = OnceTrigger(now + timedelta(seconds=10))
        assert not (trigger1 < trigger2)
        assert not (trigger1 > trigger2)
        assert trigger1 <= trigger2
        assert trigger1 >= trigger2


if __name__ == "__main__":
    pytest.main([__file__])
