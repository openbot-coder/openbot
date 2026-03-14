#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for memory_search tool."""

from unittest.mock import MagicMock, patch
import pytest
from openbot.agents.buildin_tools.memory_search import create_memory_search_tool


class TestMemorySearch:
    """Test memory_search tool function."""
    
    @pytest.mark.asyncio
    async def test_memory_search_with_none_manager(self):
        """Test memory_search when memory_manager is None."""
        memory_search = create_memory_search_tool(None)
        
        response = await memory_search("test query")
        assert response.content[0]["type"] == "text"
        assert "错误：记忆管理器未启用。" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_memory_search_success(self):
        """Test successful memory search."""
        # Create mock memory manager with async method
        mock_manager = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [{
            "type": "text",
            "text": "Memory search results:\n- file1.md:10: test content"
        }]
        
        # Make memory_search an async function
        async def mock_search(query, max_results, min_score):
            return mock_response
        
        mock_manager.memory_search = mock_search
        
        memory_search = create_memory_search_tool(mock_manager)
        
        response = await memory_search("test query", max_results=10, min_score=0.5)
        assert response.content[0]["type"] == "text"
        assert "Memory search results:" in response.content[0]["text"]
        assert "file1.md:10: test content" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_memory_search_default_parameters(self):
        """Test memory_search uses default parameters correctly."""
        call_args = None
        
        async def mock_search(query, max_results, min_score):
            nonlocal call_args
            call_args = (query, max_results, min_score)
            mock_response = MagicMock()
            mock_response.content = [{"type": "text", "text": "results"}]
            return mock_response
        
        mock_manager = MagicMock()
        mock_manager.memory_search = mock_search
        
        memory_search = create_memory_search_tool(mock_manager)
        
        await memory_search("test query")
        
        # Verify default parameters are used
        assert call_args == ("test query", 5, 0.1)
    
    @pytest.mark.asyncio
    async def test_memory_search_exception_handling(self):
        """Test memory_search handles exceptions gracefully."""
        async def mock_search(query, max_results, min_score):
            raise Exception("Test search error")
        
        mock_manager = MagicMock()
        mock_manager.memory_search = mock_search
        
        memory_search = create_memory_search_tool(mock_manager)
        
        response = await memory_search("test query")
        assert response.content[0]["type"] == "text"
        assert "错误：记忆搜索失败" in response.content[0]["text"]
        assert "Test search error" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_memory_search_empty_query(self):
        """Test memory_search with empty query."""
        call_args = None
        
        async def mock_search(query, max_results, min_score):
            nonlocal call_args
            call_args = (query, max_results, min_score)
            mock_response = MagicMock()
            mock_response.content = [{"type": "text", "text": "empty query results"}]
            return mock_response
        
        mock_manager = MagicMock()
        mock_manager.memory_search = mock_search
        
        memory_search = create_memory_search_tool(mock_manager)
        
        response = await memory_search("")
        assert response.content[0]["type"] == "text"
        # The actual validation is expected to be done by memory_manager
        assert call_args == ("", 5, 0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
