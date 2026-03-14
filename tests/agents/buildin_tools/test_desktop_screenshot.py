import os
import json
import tempfile
import platform
import pytest
from unittest.mock import patch, MagicMock

from openbot.agents.buildin_tools.desktop_screenshot import (
    _tool_error,
    _tool_ok,
    _capture_mss,
    _capture_macos_screencapture,
    desktop_screenshot,
)


class TestDesktopScreenshot:
    def test_tool_error(self):
        error_msg = "Test error message"
        response = _tool_error(error_msg)
        
        assert len(response.content) == 1
        assert response.content[0]["type"] == "text"
        data = json.loads(response.content[0]["text"])
        assert data["ok"] is False
        assert data["error"] == error_msg

    def test_tool_ok(self):
        test_path = "/test/path/screenshot.png"
        test_msg = "Test success message"
        response = _tool_ok(test_path, test_msg)
        
        assert len(response.content) == 1
        assert response.content[0]["type"] == "text"
        data = json.loads(response.content[0]["text"])
        assert data["ok"] is True
        assert data["path"] == os.path.abspath(test_path)
        assert data["message"] == test_msg

    def test_capture_mss_import_error(self, tmp_path):
        test_path = str(tmp_path / "test.png")
        
        with patch("builtins.__import__", side_effect=ImportError("No module named 'mss'")):
            response = _capture_mss(test_path)
            
            data = json.loads(response.content[0]["text"])
            assert data["ok"] is False
            assert "mss 依赖 'mss' 包" in data["error"]

    def test_capture_mss_success(self, tmp_path):
        test_path = str(tmp_path / "test.png")
        
        # Mock mss
        mock_sct = MagicMock()
        mock_sct.shot.return_value = test_path
        
        with patch("openbot.agents.buildin_tools.desktop_screenshot.mss.mss", return_value=mock_sct):
            # Create the file to simulate successful shot
            open(test_path, "wb").close()
            
            response = _capture_mss(test_path)
            
            mock_sct.shot.assert_called_once_with(mon=0, output=test_path)
            data = json.loads(response.content[0]["text"])
            assert data["ok"] is True
            assert data["path"] == os.path.abspath(test_path)
            assert "Desktop screenshot saved to" in data["message"]

    def test_capture_mss_file_not_generated(self, tmp_path):
        test_path = str(tmp_path / "test.png")
        
        # Mock mss
        mock_sct = MagicMock()
        mock_sct.shot.return_value = test_path
        
        with patch("openbot.agents.buildin_tools.desktop_screenshot.mss.mss", return_value=mock_sct):
            # Don't create the file
            response = _capture_mss(test_path)
            
            data = json.loads(response.content[0]["text"])
            assert data["ok"] is False
            assert "mss 报告成功，但未生成文件" in data["error"]

    def test_capture_mss_exception(self, tmp_path):
        test_path = str(tmp_path / "test.png")
        
        # Mock mss to raise exception
        with patch("openbot.agents.buildin_tools.desktop_screenshot.mss.mss", side_effect=Exception("Test exception")):
            response = _capture_mss(test_path)
            
            data = json.loads(response.content[0]["text"])
            assert data["ok"] is False
            assert "desktop_screenshot (mss) failed: Test exception" in data["error"]

    def test_capture_macos_screencapture_success(self, tmp_path):
        test_path = str(tmp_path / "test.png")
        
        # Mock subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        with patch("openbot.agents.buildin_tools.desktop_screenshot.subprocess.run", return_value=mock_result):
            # Create the file
            open(test_path, "wb").close()
            
            response = _capture_macos_screencapture(test_path, capture_window=False)
            
            expected_cmd = ["screencapture", "-x", test_path]
            mock_result.run.assert_called_once()
            data = json.loads(response.content[0]["text"])
            assert data["ok"] is True
            assert data["path"] == os.path.abspath(test_path)

    def test_capture_macos_screencapture_capture_window(self, tmp_path):
        test_path = str(tmp_path / "test.png")
        
        # Mock subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        with patch("openbot.agents.buildin_tools.desktop_screenshot.subprocess.run", return_value=mock_result):
            open(test_path, "wb").close()
            
            response = _capture_macos_screencapture(test_path, capture_window=True)
            
            expected_cmd = ["screencapture", "-x", "-w", test_path]
            # Check that -w is in the command
            args, _ = mock_result.run.call_args
            assert "-w" in args[0]
            data = json.loads(response.content[0]["text"])
            assert data["ok"] is True

    def test_capture_macos_screencapture_command_failure(self, tmp_path):
        test_path = str(tmp_path / "test.png")
        
        # Mock subprocess.run to return error
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Test error"
        
        with patch("openbot.agents.buildin_tools.desktop_screenshot.subprocess.run", return_value=mock_result):
            response = _capture_macos_screencapture(test_path, capture_window=False)
            
            data = json.loads(response.content[0]["text"])
            assert data["ok"] is False
            assert "screencapture failed: Test error" in data["error"]

    def test_capture_macos_screencapture_file_not_generated(self, tmp_path):
        test_path = str(tmp_path / "test.png")
        
        # Mock subprocess.run success but no file
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        with patch("openbot.agents.buildin_tools.desktop_screenshot.subprocess.run", return_value=mock_result):
            # Don't create the file
            response = _capture_macos_screencapture(test_path, capture_window=False)
            
            data = json.loads(response.content[0]["text"])
            assert data["ok"] is False
            assert "screencapture 报告成功，但未生成文件" in data["error"]

    def test_capture_macos_screencapture_timeout(self, tmp_path):
        test_path = str(tmp_path / "test.png")
        
        from subprocess import TimeoutExpired
        
        with patch("openbot.agents.buildin_tools.desktop_screenshot.subprocess.run", side_effect=TimeoutExpired(cmd=["screencapture"], timeout=30)):
            response = _capture_macos_screencapture(test_path, capture_window=False)
            
            data = json.loads(response.content[0]["text"])
            assert data["ok"] is False
            assert "screencapture 超时" in data["error"]

    def test_capture_macos_screencapture_general_exception(self, tmp_path):
        test_path = str(tmp_path / "test.png")
        
        with patch("openbot.agents.buildin_tools.desktop_screenshot.subprocess.run", side_effect=Exception("Test exception")):
            response = _capture_macos_screencapture(test_path, capture_window=False)
            
            data = json.loads(response.content[0]["text"])
            assert data["ok"] is False
            assert "desktop_screenshot failed: Test exception" in data["error"]

    @pytest.mark.asyncio
    async def test_desktop_screenshot_empty_path(self):
        with patch("openbot.agents.buildin_tools.desktop_screenshot._capture_mss") as mock_capture:
            mock_capture.return_value = _tool_ok("/tmp/test.png", "Success")
            
            await desktop_screenshot(path="", capture_window=False)
            
            # Check that the path passed to _capture_mss is a temp file with .png extension
            args, _ = mock_capture.call_args
            path = args[0]
            assert path.startswith(tempfile.gettempdir())
            assert path.endswith(".png")
            assert "desktop_screenshot_" in path

    @pytest.mark.asyncio
    async def test_desktop_screenshot_path_without_png_extension(self, tmp_path):
        test_path = str(tmp_path / "test")  # No .png extension
        
        with patch("openbot.agents.buildin_tools.desktop_screenshot._capture_mss") as mock_capture:
            mock_capture.return_value = _tool_ok(f"{test_path}.png", "Success")
            
            await desktop_screenshot(path=test_path, capture_window=False)
            
            args, _ = mock_capture.call_args
            assert args[0] == f"{test_path}.png"

    @pytest.mark.asyncio
    async def test_desktop_screenshot_macos_capture_window_true(self):
        with patch("platform.system", return_value="Darwin"):
            with patch("openbot.agents.buildin_tools.desktop_screenshot._capture_macos_screencapture") as mock_capture:
                mock_capture.return_value = _tool_ok("/test.png", "Success")
                
                await desktop_screenshot(path="/test.png", capture_window=True)
                
                mock_capture.assert_called_once_with("/test.png", capture_window=True)

    @pytest.mark.asyncio
    async def test_desktop_screenshot_macos_capture_window_false(self):
        with patch("platform.system", return_value="Darwin"):
            with patch("openbot.agents.buildin_tools.desktop_screenshot._capture_mss") as mock_capture:
                mock_capture.return_value = _tool_ok("/test.png", "Success")
                
                await desktop_screenshot(path="/test.png", capture_window=False)
                
                mock_capture.assert_called_once_with("/test.png")

    @pytest.mark.asyncio
    async def test_desktop_screenshot_linux_capture_window_ignored(self):
        with patch("platform.system", return_value="Linux"):
            with patch("openbot.agents.buildin_tools.desktop_screenshot._capture_mss") as mock_capture:
                mock_capture.return_value = _tool_ok("/test.png", "Success")
                
                await desktop_screenshot(path="/test.png", capture_window=True)
                
                mock_capture.assert_called_once_with("/test.png")

    @pytest.mark.asyncio
    async def test_desktop_screenshot_windows_capture_window_ignored(self):
        with patch("platform.system", return_value="Windows"):
            with patch("openbot.agents.buildin_tools.desktop_screenshot._capture_mss") as mock_capture:
                mock_capture.return_value = _tool_ok("/test.png", "Success")
                
                await desktop_screenshot(path="/test.png", capture_window=True)
                
                mock_capture.assert_called_once_with("/test.png")

    @pytest.mark.asyncio
    async def test_desktop_screenshot_path_with_special_characters(self, tmp_path):
        test_path = str(tmp_path / "test path with spaces and 中文.png")
        
        with patch("openbot.agents.buildin_tools.desktop_screenshot._capture_mss") as mock_capture:
            mock_capture.return_value = _tool_ok(test_path, "Success")
            
            await desktop_screenshot(path=test_path, capture_window=False)
            
            mock_capture.assert_called_once_with(test_path)
