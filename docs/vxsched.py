"""
VXSched: A lightweight event scheduler.
All-in-one file merged from: config.py, trigger.py, base.py, cli.py
"""

import os
import json
import pickle
import logging
import threading
from threading import Event as ThreadingEvent, Thread, current_thread
import time
import uuid
import importlib.util
from abc import abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import (
    Optional,
    Generator,
    Literal,
    List,
    Any,
    Tuple,
    Dict,
    Callable,
    DefaultDict,
    Set,
    Union,
)
from heapq import heappush, heappop
from contextlib import suppress
from collections import defaultdict
from concurrent.futures import Future
from queue import Empty
from argparse import ArgumentParser

# External dependencies (assuming these are installed)
from pydantic import Field
from vxutils import to_datetime, VXDataModel, VXThreadPoolExecutor, loggerConfig


# ==========================================
# Part 1: Configuration (from config.py)
# ==========================================


def _freeze(obj: Any) -> Any:
    if isinstance(obj, (MappingProxyType, dict)):
        return MappingProxyType({k: _freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(_freeze(v) for v in obj)
    if isinstance(obj, (frozenset, set)):
        return frozenset(_freeze(v) for v in obj)
    return obj


def _release(obj: Any) -> Any:
    if isinstance(obj, (MappingProxyType, dict)):
        return {k: _release(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [_release(v) for v in obj]
    if isinstance(obj, (frozenset, set)):
        return set(_release(v) for v in obj)
    return obj


class Config:
    """配置类，用于管理应用程序配置。
    配置项是只读的，不可变对象。
    """

    def __init__(
        self,
        **config_item: Any,
    ) -> None:
        for k, v in config_item.items():
            self.__dict__[k] = _freeze(v)
            if k == "env":
                for env_name, env_value in v.items():
                    os.environ[env_name] = env_value
                    logging.debug(f"Set Enviornment Variable `{env_name}` to *********")

    @classmethod
    def load(cls, config_file: str = "vxsched.json") -> Dict[str, Any]:
        """从 JSON 文件加载配置。"""
        config_file = Path(config_file)
        if not config_file.exists():
            logging.error(f"File {config_file} not found")
            return cls()

        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
            return cls(**config)

    def save(self, config_file: str = "vxsched.json") -> None:
        """保存配置到 JSON 文件。"""
        config_file = Path(config_file)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(_release(self.__dict__), f, ensure_ascii=False, indent=4)

    def get(self, key: str, default: any = None) -> any:
        return self.__dict__.get(key, default)

    def __iter__(self):
        return iter(self.__dict__)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __contains__(self, key: str) -> bool:
        return key in self.__dict__

    def __setitem__(self, key: str, value: any) -> None:
        raise RuntimeError(f"Key {key} is not allowed")

    def __getitem__(self, key: str) -> any:
        return self.__dict__[key]

    def __setattr__(self, name: str, value: any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            raise RuntimeError(f"Key '{name}' is Readonly")

    def __str__(self) -> str:
        return str(self.__dict__)

    def __repr__(self) -> str:
        return self.__str__()


class Params:
    """参数类，用于管理应用程序持久化参数。
    支持 pickle 序列化保存。
    """

    def __init__(self) -> None:
        self.__save_params__ = {}

    def __getstate__(self) -> Dict[str, Any]:
        """获取对象状态，用于 pickle 序列化。"""
        state = self.__save_params__.copy()
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """从状态恢复对象，用于 pickle 反序列化。"""
        self.__dict__: Dict[str, Any] = {}
        self.__dict__.update(state)

        self.__save_params__: Dict[str, Any] = {}
        self.__save_params__.update(state)

    def __getitem__(self, key: str) -> any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(f"Key {key} not found")

    def set_params(self, name: str, value: Any, persist: bool = False) -> None:
        """设置参数。

        Args:
            name: 参数名
            value: 参数值
            persist: 是否需要持久化保存
        """
        if persist:
            self.__save_params__[name] = value
        setattr(self, name, value)


# ==========================================
# Part 2: Triggers (from trigger.py)
# ==========================================


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


class Trigger(VXDataModel):
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


# ==========================================
# Part 3: Base Logic (from base.py)
# ==========================================

INIT_EVENT = "__INIT__"
SHUTDOWN_EVENT = "__SHUTDOWN__"
RESERVED_EVENTS = {INIT_EVENT, SHUTDOWN_EVENT}


class Event(VXDataModel):
    """事件模型"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8], description="事件 ID")
    type: str = Field(description="事件类型")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="事件数据")
    priority: int = Field(default=10, description="事件优先级")
    channel: str = Field(default="default", description="事件通道")
    reply_to: str = Field(default="", description="回复通道")

    def __lt__(self, other: "Event") -> bool:
        if isinstance(other, Event):
            return self.priority < other.priority
        return NotImplemented

    def __le__(self, other: "Event") -> bool:
        if isinstance(other, Event):
            return self.priority <= other.priority
        return NotImplemented

    def __gt__(self, other: "Event") -> bool:
        if isinstance(other, Event):
            return self.priority > other.priority
        return NotImplemented

    def __ge__(self, other: "Event") -> bool:
        if isinstance(other, Event):
            return self.priority >= other.priority
        return NotImplemented


class _EventQueue:
    """事件队列"""

    def __init__(self):
        self._queue: List[Tuple[Trigger, Any]] = []
        self.mutex = threading.Lock()
        self.not_empty = threading.Condition(self.mutex)

    def _qsize(self):
        now = datetime.now()
        return len([1 for _, t, _ in self._queue if t.trigger_dt <= now])

    @property
    def queue(self) -> List[Tuple[Trigger, Any]]:
        """返回所有任务列表以供调试。"""
        return self._queue

    def qsize(self) -> int:
        """返回队列大小"""
        with self.mutex:
            return self._qsize()

    def empty(self):
        """如果队列为空返回 True，否则返回 False（不可靠！）。"""
        with self.mutex:
            return self._qsize() == 0

    def put(self, event: "Event", trigger: Optional[Trigger] = None) -> None:
        """将项目放入队列。"""
        if trigger is None:
            trigger = once(fire_time=datetime.now())

        with self.mutex:
            self._put(event, trigger=trigger)
            self.not_empty.notify()

    # Put a new item in the queue
    def _put(self, event: "Event", trigger: Trigger) -> None:
        with suppress(StopIteration):
            next(trigger)
            heappush(self._queue, (event.priority, trigger, event))

    def get(self, block=True, timeout=None) -> Optional["Event"]:
        """从队列中移除并返回一个项目。"""
        with self.not_empty:
            if not block and (not self._qsize()):
                raise Empty

            if timeout is not None and timeout <= 0:
                raise ValueError("'timeout' must be a non-negative number")

            if timeout is not None:
                endtime = datetime.now().timestamp() + timeout
            else:
                endtime = float("inf")

            while not self._qsize():
                now = datetime.now().timestamp()
                if now >= endtime:
                    raise Empty

                lastest_trigger_dt = (
                    endtime
                    if len(self._queue) == 0
                    else self._queue[0][1].trigger_dt.timestamp()
                )
                min_endtime = min(endtime, lastest_trigger_dt, now + 1)
                remaining = min_endtime - now
                self.not_empty.wait(remaining)
            event = self._get()
            return event

    def get_nowait(self) -> Event:
        """相当于 get(block=False)。"""
        return self.get(block=False)

    def _get(self) -> Event:
        _, trigger, event = heappop(self._queue)
        if trigger.status != "Completed":
            self._put(event, trigger)
            self.not_empty.notify()
        return event

    def clear(self) -> None:
        """清空队列中的所有事件。"""
        with self.mutex:
            self._queue.clear()


def _run_handler(
    handler: Callable[["Scheduler", Event], Any],
    app: "Scheduler",
    event: Event,
) -> Any:
    """运行事件处理器"""
    try:
        return handler(app, event)
    except Exception as e:
        logging.error(
            f"Error in handler {handler.__name__}: {e}", exc_info=True, stack_info=True
        )


class Scheduler:
    """
    调度器基类。
    """

    executor: VXThreadPoolExecutor = VXThreadPoolExecutor()

    def __init__(
        self,
        config: Optional[Dict[str, str]] = None,
    ):
        self._handlers: DefaultDict[str, List[Callable[...]]] = defaultdict(list)
        self._event_queue = _EventQueue()
        self._stop_mutex = ThreadingEvent()
        self._stop_mutex.set()
        self._config = Config(**(config or {}))
        self._params: Params = Params()
        self._workers: Set[Thread] = set()

    def __call__(
        self,
        event_type: str,
    ) -> None:
        """通过装饰器注册处理器"""

        def wrapper(handler: Callable[[Event, Dict[str, Any]], Any]) -> None:
            self.register(event_type, handler)
            return handler

        return wrapper

    def register(
        self,
        event_type: str,
        handler: Optional[Callable[["Scheduler", Event], Any]] = None,
    ) -> Callable[Callable[["Scheduler", Event], Any], Any]:
        """注册处理器"""
        if handler is not None:
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)
                logging.debug(
                    f"Register handler {handler.__name__} to event type {event_type}"
                )
            return handler
        else:

            def wrapper(hdlr: Callable[[Event, Dict[str, Any]], Any]) -> None:
                return self.register(event_type, hdlr)

            return wrapper

    def unregister(
        self,
        event_type: str,
        handler: Optional[Callable[[Event, Dict[str, Any]], Any]] = None,
    ) -> None:
        """注销事件处理器"""
        if handler is None:
            handlers = self._handlers.pop(event_type, [])
            for hdlr in handlers:
                logging.warning(
                    f"Unregister handler {hdlr.__name__} from event type {event_type}"
                )
        elif handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logging.warning(
                f"Unregister handler {handler.__name__} from event type {event_type}"
            )
        else:
            logging.error(
                f"Handler {handler.__name__} not registered to event type {event_type}"
            )

    def dispatch(self, event: Event, *, wait: bool = False) -> Optional[List[Any]]:
        """分发事件到处理器"""
        results: List[Future] = [
            self.executor.submit(_run_handler, handler, self, event)
            for handler in self._handlers[event.type]
        ]
        return [r.result() for r in results] if wait else results

    def include(self, scheduler: "Scheduler") -> None:
        """包含其他调度器的处理器"""
        for event_type, hdls in scheduler._handlers.items():
            for handler in hdls:
                if handler not in self._handlers[event_type]:
                    self._handlers[event_type].append(handler)
                    logging.warning(
                        f"Include handler {handler.__name__} to event type {event_type}"
                    )
                else:
                    logging.warning(
                        f"Handler {handler.__name__} already registered to event type {event_type}"
                    )

    @property
    def config(self) -> Dict[str, Any]:
        """获取配置。"""
        return self._config

    @property
    def params(self) -> Params:
        """获取参数。"""
        return self._params

    def run(self) -> None:
        """运行调度器。"""
        logging.debug(
            f"{self.__class__.__name__} worker({current_thread().name}) started."
        )
        while not self._stop_mutex.is_set():
            try:
                event = self._event_queue.get(timeout=1)
                self.dispatch(event=event, wait=False)
            except Empty:
                continue
            except Exception as e:
                logging.error(
                    f"Error handling event {event}: {e}",
                    exc_info=True,
                    stack_info=True,
                )
        logging.debug(
            f"{self.__class__.__name__} worker({current_thread().name}) stopped."
        )

    def _initialize(self) -> bool:
        """初始化调度器。"""
        if not self._stop_mutex.is_set():
            logging.warning(f"{self.__class__.__name__} scheduler is already started.")
            return False

        try:
            self._stop_mutex.clear()
            self.dispatch(event=Event(type=INIT_EVENT), wait=True)
            logging.info(
                f"{self.__class__.__name__} {INIT_EVENT} event handled successfully."
            )
        except Exception as e:
            logging.error(
                f"Error handling {INIT_EVENT} event: {e}",
                exc_info=True,
                stack_info=True,
            )
            self._stop_mutex.set()
            return False
        return True

    def stop(self) -> None:
        """停止调度器。"""
        if self._stop_mutex.is_set():
            logging.warning(f"{self.__class__.__name__} scheduler is already stopped.")
            return

        try:
            self._stop_mutex.set()
            for worker in self._workers:
                worker.join()
            self._workers.clear()

            self.dispatch(event=Event(type=SHUTDOWN_EVENT), wait=True)
            if not (Path(".") / ".vxsched").exists():
                (Path(".") / ".vxsched").mkdir(parents=True)

            with open(Path(".") / ".vxsched" / "params.pkl", "wb") as f:
                pickle.dump(self._params, f)
                logging.warning(f"Save params to {Path('.') / '.vxsched/params.pkl'}")
            logging.info(
                f"{self.__class__.__name__} {SHUTDOWN_EVENT} event handled successfully."
            )

        except Exception as e:
            logging.error(
                f"Error handling {SHUTDOWN_EVENT} event: {e}",
                exc_info=True,
                stack_info=True,
            )
        return

    def start(self) -> None:
        """启动调度器。"""
        if not self._initialize():
            return False

        for i in range(3):
            worker = Thread(
                target=self.run,
                daemon=True,
                name=f"{self.__class__.__name__}Worker-{i}",
            )
            worker.start()
            self._workers.add(worker)

        return True

    def wait(self) -> None:
        """等待所有工作线程结束。"""
        while not self._stop_mutex.is_set():
            time.sleep(1)

    def submit(self, event: Union[str, Event], *, trigger: Trigger = None) -> None:
        """提交事件到调度器。"""

        if self._stop_mutex.is_set():
            logging.warning(f"{self.__class__.__name__} scheduler is already stopped.")
            return

        if isinstance(event, str):
            event = Event(type=event)

        if event.type in RESERVED_EVENTS:
            logging.warning(f"Event type {event.type} is reserved.")
            return

        self._event_queue.put(event, trigger=trigger)

    def load_settings(
        self,
        config_file: Union[str, Path] = "config.json",
        is_load_params: bool = False,
    ) -> None:
        """加载配置,以及参数。

        Args:
            config_file (Union[str, Path], optional): 配置文件路径. Defaults to "config.json".
            is_load_params (bool, optional): 是否加载参数. Defaults to False.

        """
        self._config = Config.load(config_file)

        if is_load_params:
            params_pkl = Path(".") / ".vxsched" / "params.pkl"
            if params_pkl.exists():
                with open(params_pkl, "rb") as f:
                    self._params = pickle.load(f)
                    logging.info(f"Load params from {params_pkl.absolute()}")
            else:
                logging.warning(f"File {params_pkl.absolute()} not found")
                self._params = Params()


# Global instance
APP = Scheduler()

start = APP.start
wait = APP.wait
stop = APP.stop
register = APP.register
dispatch = APP.dispatch
unregister = APP.unregister


def load_modules(path: str) -> None:
    """从给定路径加载模块。"""
    for module in Path(path).glob("*.py"):
        if module.name.startswith("_"):
            continue
        logging.info(f"Loading module {module.name}")
        spec = importlib.util.spec_from_file_location(module.stem, module)
        if spec is None:
            logging.error(f"Error loading module {module.name}")
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


# ==========================================
# Part 4: CLI (from cli.py)
# ==========================================

DEFAULT_CONFIG = {
    "env": {
        "API_KEY": "123456",
    },
}

DEFAULT_HANDLER_FILE = """
import logging
from vxutils import loggerConfig
from vxsched import register, Event, Scheduler, INIT_EVENT, daily, every,APP

# 注册一个自定义事件处理器
@register("my_task")
def handle_my_task(app: Scheduler, event: Event):
    logging.info(f"Processing my_task: {event}")

# 在调度器启动时注册定时任务
@register(INIT_EVENT)
def on_init(app: Scheduler, event: Event):
    logging.info("Scheduler started!")
    
    # 每天 08:00 执行
    app.submit("my_task", trigger=daily("08:00:00"))
    
    # 每 10 秒执行一次
    app.submit(Event(type="my_task", data={"msg": "Hello"}), trigger=every(3))
    
if __name__ == "__main__":
    try:
        loggerConfig(level="INFO", filename="", force=True)
        APP.start()
        APP.submit(Event(type="test"))
        APP.wait()
    except KeyboardInterrupt:
        pass
    finally:
        APP.stop()


"""


def init_command(args: ArgumentParser, app: Optional[Scheduler] = APP) -> None:
    """初始化配置目录"""
    loggerConfig(level="INFO", filename="", force=True)

    target = Path(args.target)
    if not target.exists():
        target.mkdir(parents=True)
    logging.info(f"Initialize config directory {target}")

    for dir in ["log", "mods", "tmp"]:
        dir_path = target / dir
        if not dir_path.exists():
            dir_path.mkdir(parents=True)
        logging.info(f"Initialize directory {dir_path}")

    # Initialize config file
    config_file = target / "config.json"
    if not config_file.exists():
        with open(config_file, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        logging.info(f"Create config file {config_file}")

    if args.examples:
        handler_file = target / "mods" / "handlers.py"
        with open(handler_file, "w", encoding="utf-8") as f:
            f.write(DEFAULT_HANDLER_FILE)
        logging.info(f"Create example handler file {handler_file}")


def run_command(args: ArgumentParser, app: Optional[Scheduler] = APP) -> None:
    """运行调度器"""
    if args.verbose:
        loggerConfig(
            level="DEBUG", filename=args.log_file, force=True, async_logger=True
        )
    else:
        loggerConfig(level="INFO", filename="", force=True, async_logger=True)

    config_file = Path(args.config)
    if config_file.exists():
        app.load_settings(config_file, args.load_params)
        logging.info(f"Load config file {config_file}")

    try:
        load_modules(args.mods)
        app.start()
        logging.warning(f"Press Ctrl+C to stop the {app.__class__.__name__}.")
        app.wait()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()


def main():
    parser = ArgumentParser(description="vxsched 命令行工具")
    subparsers = parser.add_subparsers(title="command", dest="command")

    # Create init directory and example handler file
    init_parser = subparsers.add_parser("init", help="初始化配置目录")
    init_parser.add_argument(
        "-t", "--target", type=str, default=".", help="目标目录路径"
    )
    init_parser.add_argument(
        "-e", "--examples", action="store_true", help="创建示例处理器文件"
    )
    init_parser.set_defaults(func=init_command)

    # Create run subcommand
    run_parser = subparsers.add_parser("run", help="运行调度器")
    run_parser.add_argument(
        "-c", "--config", type=str, default="config.json", help="配置文件路径"
    )
    run_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="启用详细日志输出",
    )
    run_parser.add_argument("--log-file", type=str, default="", help="日志文件路径")
    run_parser.add_argument(
        "-m",
        "--mods",
        type=str,
        default="mods/",
        help="处理器模块路径",
    )
    run_parser.add_argument(
        "-p",
        "--load_params",
        help="加载参数 pickle 文件",
        action="store_true",
        default=False,
    )
    run_parser.set_defaults(func=run_command)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args, APP)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
