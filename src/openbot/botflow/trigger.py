from datetime import datetime, timedelta
from typing import List, Generator, Optional, Any, Literal, Tuple
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod


class _CronField:
    """Cron 表达式字段解析器。

    解析单个 cron 字段 (秒, 分, 时, 日, 月, 周)。
    支持格式:
    - 确定值: "5"
    - 范围: "1-5"
    - 步长: "*/5" 或 "1/5"
    - 列表: "1,3,5"
    - 任意: "*"
    """

    def __init__(self, value: str, min_val: int, max_val: int):
        """初始化 _CronField。

        Args:
            value: cron 字段值
            min_val: 允许的最小值
            max_val: 允许的最大值
        """
        self.min = min_val
        self.max = max_val
        self.values = self._parse_field(value)
        self.iter_index = 0

    def _parse_field(self, value: str) -> List[int]:
        """Parse cron field value.

        Args:
            value: field value to parse

        Returns:
            list of valid values
        """
        if value == "*":
            return list(range(self.min, self.max + 1))

        values = set()
        for part in value.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                values.update(range(start, end + 1))
            elif "/" in part:
                start_val, step = part.split("/")
                start = self.min if start_val == "*" else int(start_val)
                step = int(step)
                values.update(range(start, self.max + 1, step))
            else:
                values.add(int(part))
        return sorted(list(values))

    def __contains__(self, value: int) -> bool:
        """Check if value is allowed in this field."""
        return value in self.values

    def __iter__(self) -> Generator[int, None, None]:
        """Iterate over field values."""
        for idx in range(self.iter_index, len(self.values)):
            yield self.values[idx]
        self.iter_index = 0  # Reset the index to 0 after the loop

    def reset(self, value: Optional[int] = None) -> None:
        """Reset iteration starting index to first >= value."""

        self.iter_index = 0
        for idx, val in enumerate(self.values):
            if val >= value:
                self.iter_index = idx
                break


class _Cron:
    """Cron 表达式解析器。

    支持: 秒, 分, 时, 日, 月, 周。
    """

    def __init__(self, cron_expression: str, start_dt: Any = None, end_dt: Any = None):
        """初始化 _Cron。

        Args:
            cron_expression: cron 表达式字符串
            start_dt: 开始时间
            end_dt: 结束时间
        """
        self.cron_expression = cron_expression
        if start_dt is None:
            start_dt = datetime.now()
        if end_dt is None:
            end_dt = datetime.max
        self.start_dt = to_datetime(start_dt).replace(microsecond=0)
        self.end_dt = to_datetime(end_dt).replace(microsecond=0)

        fields = self.cron_expression.split()
        if len(fields) != 6:
            raise ValueError("Invalid cron expression format")

        second, minute, hour, day, month, weekday = fields

        self.seconds = _CronField(second, 0, 59)
        self.minutes = _CronField(minute, 0, 59)
        self.hours = _CronField(hour, 0, 23)
        self.days = _CronField(day, 1, 31)
        self.months = _CronField(month, 1, 12)
        self.weekdays = _CronField(weekday, 0, 6)

    def _initialize_fields(self, current_dt: datetime) -> datetime:
        """Initialize iteration indices based on current time."""

        current_dt = (
            current_dt.replace(microsecond=0)
            if current_dt
            else datetime.now().replace(microsecond=0)
        )

        self.seconds.reset(current_dt.second)
        self.minutes.reset(current_dt.minute)
        self.hours.reset(current_dt.hour)
        self.days.reset(current_dt.day)
        self.months.reset(current_dt.month)

        if current_dt.month <= self.months.values[-1]:
            self.months.reset(current_dt.month)
            if current_dt.day <= self.days.values[-1]:
                self.days.reset(current_dt.day)
                if current_dt.hour <= self.hours.values[-1]:
                    self.hours.reset(current_dt.hour)
                    if current_dt.minute <= self.minutes.values[-1]:
                        self.minutes.reset(current_dt.minute)
                        if current_dt.second <= self.seconds.values[-1]:
                            self.seconds.reset(current_dt.second)
        else:
            current_dt = current_dt.replace(
                year=current_dt.year + 1,
                month=self.months.values[0],
                day=self.days.values[0],
                hour=self.hours.values[0],
                minute=self.minutes.values[0],
                second=self.seconds.values[0],
                microsecond=0,
            )
        return current_dt

    def __call__(
        self, current_dt: Optional[datetime] = None
    ) -> Generator[datetime, None, None]:
        """Yield matching datetimes within range."""
        if current_dt is None:
            current_dt = datetime.now()

        current_dt = self._initialize_fields(current_dt)

        while current_dt <= self.end_dt:
            for month in self.months:
                for day in self.days:
                    try:
                        current_dt = current_dt.replace(
                            year=current_dt.year,
                            month=month,
                            day=day,
                        )
                        if current_dt.weekday() not in self.weekdays:
                            continue

                        for hour in self.hours:
                            for minute in self.minutes:
                                for second in self.seconds:
                                    current_dt = current_dt.replace(
                                        hour=hour, minute=minute, second=second
                                    )
                                    if current_dt >= self.start_dt:
                                        yield current_dt
                    except ValueError:
                        pass
            current_dt = current_dt.replace(
                year=current_dt.year + 1,
            )


class Trigger(BaseModel):
    """触发器基类接口。

    子类必须实现 get_next_fire_time 方法。
    """

    start_dt: datetime = Field(default_factory=datetime.now, description="触发开始时间")
    end_dt: datetime = Field(default_factory=datetime.max, description="触发结束时间")
    trigger_dt: datetime = Field(
        default_factory=datetime.now, description="当前触发时间"
    )
    interval: float = Field(default=0.0, description="触发间隔(秒)")
    cron_expression: str = Field(default="* * * * * *", description="Cron 表达式")
    skip_past: bool = Field(default=False, description="是否跳过过期时间")
    status: Literal["Ready", "Running", "Completed"] = Field(
        default="Ready", description="触发器状态"
    )

    def model_post_init(self, __context: Any, /) -> None:
        if self.start_dt > self.end_dt:
            raise ValueError(
                f"{self.start_dt=} must not be greater than {self.end_dt=}"
            )

        if not (self.start_dt <= self.trigger_dt <= self.end_dt):
            raise ValueError(
                f"{self.trigger_dt=} must be between {self.start_dt=} and {self.end_dt=}"
            )

    @abstractmethod
    def get_next_fire_time(
        self,
    ) -> Optional[Tuple[datetime, Literal["Ready", "Running", "Completed"]]]:
        """Get next fire time."""
        raise NotImplementedError

    @abstractmethod
    def get_first_fire_time(
        self,
    ) -> Optional[Tuple[datetime, Literal["Ready", "Running", "Completed"]]]:
        """Get first fire time."""
        raise NotImplementedError

    def __iter__(self) -> Generator[datetime, None, None]:
        self.status = "Ready"
        return self

    def __next__(self) -> datetime:
        if self.status == "Completed":
            raise StopIteration

        if self.status == "Ready":
            self.trigger_dt, self.status = self.get_first_fire_time()
        else:
            self.trigger_dt, self.status = self.get_next_fire_time()

        if self.status == "Completed":
            raise StopIteration

        return self

    def __lt__(self, other: "Trigger") -> bool:
        if isinstance(other, Trigger):
            return self.trigger_dt < other.trigger_dt
        return NotImplemented

    def __le__(self, other: "Trigger") -> bool:
        if isinstance(other, Trigger):
            return self.trigger_dt <= other.trigger_dt
        return NotImplemented

    def __gt__(self, other: "Trigger") -> bool:
        if isinstance(other, Trigger):
            return self.trigger_dt > other.trigger_dt
        return NotImplemented

    def __ge__(self, other: "Trigger") -> bool:
        if isinstance(other, Trigger):
            return self.trigger_dt >= other.trigger_dt
        return NotImplemented


class OnceTrigger(Trigger):
    """一次性触发器，在指定时间触发一次。"""

    def __init__(self, trigger_dt: datetime, skip_past: bool = False):
        """初始化 OnceTrigger。

        Args:
            trigger_dt: 触发时间
        """
        super().__init__(
            start_dt=trigger_dt,
            end_dt=trigger_dt,
            trigger_dt=trigger_dt,
            skip_past=skip_past,
            interval=0,
        )

    def get_next_fire_time(
        self,
    ) -> Optional[Tuple[datetime, Literal["Ready", "Running", "Completed"]]]:
        """Get next fire time for one-off trigger (always Completed)."""
        return datetime.max, "Completed"

    def get_first_fire_time(self) -> Optional[Tuple[datetime, Literal["Ready"]]]:
        """Get first fire time."""
        if self.skip_past and self.trigger_dt < datetime.now():
            return datetime.max, "Completed"
        else:
            return self.trigger_dt, "Running"


class IntervalTrigger(Trigger):
    """间隔触发器，在指定时间范围内按固定间隔重复触发。"""

    def __init__(
        self,
        interval: float,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
        skip_past: bool = False,
    ):
        """初始化 IntervalTrigger。

        Args:
            interval: 间隔秒数
            start_dt: 开始时间
            end_dt: 结束时间
            skip_past: 是否跳过过期时间
        """

        super().__init__(
            interval=interval,
            start_dt=start_dt,
            trigger_dt=start_dt,
            end_dt=end_dt,
            skip_past=skip_past,
        )

    def get_first_fire_time(self) -> Optional[datetime]:
        """Get first fire time."""
        if self.status in ["Running", "Completed"]:
            return self.trigger_dt, self.status

        if self.skip_past and self.trigger_dt < datetime.now():
            delta = timedelta(
                seconds=(datetime.now().timestamp() - self.start_dt.timestamp())
                // self.interval
                * self.interval
                + self.interval
            )
            self.trigger_dt = self.start_dt + delta
            if self.trigger_dt > self.end_dt:
                return datetime.max, "Completed"
            return self.trigger_dt, "Running"
        else:
            return self.trigger_dt, "Running"

    def get_next_fire_time(
        self,
    ) -> Optional[Tuple[datetime, Literal["Ready", "Running", "Completed"]]]:
        """Get next fire time or Completed when exceeding end time."""
        if (
            self.status == "Completed"
            or self.trigger_dt + timedelta(seconds=self.interval) > self.end_dt
        ):
            return datetime.max, "Completed"

        self.trigger_dt += timedelta(seconds=self.interval)
        return self.trigger_dt, "Running"


class CronTrigger(Trigger):
    """Cron 触发器，支持秒级精度和时间范围。"""

    def __init__(
        self,
        cron_expression: str,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
        skip_past: bool = False,
    ):
        """初始化 CronTrigger。

        Args:
            cron_expression: cron 表达式
            start_dt: 开始时间
            end_dt: 结束时间
            skip_past: 是否跳过过期时间
        """
        super().__init__(
            cron_expression=cron_expression,
            start_dt=start_dt,
            trigger_dt=start_dt,
            end_dt=end_dt,
            skip_past=skip_past,
        )

    def get_first_fire_time(self) -> Optional[Tuple[datetime, Literal["Ready"]]]:
        """Get first fire time."""
        if self.status in ["Running", "Completed"]:
            return self.trigger_dt, self.status

        self._cron = _Cron(
            cron_expression=self.cron_expression,
            start_dt=self.start_dt,
            end_dt=self.end_dt,
        )()
        for trigger_dt in self._cron:
            if self.skip_past and trigger_dt < datetime.now():
                continue
            elif trigger_dt > self.end_dt:
                return datetime.max, "Completed"
            else:
                return trigger_dt, "Running"
        return datetime.max, "Completed"

    def get_next_fire_time(
        self,
    ) -> Optional[Tuple[datetime, Literal["Ready", "Running", "Completed"]]]:
        """Get next fire time or Completed when exhausted."""
        if self.status == "Completed":
            return datetime.max, "Completed"

        try:
            trigger_dt = next(self._cron)
            if self.trigger_dt > self.end_dt:
                return datetime.max, "Completed"
        except StopIteration:
            return datetime.max, "Completed"

        return trigger_dt, "Running"


def once(fire_time: datetime) -> Trigger:
    """Decorator for a one-off trigger."""

    return OnceTrigger(fire_time)


def daily(
    time_str: str,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
    skip_past: bool = False,
) -> Trigger:
    """Decorator for a daily trigger at HH:MM:SS."""
    if start_dt is None:
        start_dt = datetime.now()
    if end_dt is None:
        end_dt = datetime.max
    hour, minute, second = map(int, time_str.split(":"))
    return CronTrigger(
        f"{second} {minute} {hour} * * *",
        start_dt=start_dt,
        end_dt=end_dt,
        skip_past=skip_past,
    )


def weekly(
    time_str: str,
    day_of_week: int,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
    skip_past: bool = False,
) -> Trigger:
    """Decorator for a weekly trigger at HH:MM:SS on specified weekday."""
    if start_dt is None:
        start_dt = datetime.now()
    if end_dt is None:
        end_dt = datetime.max
    hour, minute, second = map(int, time_str.split(":"))

    return CronTrigger(
        f"{second} {minute} {hour} * * {day_of_week}",
        start_dt=start_dt,
        end_dt=end_dt,
        skip_past=skip_past,
    )


def every(
    interval: float,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
    skip_past: bool = False,
) -> Trigger:
    """Decorator for an interval trigger."""
    start_dt = datetime.now() if start_dt is None else start_dt
    end_dt = datetime.max if end_dt is None else end_dt

    return IntervalTrigger(
        interval=interval, start_dt=start_dt, end_dt=end_dt, skip_past=skip_past
    )


def crontab(
    cron_expression: str,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
    skip_past: bool = False,
) -> Trigger:
    """Decorator for a cron-based trigger."""
    start_dt = datetime.now() if start_dt is None else start_dt
    end_dt = datetime.max if end_dt is None else end_dt
    return CronTrigger(
        cron_expression=cron_expression,
        start_dt=start_dt,
        end_dt=end_dt,
        skip_past=skip_past,
    )
