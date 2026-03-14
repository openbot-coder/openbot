#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for file_io tool."""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from openbot.agents.buildin_tools.file_io import (
    WORKING_DIR,
    _resolve_file_path,
    read_file,
    write_file,
    edit_file,
    append_file,
    remove_file,
)


class TestFilePathResolution:
    """Test file path resolution functionality."""
    
    def test_absolute_path_resolution(self):
        """Test absolute paths are returned unchanged."""
        abs_path = "/tmp/test/file.txt"
        assert _resolve_file_path(abs_path) == abs_path
    
    def test_relative_path_resolution(self, monkeypatch):
        """Test relative paths are resolved against WORKING_DIR."""
        test_working_dir = "/test/working/dir"
        monkeypatch.setenv("OPENBOT_WORKING_DIR", test_working_dir)
        
        # Test directly with the function (WORKING_DIR is already resolved at module level)
        # We'll test the actual functionality by passing paths directly
        assert _resolve_file_path("relative/path.txt") == str(WORKING_DIR / "relative/path.txt")
        assert _resolve_file_path("./file.txt") == str(WORKING_DIR / "file.txt")
        assert _resolve_file_path("../parent.txt") == str(WORKING_DIR / "../parent.txt")
    
    def test_home_path_resolution(self):
        """Test paths starting with ~ are resolved correctly."""
        home_dir = os.path.expanduser("~")
        resolved = _resolve_file_path("~/test.txt")
        assert str(Path(resolved).expanduser()) == str(Path(f"{home_dir}/test.txt").expanduser())


class TestReadFile:
    """Test read_file function."""
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """Test reading a file that doesn't exist returns error."""
        response = await read_file("/nonexistent/path/file.txt")
        assert response.content[0]["type"] == "text"
        assert "错误: 文件" in response.content[0]["text"]
        assert "不存在" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_read_directory_instead_of_file(self, tmp_path):
        """Test reading a directory returns error."""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()
        
        response = await read_file(str(dir_path))
        assert response.content[0]["type"] == "text"
        assert "错误: 路径" in response.content[0]["text"]
        assert "不是一个文件" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_read_entire_file(self, tmp_path):
        """Test reading entire file content."""
        test_file = tmp_path / "test.txt"
        content = "line1\nline2\nline3\nline4\nline5"
        with open(test_file, "w") as f:
            f.write(content)
        
        response = await read_file(str(test_file))
        assert response.content[0]["type"] == "text"
        assert response.content[0]["text"] == content
    
    @pytest.mark.asyncio
    async def test_read_specific_line_range(self, tmp_path):
        """Test reading specific line range."""
        test_file = tmp_path / "test.txt"
        lines = [f"line{i}\n" for i in range(1, 11)]  # 10 lines
        with open(test_file, "w") as f:
            f.writelines(lines)
        
        # Read lines 3-7
        response = await read_file(str(test_file), start_line=3, end_line=7)
        assert response.content[0]["type"] == "text"
        content = response.content[0]["text"]
        assert f"{str(test_file)}  (行 3-7 共 10 行)" in content
        assert "line3" in content
        assert "line7" in content
        assert "line1" not in content
        assert "line10" not in content
    
    @pytest.mark.asyncio
    async def test_read_start_line_only(self, tmp_path):
        """Test reading from start_line to end of file."""
        test_file = tmp_path / "test.txt"
        lines = [f"line{i}\n" for i in range(1, 6)]
        with open(test_file, "w") as f:
            f.writelines(lines)
        
        # Read from line 3 onwards
        response = await read_file(str(test_file), start_line=3)
        assert response.content[0]["type"] == "text"
        content = response.content[0]["text"]
        assert f"{str(test_file)}  (行 3-5 共 5 行)" in content
        assert "line3" in content
        assert "line5" in content
        assert "line1" not in content
    
    @pytest.mark.asyncio
    async def test_read_end_line_only(self, tmp_path):
        """Test reading from start to end_line."""
        test_file = tmp_path / "test.txt"
        lines = [f"line{i}\n" for i in range(1, 6)]
        with open(test_file, "w") as f:
            f.writelines(lines)
        
        # Read up to line 3
        response = await read_file(str(test_file), end_line=3)
        assert response.content[0]["type"] == "text"
        content = response.content[0]["text"]
        assert f"{str(test_file)}  (行 1-3 共 5 行)" in content
        assert "line1" in content
        assert "line3" in content
        assert "line5" not in content
    
    @pytest.mark.asyncio
    async def test_start_line_exceeds_file_length(self, tmp_path):
        """Test start_line is larger than total lines returns error."""
        test_file = tmp_path / "test.txt"
        lines = [f"line{i}\n" for i in range(1, 6)]  # 5 lines
        with open(test_file, "w") as f:
            f.writelines(lines)
        
        response = await read_file(str(test_file), start_line=10)
        assert response.content[0]["type"] == "text"
        assert "错误: start_line 10 超过了文件长度" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_start_line_greater_than_end_line(self, tmp_path):
        """Test start_line > end_line returns error."""
        test_file = tmp_path / "test.txt"
        lines = [f"line{i}\n" for i in range(1, 6)]
        with open(test_file, "w") as f:
            f.writelines(lines)
        
        response = await read_file(str(test_file), start_line=5, end_line=2)
        assert response.content[0]["type"] == "text"
        assert "错误: start_line (5) 大于 end_line (2)" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_read_empty_file(self, tmp_path):
        """Test reading empty file returns empty content."""
        test_file = tmp_path / "empty.txt"
        test_file.touch()
        
        response = await read_file(str(test_file))
        assert response.content[0]["type"] == "text"
        assert response.content[0]["text"] == ""
    
    @pytest.mark.asyncio
    async def test_read_file_permission_error(self, tmp_path):
        """Test permission error when reading file returns error."""
        test_file = tmp_path / "no_perm.txt"
        with open(test_file, "w") as f:
            f.write("content")
        test_file.chmod(0o000)  # Remove all permissions
        
        try:
            response = await read_file(str(test_file))
            assert response.content[0]["type"] == "text"
            assert "错误: 读取文件失败" in response.content[0]["text"]
        finally:
            test_file.chmod(0o644)  # Restore permissions for cleanup


class TestWriteFile:
    """Test write_file function."""
    
    @pytest.mark.asyncio
    async def test_write_new_file(self, tmp_path):
        """Test writing content to a new file."""
        test_file = tmp_path / "new_file.txt"
        content = "Hello, World!\nThis is a test file."
        
        response = await write_file(str(test_file), content)
        assert response.content[0]["type"] == "text"
        assert "写入了" in response.content[0]["text"]
        assert str(test_file) in response.content[0]["text"]
        
        # Verify file content
        with open(test_file, "r") as f:
            assert f.read() == content
    
    @pytest.mark.asyncio
    async def test_overwrite_existing_file(self, tmp_path):
        """Test overwriting an existing file."""
        test_file = tmp_path / "existing.txt"
        with open(test_file, "w") as f:
            f.write("old content")
        
        new_content = "new content"
        response = await write_file(str(test_file), new_content)
        assert "写入了" in response.content[0]["text"]
        
        with open(test_file, "r") as f:
            assert f.read() == new_content
    
    @pytest.mark.asyncio
    async def test_write_empty_content(self, tmp_path):
        """Test writing empty content creates empty file."""
        test_file = tmp_path / "empty.txt"
        response = await write_file(str(test_file), "")
        assert "写入了 0 字节" in response.content[0]["text"]
        
        with open(test_file, "r") as f:
            assert f.read() == ""
    
    @pytest.mark.asyncio
    async def test_write_file_with_empty_path(self):
        """Test writing with empty file_path returns error."""
        response = await write_file("", "content")
        assert response.content[0]["type"] == "text"
        assert "错误: 未提供 `file_path`" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_write_file_permission_error(self, tmp_path):
        """Test permission error when writing returns error."""
        test_file = tmp_path / "protected.txt"
        test_file.touch()
        test_file.chmod(0o444)  # Read-only
        
        try:
            response = await write_file(str(test_file), "content")
            assert response.content[0]["type"] == "text"
            assert "错误: 写入文件失败" in response.content[0]["text"]
        finally:
            test_file.chmod(0o644)
    
    @pytest.mark.asyncio
    async def test_write_to_directory_path(self, tmp_path):
        """Test writing to a directory path returns error."""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()
        
        response = await write_file(str(dir_path), "content")
        assert "错误: 写入文件失败" in response.content[0]["text"]


class TestEditFile:
    """Test edit_file function."""
    
    @pytest.mark.asyncio
    async def test_edit_existing_text(self, tmp_path):
        """Test replacing existing text in file."""
        test_file = tmp_path / "edit_test.txt"
        original_content = "Hello, World!\nThis is a test.\nHello again!"
        with open(test_file, "w") as f:
            f.write(original_content)
        
        response = await edit_file(str(test_file), "Hello", "Hi")
        assert response.content[0]["type"] == "text"
        assert "成功替换了" in response.content[0]["text"]
        
        # Verify all occurrences are replaced
        with open(test_file, "r") as f:
            new_content = f.read()
        assert new_content == "Hi, World!\nThis is a test.\nHi again!"
    
    @pytest.mark.asyncio
    async def test_edit_nonexistent_file(self):
        """Test editing non-existent file returns error."""
        response = await edit_file("/nonexistent/file.txt", "old", "new")
        assert response.content[0]["type"] == "text"
        assert "错误: 文件" in response.content[0]["text"]
        assert "不存在" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_edit_text_not_found(self, tmp_path):
        """Test when old_text not found in file returns error."""
        test_file = tmp_path / "edit_test.txt"
        with open(test_file, "w") as f:
            f.write("Hello, World!")
        
        response = await edit_file(str(test_file), "NonExistent", "Replacement")
        assert response.content[0]["type"] == "text"
        assert "错误: 在" in response.content[0]["text"]
        assert "中未找到要替换的文本" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_edit_with_multiline_text(self, tmp_path):
        """Test replacing multi-line text."""
        test_file = tmp_path / "multiline.txt"
        original_content = "line1\nline2\nline3\nline4"
        with open(test_file, "w") as f:
            f.write(original_content)
        
        old_text = "line2\nline3"
        new_text = "new_line2\nnew_line3"
        response = await edit_file(str(test_file), old_text, new_text)
        assert "成功替换了" in response.content[0]["text"]
        
        with open(test_file, "r") as f:
            assert f.read() == "line1\nnew_line2\nnew_line3\nline4"
    
    @pytest.mark.asyncio
    async def test_edit_empty_old_text(self, tmp_path):
        """Test replacing empty old_text works correctly (empty string matches everywhere)."""
        test_file = tmp_path / "empty_old.txt"
        original_content = "test content"
        with open(test_file, "w") as f:
            f.write(original_content)
        
        response = await edit_file(str(test_file), "", "X")
        assert "成功替换了" in response.content[0]["text"]
        
        # Verify content - empty string replacement adds X between every character
        with open(test_file, "r") as f:
            new_content = f.read()
        assert new_content == "XtXeXsXtX XcXoXnXtXeXnXtX"
    
    @pytest.mark.asyncio
    @patch('openbot.agents.buildin_tools.file_io.read_file')
    async def test_edit_read_file_returns_empty_content(self, mock_read_file, tmp_path):
        """Test edit_file handles case where read_file returns empty content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        # Mock read_file to return empty content
        mock_response = MagicMock()
        mock_response.content = []
        mock_read_file.return_value = mock_response
        
        response = await edit_file(str(test_file), "old", "new")
        assert "错误: 读取文件" in response.content[0]["text"]
        assert "失败" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    @patch('openbot.agents.buildin_tools.file_io.write_file')
    async def test_edit_write_file_returns_error(self, mock_write_file, tmp_path):
        """Test edit_file propagates write_file errors correctly."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")
        
        # Mock write_file to return error
        mock_response = MagicMock()
        mock_response.content = [{"type": "text", "text": "错误: 写入文件失败"}]
        mock_write_file.return_value = mock_response
        
        response = await edit_file(str(test_file), "old", "new")
        assert "错误: 写入文件失败" in response.content[0]["text"]


class TestAppendFile:
    """Test append_file function."""
    
    @pytest.mark.asyncio
    async def test_append_to_existing_file(self, tmp_path):
        """Test appending content to existing file."""
        test_file = tmp_path / "append.txt"
        with open(test_file, "w") as f:
            f.write("original content\n")
        
        append_content = "appended content"
        response = await append_file(str(test_file), append_content)
        assert response.content[0]["type"] == "text"
        assert "追加了" in response.content[0]["text"]
        
        with open(test_file, "r") as f:
            assert f.read() == "original content\nappended content"
    
    @pytest.mark.asyncio
    async def test_append_to_new_file(self, tmp_path):
        """Test appending to non-existent file creates it."""
        test_file = tmp_path / "new_append.txt"
        assert not test_file.exists()
        
        content = "new file content"
        response = await append_file(str(test_file), content)
        assert "追加了" in response.content[0]["text"]
        assert test_file.exists()
        
        with open(test_file, "r") as f:
            assert f.read() == content
    
    @pytest.mark.asyncio
    async def test_append_empty_content(self, tmp_path):
        """Test appending empty content."""
        test_file = tmp_path / "append_empty.txt"
        with open(test_file, "w") as f:
            f.write("original")
        
        response = await append_file(str(test_file), "")
        assert "追加了 0 字节" in response.content[0]["text"]
        
        with open(test_file, "r") as f:
            assert f.read() == "original"
    
    @pytest.mark.asyncio
    async def test_append_with_empty_path(self):
        """Test appending with empty file_path returns error."""
        response = await append_file("", "content")
        assert "错误: 未提供 `file_path`" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_append_permission_error(self, tmp_path):
        """Test permission error when appending returns error."""
        test_file = tmp_path / "readonly.txt"
        with open(test_file, "w") as f:
            f.write("original")
        test_file.chmod(0o444)
        
        try:
            response = await append_file(str(test_file), "append")
            assert "错误: 追加文件失败" in response.content[0]["text"]
        finally:
            test_file.chmod(0o644)


class TestRemoveFile:
    """Test remove_file function."""
    
    @pytest.mark.asyncio
    async def test_remove_existing_file(self, tmp_path, monkeypatch):
        """Test removing existing file moves it to trash."""
        # Set WORKING_DIR to tmp_path
        monkeypatch.setenv("OPENBOT_WORKING_DIR", str(tmp_path))
        import importlib
        from openbot.agents.buildin_tools import file_io
        importlib.reload(file_io)
        
        # Create test file
        test_file = tmp_path / "to_remove.txt"
        with open(test_file, "w") as f:
            f.write("content")
        
        # Create trash dir
        trash_dir = tmp_path / ".trash"
        trash_dir.mkdir()
        
        response = await file_io.remove_file("to_remove.txt")
        assert response.content[0]["type"] == "text"
        assert "已将" in response.content[0]["text"]
        assert "移动到回收站" in response.content[0]["text"]
        
        # Verify file is moved
        assert not test_file.exists()
        assert len(list(trash_dir.glob("to_remove.txt.*"))) == 1
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_file(self):
        """Test removing non-existent file returns error."""
        response = await remove_file("/nonexistent/file.txt")
        assert "错误: 文件" in response.content[0]["text"]
        assert "不存在" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_remove_directory(self, tmp_path):
        """Test removing a directory returns error."""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()
        
        response = await remove_file(str(dir_path))
        assert "错误: 路径" in response.content[0]["text"]
        assert "不是一个文件" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_remove_with_empty_path(self):
        """Test removing with empty file_path returns error."""
        response = await remove_file("")
        assert "错误: 未提供 `file_path`" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_trash_dir_created_automatically(self, tmp_path, monkeypatch):
        """Test .trash directory is created if it doesn't exist."""
        monkeypatch.setenv("OPENBOT_WORKING_DIR", str(tmp_path))
        import importlib
        from openbot.agents.buildin_tools import file_io
        importlib.reload(file_io)
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        trash_dir = tmp_path / ".trash"
        assert not trash_dir.exists()
        
        await file_io.remove_file("test.txt")
        assert trash_dir.exists()
        assert trash_dir.is_dir()
    
    @pytest.mark.asyncio
    async def test_remove_permission_error(self, tmp_path, monkeypatch):
        """Test permission error when moving to trash returns error."""
        monkeypatch.setenv("OPENBOT_WORKING_DIR", str(tmp_path))
        import importlib
        from openbot.agents.buildin_tools import file_io
        importlib.reload(file_io)
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        # Make trash dir read-only
        trash_dir = tmp_path / ".trash"
        trash_dir.mkdir()
        trash_dir.chmod(0o555)  # Read-only
        
        try:
            response = await file_io.remove_file("test.txt")
            assert "错误: 移除文件失败" in response.content[0]["text"]
            assert test_file.exists()  # File should still exist
        finally:
            trash_dir.chmod(0o755)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
