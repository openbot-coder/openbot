#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for file_search tool."""

import os
import re
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from openbot.agents.buildin_tools.file_search import (
    WORKING_DIR,
    _is_text_file,
    _relative_display,
    grep_search,
    glob_search,
    _BINARY_EXTENSIONS,
    _MAX_FILE_SIZE,
    _MAX_MATCHES,
)


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_is_text_file_text_extension(self, tmp_path):
        """Test text files with known extensions are recognized."""
        test_file = tmp_path / "test.py"
        test_file.touch()
        assert _is_text_file(test_file) is True
        
        test_file = tmp_path / "test.txt"
        test_file.touch()
        assert _is_text_file(test_file) is True
        
        test_file = tmp_path / "test.md"
        test_file.touch()
        assert _is_text_file(test_file) is True
        
        test_file = tmp_path / "test.json"
        test_file.touch()
        assert _is_text_file(test_file) is True
    
    def test_is_text_file_binary_extension(self, tmp_path):
        """Test binary files are correctly identified."""
        for ext in _BINARY_EXTENSIONS:
            test_file = tmp_path / f"test{ext}"
            test_file.touch()
            assert _is_text_file(test_file) is False
    
    def test_is_text_file_large_file(self, tmp_path):
        """Test files larger than _MAX_FILE_SIZE are considered binary."""
        test_file = tmp_path / "large.txt"
        # Create a file just over 2MB
        test_file.write_text("x" * (_MAX_FILE_SIZE + 1))
        assert _is_text_file(test_file) is False
        
        # Small file should be text
        small_file = tmp_path / "small.txt"
        small_file.write_text("x" * 100)
        assert _is_text_file(small_file) is True
    
    def test_is_text_file_nonexistent(self, tmp_path):
        """Test non-existent files return False."""
        test_file = tmp_path / "nonexistent.txt"
        assert _is_text_file(test_file) is False
    
    def test_relative_display_relative_path(self, tmp_path):
        """Test relative path display works correctly."""
        root = tmp_path / "project"
        root.mkdir()
        target = root / "src" / "module" / "file.py"
        target.parent.mkdir(parents=True)
        
        assert _relative_display(target, root) == "src/module/file.py"
    
    def test_relative_display_absolute_path(self, tmp_path):
        """Test absolute path is returned when target is outside root."""
        root = tmp_path / "project"
        root.mkdir()
        target = tmp_path / "outside" / "file.py"
        target.parent.mkdir()
        
        assert _relative_display(target, root) == str(target)


class TestGrepSearch:
    """Test grep_search function."""
    
    @pytest.mark.asyncio
    async def test_grep_empty_pattern(self):
        """Test grep with empty pattern returns error."""
        response = await grep_search("")
        assert response.content[0]["type"] == "text"
        assert "错误：未提供搜索 `pattern`" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_grep_nonexistent_path(self):
        """Test grep on non-existent path returns error."""
        response = await grep_search("test", "/nonexistent/path")
        assert response.content[0]["type"] == "text"
        assert "错误：路径" in response.content[0]["text"]
        assert "不存在" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_grep_invalid_regex(self):
        """Test grep with invalid regex returns error."""
        response = await grep_search("[invalid regex", is_regex=True)
        assert response.content[0]["type"] == "text"
        assert "错误：无效正则表达式" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_grep_single_file_exact_match(self, tmp_path):
        """Test grep search in single file with exact match."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1: hello world\nline2: test content\nline3: hello again")
        
        response = await grep_search("hello", str(test_file))
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        assert "test.txt:1:> line1: hello world" in result
        assert "test.txt:3:> line3: hello again" in result
        assert "line2" not in result
    
    @pytest.mark.asyncio
    async def test_grep_single_file_case_insensitive(self, tmp_path):
        """Test grep case-insensitive search."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World\nhello world\nHELLO WORLD")
        
        response = await grep_search("hello", str(test_file), case_sensitive=False)
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        assert "test.txt:1:> Hello World" in result
        assert "test.txt:2:> hello world" in result
        assert "test.txt:3:> HELLO WORLD" in result
    
    @pytest.mark.asyncio
    async def test_grep_regex_match(self, tmp_path):
        """Test grep with regex pattern."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("123 abc\n456 def\n789 ghi")
        
        response = await grep_search(r"\d+", str(test_file), is_regex=True)
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        assert "test.txt:1:> 123 abc" in result
        assert "test.txt:2:> 456 def" in result
        assert "test.txt:3:> 789 ghi" in result
    
    @pytest.mark.asyncio
    async def test_grep_with_context_lines(self, tmp_path):
        """Test grep with context lines."""
        test_file = tmp_path / "test.txt"
        lines = [f"line{i}" for i in range(1, 11)]
        test_file.write_text("\n".join(lines))
        
        response = await grep_search("line5", str(test_file), context_lines=2)
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        
        # Should show lines 3-7 with line5 highlighted
        assert "test.txt:3:  line3" in result
        assert "test.txt:4:  line4" in result
        assert "test.txt:5:> line5" in result
        assert "test.txt:6:  line6" in result
        assert "test.txt:7:  line7" in result
        assert "---" in result  # Separator after context
    
    @pytest.mark.asyncio
    async def test_grep_directory_recursive(self, tmp_path):
        """Test grep searches recursively in directory."""
        # Create directory structure
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir2").mkdir()
        
        file1 = tmp_path / "file1.txt"
        file1.write_text("test content in root")
        
        file2 = tmp_path / "dir1" / "file2.txt"
        file2.write_text("test content in dir1")
        
        file3 = tmp_path / "dir2" / "file3.py"
        file3.write_text("test content in dir2")
        
        # Binary file should be skipped
        binary_file = tmp_path / "image.png"
        binary_file.write_text("binary content with test")
        
        response = await grep_search("test", str(tmp_path))
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        
        assert "file1.txt:1:> test content in root" in result
        assert "dir1/file2.txt:1:> test content in dir1" in result
        assert "dir2/file3.py:1:> test content in dir2" in result
        assert "image.png" not in result  # Binary file skipped
    
    @pytest.mark.asyncio
    async def test_grep_no_matches(self, tmp_path):
        """Test grep returns appropriate message when no matches."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content without the pattern")
        
        response = await grep_search("nonexistent", str(test_file))
        assert response.content[0]["type"] == "text"
        assert "未找到匹配模式的结果：nonexistent" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_grep_result_truncation(self, tmp_path):
        """Test grep results are truncated when exceeding _MAX_MATCHES."""
        test_file = tmp_path / "test.txt"
        # Create _MAX_MATCHES + 10 lines all matching
        content = "\n".join([f"test line {i}" for i in range(_MAX_MATCHES + 10)])
        test_file.write_text(content)
        
        response = await grep_search("test", str(test_file))
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        
        assert "（结果已截断，最多显示 200 条匹配。）" in result
        # Count matches - should be _MAX_MATCHES (each match is one line)
        matches = [line for line in result.split("\n") if ":>" in line]
        assert len(matches) == _MAX_MATCHES
    
    @pytest.mark.asyncio
    async def test_grep_skip_unreadable_files(self, tmp_path):
        """Test grep skips unreadable files gracefully."""
        readable_file = tmp_path / "readable.txt"
        readable_file.write_text("test content")
        
        unreadable_file = tmp_path / "unreadable.txt"
        unreadable_file.write_text("test content")
        unreadable_file.chmod(0o000)
        
        try:
            response = await grep_search("test", str(tmp_path))
            assert response.content[0]["type"] == "text"
            result = response.content[0]["text"]
            assert "readable.txt:1:> test content" in result
            # Should not have error, just skip unreadable file
        finally:
            unreadable_file.chmod(0o644)

    @pytest.mark.asyncio
    async def test_grep_truncated_early_break(self, tmp_path):
        """Test grep breaks early when truncated flag is set from previous file."""
        # Create multiple files with many matches
        file1 = tmp_path / "file1.txt"
        # Each match with context_lines=0 adds 1 line, so _MAX_MATCHES matches will fill the limit
        file1.write_text("\n".join([f"test line {i}" for i in range(_MAX_MATCHES)]))
        
        file2 = tmp_path / "file2.txt"
        file2.write_text("test in file2")  # This should not be processed
        
        response = await grep_search("test", str(tmp_path))
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        
        assert "（结果已截断，最多显示 200 条匹配。）" in result
        assert "file2.txt" not in result  # file2 should not be processed


class TestGlobSearch:
    """Test glob_search function."""
    
    @pytest.mark.asyncio
    async def test_glob_empty_pattern(self):
        """Test glob with empty pattern returns error."""
        response = await glob_search("")
        assert response.content[0]["type"] == "text"
        assert "错误：未提供 glob `pattern`" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_glob_nonexistent_path(self):
        """Test glob on non-existent path returns error."""
        response = await glob_search("*.py", "/nonexistent/path")
        assert response.content[0]["type"] == "text"
        assert "错误：路径" in response.content[0]["text"]
        assert "不存在" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_glob_path_is_file(self, tmp_path):
        """Test glob with file path instead of directory returns error."""
        test_file = tmp_path / "test.txt"
        test_file.touch()
        
        response = await glob_search("*.py", str(test_file))
        assert response.content[0]["type"] == "text"
        assert "错误：路径" in response.content[0]["text"]
        assert "不是目录" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_glob_simple_pattern(self, tmp_path):
        """Test glob with simple pattern matching files."""
        # Create test files
        (tmp_path / "file1.py").touch()
        (tmp_path / "file2.py").touch()
        (tmp_path / "file3.txt").touch()
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file4.py").touch()
        
        response = await glob_search("*.py", str(tmp_path))
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        
        files = result.strip().split("\n")
        assert "file1.py" in files
        assert "file2.py" in files
        assert "file3.txt" not in files
        assert "subdir/file4.py" not in files  # Simple * doesn't recurse
    
    @pytest.mark.asyncio
    async def test_glob_recursive_pattern(self, tmp_path):
        """Test glob with recursive ** pattern."""
        # Create test files
        (tmp_path / "file1.py").touch()
        (tmp_path / "subdir1").mkdir()
        (tmp_path / "subdir1" / "file2.py").touch()
        (tmp_path / "subdir1" / "subdir2").mkdir()
        (tmp_path / "subdir1" / "subdir2" / "file3.py").touch()
        (tmp_path / "other.txt").touch()
        
        response = await glob_search("**/*.py", str(tmp_path))
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        
        files = result.strip().split("\n")
        assert "file1.py" in files
        assert "subdir1/file2.py" in files
        assert "subdir1/subdir2/file3.py" in files
        assert "other.txt" not in files
    
    @pytest.mark.asyncio
    async def test_glob_include_directories(self, tmp_path):
        """Test glob includes directories with trailing slash."""
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir2").mkdir()
        (tmp_path / "file1.txt").touch()
        
        response = await glob_search("*", str(tmp_path))
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        
        entries = result.strip().split("\n")
        assert "dir1/" in entries
        assert "dir2/" in entries
        assert "file1.txt" in entries
    
    @pytest.mark.asyncio
    async def test_glob_no_matches(self, tmp_path):
        """Test glob returns appropriate message when no matches."""
        response = await glob_search("*.nonexistent", str(tmp_path))
        assert response.content[0]["type"] == "text"
        assert "没有文件匹配该模式：*.nonexistent" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_glob_result_truncation(self, tmp_path):
        """Test glob results are truncated when exceeding _MAX_MATCHES."""
        # Create _MAX_MATCHES + 10 files
        for i in range(_MAX_MATCHES + 10):
            (tmp_path / f"file_{i:03d}.txt").touch()
        
        response = await glob_search("*.txt", str(tmp_path))
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        
        assert "（结果已截断，最多显示 200 条记录。）" in result
        files = [line for line in result.split("\n") if line.endswith(".txt")]
        assert len(files) == _MAX_MATCHES
    
    @pytest.mark.asyncio
    async def test_glob_pattern_with_special_chars(self, tmp_path):
        """Test glob handles patterns with special characters."""
        (tmp_path / "test_file1.txt").touch()
        (tmp_path / "test_file2.txt").touch()
        (tmp_path / "other_file.txt").touch()
        
        response = await glob_search("test_*.txt", str(tmp_path))
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        
        files = result.strip().split("\n")
        assert "test_file1.txt" in files
        assert "test_file2.txt" in files
        assert "other_file.txt" not in files
    
    @pytest.mark.asyncio
    async def test_glob_error_handling(self, tmp_path):
        """Test glob handles exceptions gracefully."""
        with patch('pathlib.Path.glob') as mock_glob:
            mock_glob.side_effect = Exception("Test error")
            
            response = await glob_search("*.py", str(tmp_path))
            assert response.content[0]["type"] == "text"
            assert "错误：Glob 搜索失败" in response.content[0]["text"]
            assert "Test error" in response.content[0]["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
