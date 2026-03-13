import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient
from openbot.gateway.botflow import BotFlow


class TestBotFlowAPI:
    """测试 BotFlow API 端点"""

    def test_health_endpoint(self):
        """测试健康检查端点"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))
        client = TestClient(bot_flow.app)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_webui_endpoint(self):
        """测试 Web UI 端点"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))
        client = TestClient(bot_flow.app)

        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "OpenBot Gateway" in response.text

    def test_webui_robots_endpoint(self):
        """测试 /webui 端点"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))
        client = TestClient(bot_flow.app)

        response = client.get("/webui")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestBotFlowEndpoints:
    """测试 BotFlow REST API 端点"""

    @pytest.mark.asyncio
    async def test_process_endpoint_no_message(self):
        """测试 process 端点 - 无消息"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))
        await bot_flow.initialize()

        client = TestClient(bot_flow.app)
        response = client.post("/process", json={})
        assert response.status_code == 200
        data = response.json()
        assert "error" in data or "status" in data


class TestWebSocketEndpoint:
    """测试 WebSocket 端点"""

    def test_websocket_route_exists(self):
        """测试 WebSocket 路由是否存在"""
        bot_flow = BotFlow(homespace=Path("E:\\src\\openbot\\.openbot"))

        ws_routes = []
        for route in bot_flow.app.routes:
            if hasattr(route, 'path') and 'ws' in route.path.lower():
                ws_routes.append(route.path)

        assert "/ws/{client_id}" in ws_routes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
