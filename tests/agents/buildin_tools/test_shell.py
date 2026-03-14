#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for shell tool."""

import asyncio
import locale
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from openbot.agents.buildin_tools.shell import (
    WORKING_DIR,
    execute_shell_command,
    execute_python_code,
)


class TestExecuteShellCommand:
    """Test execute_shell_command function."""
    
    @pytest.mark.asyncio
    async def test_shell_command_success(self, tmp_path):
        """Test successful shell command execution."""
        response = await execute_shell_command("echo 'hello world'", cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert response.content[0]["text"] == "hello world"
    
    @pytest.mark.asyncio
    async def test_shell_command_success_no_output(self, tmp_path):
        """Test successful command with no output."""
        # Create a directory (no output)
        test_dir = tmp_path / "test_dir"
        assert not test_dir.exists()
        
        response = await execute_shell_command(f"mkdir {test_dir}", cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert "命令执行成功（无输出）" in response.content[0]["text"]
        assert test_dir.exists()
    
    @pytest.mark.asyncio
    async def test_shell_command_failure(self, tmp_path):
        """Test failed shell command execution."""
        response = await execute_shell_command("command_that_does_not_exist", cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        assert "命令失败，退出码" in result
        assert "[标准错误]" in result
        assert "command_that_does_not_exist" in result
    
    @pytest.mark.asyncio
    async def test_shell_command_with_cwd(self, tmp_path):
        """Test shell command executes in specified working directory."""
        # Create a file in tmp_path
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        # Run ls in tmp_path
        response = await execute_shell_command("ls", cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert "test.txt" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_shell_command_default_cwd(self):
        """Test shell command uses default WORKING_DIR when cwd not specified."""
        response = await execute_shell_command("pwd")
        assert response.content[0]["type"] == "text"
        assert str(WORKING_DIR) in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_shell_command_empty_command(self, tmp_path):
        """Test empty shell command."""
        response = await execute_shell_command("", cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        # Empty command should execute successfully with no output
        assert "命令执行成功（无输出）" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_shell_command_timeout(self, tmp_path):
        """Test shell command timeout handling."""
        # Run a command that sleeps longer than timeout
        response = await execute_shell_command("sleep 2", timeout=1, cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        assert "命令失败，退出码 -1" in result
        assert "超时错误: 命令执行超过了 1 秒的限制" in result
    
    @pytest.mark.asyncio
    async def test_shell_command_output_encoding(self, tmp_path):
        """Test shell command handles different encodings correctly."""
        # Create a file with Chinese characters
        test_file = tmp_path / "test.txt"
        test_file.write_text("你好，世界！", encoding="utf-8")
        
        response = await execute_shell_command(f"cat {test_file}", cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert "你好，世界！" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_shell_command_large_output(self, tmp_path):
        """Test shell command with large output."""
        # Create a file with 100 lines then cat it
        test_file = tmp_path / "lines.txt"
        with open(test_file, "w") as f:
            for i in range(1, 101):
                f.write(f"line {i}\n")
        
        response = await execute_shell_command(f"cat {test_file}", cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        lines = response.content[0]["text"].split("\n")
        assert len(lines) == 100
        assert lines[0] == "line 1"
        assert lines[-1] == "line 100"
    
    @pytest.mark.asyncio
    async def test_shell_command_general_exception(self, tmp_path):
        """Test general exception handling."""
        with patch('asyncio.create_subprocess_shell') as mock_create:
            mock_create.side_effect = Exception("Test exception")
            
            response = await execute_shell_command("echo test", cwd=tmp_path)
            assert response.content[0]["type"] == "text"
            assert "错误: Shell 命令执行失败，原因: \nTest exception" in response.content[0]["text"]


class TestExecutePythonCode:
    """Test execute_python_code function."""
    
    @pytest.mark.asyncio
    async def test_python_code_success(self, tmp_path):
        """Test successful Python code execution."""
        code = "print('Hello from Python')"
        response = await execute_python_code(code, cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert response.content[0]["text"] == "Hello from Python"
    
    @pytest.mark.asyncio
    async def test_python_code_success_no_output(self, tmp_path):
        """Test successful Python code with no output."""
        code = "x = 1 + 2"
        response = await execute_python_code(code, cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert "执行成功（无输出）" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_python_code_failure(self, tmp_path):
        """Test Python code with syntax error."""
        code = "print('unterminated string"
        response = await execute_python_code(code, cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        assert "执行失败，退出码" in result
        assert "[标准错误]" in result
        assert "SyntaxError" in result
    
    @pytest.mark.asyncio
    async def test_python_code_empty_code(self, tmp_path):
        """Test empty Python code returns error."""
        response = await execute_python_code("", cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert "错误: 未提供 Python 代码。" in response.content[0]["text"]
        
        # Test whitespace only
        response = await execute_python_code("   \n\t  ", cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert "错误: 未提供 Python 代码。" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_python_code_with_cwd(self, tmp_path):
        """Test Python code executes in specified working directory."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        code = f"""
with open('test.txt', 'r') as f:
    print(f.read())
"""
        response = await execute_python_code(code, cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert "test content" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_python_code_default_cwd(self):
        """Test Python code uses default WORKING_DIR when cwd not specified."""
        code = "import os; print(os.getcwd())"
        response = await execute_python_code(code)
        assert response.content[0]["type"] == "text"
        assert str(WORKING_DIR) in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_python_code_timeout(self, tmp_path):
        """Test Python code timeout handling."""
        code = "import time; time.sleep(2); print('done')"
        response = await execute_python_code(code, timeout=1, cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert "错误: Python 执行在 1 秒后超时。" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_python_code_uses_correct_interpreter(self, tmp_path):
        """Test Python code uses the same interpreter as the parent process."""
        code = "import sys; print(sys.executable)"
        response = await execute_python_code(code, cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert response.content[0]["text"] == sys.executable
    
    @pytest.mark.asyncio
    async def test_python_code_stderr_capture(self, tmp_path):
        """Test Python code captures stderr correctly."""
        code = "import sys; print('stdout output'); print('stderr output', file=sys.stderr); exit(1)"
        response = await execute_python_code(code, cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        result = response.content[0]["text"]
        assert "执行失败，退出码 1" in result
        assert "[标准输出]\nstdout output" in result
        assert "[标准错误]\nstderr output" in result
    
    @pytest.mark.asyncio
    async def test_python_code_general_exception(self, tmp_path):
        """Test general exception handling in Python execution."""
        with patch('asyncio.create_subprocess_exec') as mock_create:
            mock_create.side_effect = Exception("Test Python exception")
            
            code = "print('test')"
            response = await execute_python_code(code, cwd=tmp_path)
            assert response.content[0]["type"] == "text"
            assert "错误: Python 执行失败，原因: \nTest Python exception" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_python_code_complex_logic(self, tmp_path):
        """Test Python code with complex logic works correctly."""
        code = """
# Calculate sum of squares
result = sum(i**2 for i in range(10))
print(f"Sum of squares from 0 to 9: {result}")
"""
        response = await execute_python_code(code, cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        assert "Sum of squares from 0 to 9: 285" in response.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_python_code_non_utf8_output(self, tmp_path):
        """Test Python code handles non-UTF8 output correctly."""
        # Test with latin-1 characters
        code = "print(b'\\xe9\\xe8\\xe7'.decode('latin-1'))"
        response = await execute_python_code(code, cwd=tmp_path)
        assert response.content[0]["type"] == "text"
        # Should handle decoding correctly with replace
        assert "éèç" in response.content[0]["text"] or "�" in response.content[0]["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
