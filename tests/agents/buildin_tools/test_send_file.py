import os
import pytest
from unittest.mock import patch, mock_open

from openbot.agents.buildin_tools.send_file import (
    _auto_as_type,
    send_file_to_user,
)


class TestSendFile:
    def test_auto_as_type(self):
        # Test image types
        assert _auto_as_type("image/png") == "image"
        assert _auto_as_type("image/jpeg") == "image"
        assert _auto_as_type("image/gif") == "image"
        
        # Test audio types
        assert _auto_as_type("audio/mpeg") == "audio"
        assert _auto_as_type("audio/wav") == "audio"
        assert _auto_as_type("audio/ogg") == "audio"
        
        # Test video types
        assert _auto_as_type("video/mp4") == "video"
        assert _auto_as_type("video/mov") == "video"
        assert _auto_as_type("video/avi") == "video"
        
        # Test text types
        assert _auto_as_type("text/plain") == "text"
        assert _auto_as_type("text/markdown") == "text"
        assert _auto_as_type("text/html") == "text"
        
        # Test other types
        assert _auto_as_type("application/json") == "file"
        assert _auto_as_type("application/pdf") == "file"
        assert _auto_as_type("application/octet-stream") == "file"

    @pytest.mark.asyncio
    async def test_send_file_not_exists(self):
        non_existent_path = "/non/existent/file.txt"
        response = await send_file_to_user(non_existent_path)
        
        assert len(response.content) == 1
        assert response.content[0]["type"] == "text"
        assert f"错误：文件 {non_existent_path} 不存在。" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_send_file_is_directory(self, tmp_path):
        # Create a directory
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        
        response = await send_file_to_user(str(test_dir))
        
        assert len(response.content) == 1
        assert response.content[0]["type"] == "text"
        assert f"错误：路径 {str(test_dir)} 不是文件。" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_send_text_file(self, tmp_path):
        # Create a test text file
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content, encoding="utf-8")
        
        response = await send_file_to_user(str(test_file))
        
        assert len(response.content) == 1
        assert response.content[0]["type"] == "text"
        assert response.content[0]["text"] == test_content

    @pytest.mark.asyncio
    async def test_send_image_file(self, tmp_path):
        # Create a test image file
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"fake png content")
        
        response = await send_file_to_user(str(test_file))
        
        assert len(response.content) == 2
        assert response.content[0]["type"] == "image"
        assert response.content[0]["source"]["type"] == "url"
        assert response.content[0]["source"]["url"].startswith("file://")
        assert str(test_file) in response.content[0]["source"]["url"]
        assert response.content[1]["type"] == "text"
        assert response.content[1]["text"] == "已成功发送文件"

    @pytest.mark.asyncio
    async def test_send_audio_file(self, tmp_path):
        # Create a test audio file
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake mp3 content")
        
        response = await send_file_to_user(str(test_file))
        
        assert len(response.content) == 2
        assert response.content[0]["type"] == "audio"
        assert response.content[0]["source"]["type"] == "url"
        assert response.content[0]["source"]["url"].startswith("file://")
        assert str(test_file) in response.content[0]["source"]["url"]
        assert response.content[1]["type"] == "text"
        assert response.content[1]["text"] == "已成功发送文件"

    @pytest.mark.asyncio
    async def test_send_video_file(self, tmp_path):
        # Create a test video file
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake mp4 content")
        
        response = await send_file_to_user(str(test_file))
        
        assert len(response.content) == 2
        assert response.content[0]["type"] == "video"
        assert response.content[0]["source"]["type"] == "url"
        assert response.content[0]["source"]["url"].startswith("file://")
        assert str(test_file) in response.content[0]["source"]["url"]
        assert response.content[1]["type"] == "text"
        assert response.content[1]["text"] == "已成功发送文件"

    @pytest.mark.asyncio
    async def test_send_unknown_file_type(self, tmp_path):
        # Create a test file with unknown extension
        test_file = tmp_path / "test.unknown"
        test_content = b"fake unknown content"
        test_file.write_bytes(test_content)
        
        response = await send_file_to_user(str(test_file))
        
        assert len(response.content) == 2
        assert response.content[0]["type"] == "file"
        assert response.content[0]["source"]["type"] == "url"
        assert str(test_file) in response.content[0]["source"]["url"]
        assert response.content[0]["filename"] == "test.unknown"
        assert response.content[1]["type"] == "text"
        assert response.content[1]["text"] == "已成功发送文件"

    @pytest.mark.asyncio
    async def test_send_pdf_file(self, tmp_path):
        # Create a test pdf file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4 fake pdf content")
        
        response = await send_file_to_user(str(test_file))
        
        assert len(response.content) == 2
        assert response.content[0]["type"] == "file"
        assert response.content[0]["filename"] == "test.pdf"
        assert response.content[1]["type"] == "text"
        assert response.content[1]["text"] == "已成功发送文件"

    @pytest.mark.asyncio
    async def test_send_file_permission_error(self, tmp_path):
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        # Mock open to raise PermissionError
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            response = await send_file_to_user(str(test_file))
            
            assert len(response.content) == 1
            assert response.content[0]["type"] == "text"
            assert "错误：发送文件失败" in response.content[0]["text"]
            assert "Permission denied" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_send_file_general_exception(self, tmp_path):
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        # Mock os.path.exists to raise exception
        with patch("os.path.exists", side_effect=Exception("Unexpected error")):
            response = await send_file_to_user(str(test_file))
            
            assert len(response.content) == 1
            assert response.content[0]["type"] == "text"
            assert "错误：发送文件失败" in response.content[0]["text"]
            assert "Unexpected error" in response.content[0]["text"]
