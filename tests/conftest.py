import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def homespace():
    """提供测试用的 homespace 路径"""
    return Path("E:\\src\\openbot\\.openbot")


@pytest.fixture
def botflow_instance(homespace):
    """提供 BotFlow 实例"""
    from openbot.gateway.botflow import BotFlow
    return BotFlow(homespace=homespace)
