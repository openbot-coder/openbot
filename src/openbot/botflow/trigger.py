"""BotFlow 触发器 - 基于 vxsched 设计"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Tuple
from pydantic import BaseModel, Field
from enum import Enum


class TriggerStatus(str, Enum):
    READY = "Ready"
    RUNNING = "Running"
    COMPLETED = "Completed"


class Trigger(BaseModel):
    """触发器基类"""
    trigger_dt: datetime = Field(default_factory=datetime.now)
    interval: float = Field(default=0.0)
    status: TriggerStatus = Field(default=TriggerStatus.READY)
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None

    @abstractmethod
    def next(self) -> Optional[datetime]:
        """获取下次触发时间"""
        pass

    def __lt__(self, other: "Trigger") -> bool:
        if isinstance(other, Trigger):
            return self.trigger_dt < other.trigger_dt
        return NotImplemented


class OnceTrigger(Trigger):
    """一次性触发器"""
    
    def next(self) -> Optional[datetime]:
        if self.status == TriggerStatus.COMPLETED:
            return None
        self.status = TriggerStatus.COMPLETED
        return self.trigger_dt


class IntervalTrigger(Trigger):
    """间隔触发器"""
    end_dt: Optional[datetime] = None
    
    def next(self) -> Optional[datetime]:
        if self.status == TriggerStatus.COMPLETED:
            return None
        
        next_dt = self.trigger_dt + timedelta(seconds=self.interval)
        
        # 检查是否超过结束时间（如果有）
        if self.end_dt and next_dt > self.end_dt:
            self.status = TriggerStatus.COMPLETED
            return None
        
        self.trigger_dt = next_dt
        return next_dt


class CronTrigger(Trigger):
    """Cron 触发器（简化版）"""
    cron_expression: str = "* * * * * *"
    
    def next(self) -> Optional[datetime]:
        # 简化实现：每秒触发
        if self.status == TriggerStatus.COMPLETED:
            return None
        next_dt = self.trigger_dt + timedelta(seconds=1)
        self.trigger_dt = next_dt
        return next_dt
