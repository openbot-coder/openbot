#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for get_current_time tool."""

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from openbot.agents.buildin_tools.get_current_time import get_current_time


class TestGetCurrentTime:
    """Test get_current_time tool function."""
    
    @pytest.mark.asyncio
    async def test_normal_execution(self):
        """Test normal execution returns valid time string."""
        response = await get_current_time()
        
        # Check response structure
        assert hasattr(response, "content")
        assert len(response.content) == 1
        assert response.content[0]["type"] == "text"
        assert isinstance(response.content[0]["text"], str)
        assert len(response.content[0]["text"]) > 0
    
    @pytest.mark.asyncio
    async def test_time_format(self):
        """Test returned time format is correct."""
        # Mock a specific time for predictable testing
        test_time = datetime(2026, 2, 13, 19, 30, 45, tzinfo=timezone.utc)
        
        with patch("openbot.agents.buildin_tools.get_current_time.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.astimezone.return_value = test_time
            mock_datetime.now.return_value = mock_now
            mock_datetime.strftime = datetime.strftime
            mock_datetime.now.side_effect = None  # Reset side effect
            
            response = await get_current_time()
            
            # UTC time should format as "2026-02-13 19:30:45 UTC (UTC+0000)"
            time_str = response.content[0]["text"]
            assert "2026-02-13" in time_str
            assert "19:30:45" in time_str
            assert "UTC" in time_str
            assert "+0000" in time_str
    
    @pytest.mark.asyncio
    async def test_astimezone_exception_fallback(self):
        """Test fallback to UTC when astimezone raises exception."""
        with patch("openbot.agents.buildin_tools.get_current_time.datetime") as mock_datetime:
            # First call: now().astimezone() raises exception
            mock_now1 = MagicMock()
            mock_now1.astimezone.side_effect = Exception("Timezone error")
            
            # Second call: datetime.now(timezone.utc) returns test time
            test_time = datetime(2026, 2, 13, 19, 30, 45, tzinfo=timezone.utc)
            
            mock_datetime.now.side_effect = [mock_now1, test_time]
            
            response = await get_current_time()
            
            # Should fallback to ISO format UTC time
            time_str = response.content[0]["text"]
            assert "2026-02-13T19:30:45" in time_str
            assert "(UTC)" in time_str
    
    @pytest.mark.asyncio
    async def test_different_timezones(self):
        """Test with different timezone offsets."""
        # Test with UTC+8 timezone
        tz_utc_8 = timezone(timedelta(hours=8), name="CST")
        test_time = datetime(2026, 2, 13, 19, 30, 45, tzinfo=tz_utc_8)
        
        with patch("openbot.agents.buildin_tools.get_current_time.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.astimezone.return_value = test_time
            mock_datetime.now.return_value = mock_now
            mock_datetime.strftime = datetime.strftime
            mock_datetime.now.side_effect = None
            
            response = await get_current_time()
            
            time_str = response.content[0]["text"]
            assert "2026-02-13 19:30:45 CST (UTC+0800)" in time_str
    
    @pytest.mark.asyncio
    async def test_response_type(self):
        """Test response is correct ToolResponse type."""
        from agentscope.tool import ToolResponse
        response = await get_current_time()
        assert isinstance(response, ToolResponse)
    
    @pytest.mark.asyncio
    async def test_text_block_content(self):
        """Test response contains valid TextBlock dict."""
        response = await get_current_time()
        assert isinstance(response.content[0], dict)
        assert "type" in response.content[0]
        assert "text" in response.content[0]
        assert isinstance(response.content[0]["text"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
