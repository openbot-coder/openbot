#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for config module."""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
from openbot.config import ConfigManager, ModelConfig, BotFlowConfig


class TestModelConfig:
    """Test ModelConfig class."""
    
    def test_default_values(self):
        """Test default values are set correctly."""
        config = ModelConfig()
        assert config.model_id == ""
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.api_key == ""
        assert config.base_url == ""
        assert config.stream is False
        assert config.max_tokens == 2048
        assert config.temperature == 0.7
        assert config.stream_tool_parsing is True
        assert config.thinking == {}
        assert config.client_kwargs == {}
        assert config.generate_kwargs == {}
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = ModelConfig(
            model_id="test_model",
            provider="anthropic",
            model="claude-3-opus",
            api_key="sk-test123",
            base_url="https://api.anthropic.com",
            stream=True,
            max_tokens=4096,
            temperature=0.1,
            stream_tool_parsing=False
        )
        assert config.model_id == "test_model"
        assert config.provider == "anthropic"
        assert config.model == "claude-3-opus"
        assert config.api_key == "sk-test123"
        assert config.base_url == "https://api.anthropic.com"
        assert config.stream is True
        assert config.max_tokens == 4096
        assert config.temperature == 0.1
        assert config.stream_tool_parsing is False
    
    def test_extra_fields_allowed(self):
        """Test extra fields are allowed in ModelConfig."""
        config = ModelConfig(
            model_id="test",
            custom_field="value",
            another_field=123
        )
        assert config.custom_field == "value"
        assert config.another_field == 123


class TestBotFlowConfig:
    """Test BotFlowConfig class."""
    
    def test_default_values(self):
        """Test default values are set correctly."""
        config = BotFlowConfig()
        assert isinstance(config.work_dir, str)
        assert config.model_configs == {}
        assert config.mcp_config_path == "{$OPENBOT_HOMESPACE}/config/mcp.json"
        assert config.db_path == "{$OPENBOT_HOMESPACE}/memory/memory.db"
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        assert config.debug is False
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = BotFlowConfig(
            work_dir="/tmp/test",
            host="0.0.0.0",
            port=9000,
            debug=True
        )
        assert config.work_dir == "/tmp/test"
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.debug is True


class TestConfigManager:
    """Test ConfigManager class."""
    
    def setup_method(self):
        """Setup test environment by setting OPENBOT_HOMESPACE env var."""
        import os
        os.environ["OPENBOT_HOMESPACE"] = "/tmp/test_home"
    
    def teardown_method(self):
        """Cleanup environment variables."""
        import os
        if "OPENBOT_HOMESPACE" in os.environ:
            del os.environ["OPENBOT_HOMESPACE"]
    
    def test_init_with_existing_config_file(self, tmp_path):
        """Test initialization with existing config file."""
        config_file = tmp_path / "config.json"
        config_data = {
            "host": "0.0.0.0",
            "port": 9000,
            "debug": True
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config_manager = ConfigManager(config_file)
        assert config_manager.config.host == "0.0.0.0"
        assert config_manager.config.port == 9000
        assert config_manager.config.debug is True
        # raw_config contains exactly what was in the config file
        assert config_manager.raw_config == config_data
        assert config_manager.raw_config["host"] == "0.0.0.0"
        assert config_manager.raw_config["port"] == 9000
        assert config_manager.raw_config["debug"] == True
    
    def test_init_with_nonexistent_config_file(self, tmp_path):
        """Test initialization with non-existent config file (uses defaults)."""
        config_file = tmp_path / "nonexistent_config.json"
        assert not config_file.exists()
        
        config_manager = ConfigManager(config_file)
        # Should use default BotFlowConfig values
        assert config_manager.config.host == "127.0.0.1"
        assert config_manager.config.port == 8000
        assert config_manager.config.debug is False
    
    def test_add_model_config(self, tmp_path):
        """Test adding model configuration."""
        config_file = tmp_path / "config.json"
        config_manager = ConfigManager(config_file)
        
        model_config = ModelConfig(
            model_id="test_model",
            provider="openai",
            model="gpt-4o"
        )
        
        config_manager.add_model_config(model_config)
        assert "test_model" in config_manager.config.model_configs
        assert config_manager.config.model_configs["test_model"].model == "gpt-4o"
    
    def test_resolve_env_vars_dollar_brace_format(self, tmp_path, monkeypatch):
        """Test resolving environment variables in ${VAR} format."""
        monkeypatch.setenv("TEST_HOME", "/home/test")
        monkeypatch.setenv("API_KEY", "sk-12345")
        
        config_file = tmp_path / "config.json"
        config_data = {
            "work_dir": "${TEST_HOME}/work",
            "model_configs": {
                "default": {
                    "api_key": "${API_KEY}"
                }
            }
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config_manager = ConfigManager(config_file)
        assert config_manager.config.work_dir == "/home/test/work"
        assert config_manager.config.model_configs["default"].api_key == "sk-12345"
    
    def test_resolve_env_vars_brace_dollar_format(self, tmp_path, monkeypatch):
        """Test resolving environment variables in {$VAR} format."""
        monkeypatch.setenv("OPENBOT_HOMESPACE", "/home/test/.openbot")
        
        config_file = tmp_path / "config.json"
        config_data = {
            "mcp_config_path": "{$OPENBOT_HOMESPACE}/config/mcp.json",
            "db_path": "{$OPENBOT_HOMESPACE}/memory/memory.db"
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config_manager = ConfigManager(config_file)
        assert config_manager.config.mcp_config_path == "/home/test/.openbot/config/mcp.json"
        assert config_manager.config.db_path == "/home/test/.openbot/memory/memory.db"
    
    def test_resolve_env_vars_in_list(self, tmp_path, monkeypatch):
        """Test resolving environment variables in list values."""
        monkeypatch.setenv("PATH1", "/path1")
        monkeypatch.setenv("PATH2", "/path2")
        
        config_file = tmp_path / "config.json"
        config_data = {
            "search_paths": ["${PATH1}/bin", "{$PATH2}/lib", "/static/path"]
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config_manager = ConfigManager(config_file)
        assert config_manager.raw_config["search_paths"] == [
            "${PATH1}/bin",
            "{$PATH2}/lib",
            "/static/path"
        ]
        # Resolved values are in the processed config
        config_dict = config_manager.config.model_dump()
        # For Pydantic v2, extra fields are in model_extra or __dict__
        if "search_paths" in config_dict:
            assert config_dict["search_paths"] == [
                "/path1/bin",
                "/path2/lib",
                "/static/path"
            ]
        else:
            # Check in __dict__
            assert hasattr(config_manager.config, "search_paths")
            assert getattr(config_manager.config, "search_paths") == [
                "/path1/bin",
                "/path2/lib",
                "/static/path"
            ]
    
    def test_resolve_env_vars_in_keys(self, tmp_path, monkeypatch):
        """Test resolving environment variables in dictionary keys."""
        monkeypatch.setenv("MODEL_NAME", "gpt-4o")
        
        config_file = tmp_path / "config.json"
        config_data = {
            "model_configs": {
                "${MODEL_NAME}": {
                    "model": "${MODEL_NAME}"
                }
            }
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config_manager = ConfigManager(config_file)
        assert "gpt-4o" in config_manager.config.model_configs
        assert config_manager.config.model_configs["gpt-4o"].model == "gpt-4o"
    
    def test_missing_env_var_prompt(self, tmp_path):
        """Test missing environment variable prompts user for input."""
        config_file = tmp_path / "config.json"
        config_data = {
            "api_key": "${MISSING_VAR}"
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        # Mock user input
        with patch("builtins.input", return_value="user_provided_value"):
            config_manager = ConfigManager(config_file)
            assert config_manager.raw_config["api_key"] == "${MISSING_VAR}"  # raw has original
            # Resolved value is in the config object
            assert hasattr(config_manager.config, "api_key")
            assert getattr(config_manager.config, "api_key") == "user_provided_value"
        
        # Check that .env file was created with the value
        env_file = tmp_path / ".env"
        assert env_file.exists()
        with open(env_file, "r") as f:
            env_content = f.read()
            assert "MISSING_VAR=user_provided_value" in env_content
    
    def test_load_env_file(self, tmp_path):
        """Test loading variables from .env file."""
        # Create .env file
        env_file = tmp_path / ".env"
        with open(env_file, "w") as f:
            f.write("API_KEY=from_env_file\n")
            f.write("HOME_DIR=/home/from_env\n")
        
        config_file = tmp_path / "config.json"
        config_data = {
            "api_key": "${API_KEY}",
            "work_dir": "${HOME_DIR}/work"
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config_manager = ConfigManager(config_file)
        assert config_manager.raw_config["api_key"] == "${API_KEY}"
        assert config_manager.raw_config["work_dir"] == "${HOME_DIR}/work"
        # Resolved values
        assert hasattr(config_manager.config, "api_key")
        assert getattr(config_manager.config, "api_key") == "from_env_file"
        assert config_manager.config.work_dir == "/home/from_env/work"
    
    def test_nested_env_resolution(self, tmp_path, monkeypatch):
        """Test resolving nested environment variables."""
        monkeypatch.setenv("PARENT_DIR", "/home/parent")
        monkeypatch.setenv("CHILD_DIR", "child")
        
        config_file = tmp_path / "config.json"
        config_data = {
            "nested_path": "${PARENT_DIR}/${CHILD_DIR}/deep"
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config_manager = ConfigManager(config_file)
        assert config_manager.raw_config["nested_path"] == "${PARENT_DIR}/${CHILD_DIR}/deep"
        assert hasattr(config_manager.config, "nested_path")
        assert getattr(config_manager.config, "nested_path") == "/home/parent/child/deep"
    
    def test_no_env_vars_in_non_string_values(self, tmp_path):
        """Test that non-string values are not processed for env vars."""
        config_file = tmp_path / "config.json"
        config_data = {
            "port": 8080,
            "debug": True,
            "timeout": 30.5,
            "null_value": None
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config_manager = ConfigManager(config_file)
        assert config_manager.config.port == 8080
        assert config_manager.config.debug is True
        assert config_manager.raw_config["timeout"] == 30.5
        assert config_manager.raw_config["null_value"] is None
        # Non-string values are preserved correctly
        assert hasattr(config_manager.config, "timeout")
        assert getattr(config_manager.config, "timeout") == 30.5
        assert hasattr(config_manager.config, "null_value")
        assert getattr(config_manager.config, "null_value") is None
    
    def test_empty_env_var_value(self, tmp_path, monkeypatch):
        """Test handling of empty environment variable values."""
        monkeypatch.setenv("EMPTY_VAR", "")
        
        config_file = tmp_path / "config.json"
        config_data = {
            "empty_value": "${EMPTY_VAR}"
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        # Should prompt user for input since env var is empty
        with patch("builtins.input", return_value="user_input"):
            config_manager = ConfigManager(config_file)
            assert config_manager.raw_config["empty_value"] == "${EMPTY_VAR}"
            assert hasattr(config_manager.config, "empty_value")
            assert getattr(config_manager.config, "empty_value") == "user_input"
    
    def test_config_property_returns_botflowconfig(self, tmp_path):
        """Test config property returns BotFlowConfig instance."""
        config_file = tmp_path / "config.json"
        config_manager = ConfigManager(config_file)
        assert isinstance(config_manager.config, BotFlowConfig)
    
    def test_raw_config_property_returns_dict(self, tmp_path):
        """Test raw_config property returns original dict."""
        config_file = tmp_path / "config.json"
        config_data = {"custom": "value"}
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config_manager = ConfigManager(config_file)
        assert isinstance(config_manager.raw_config, dict)
        assert config_manager.raw_config == config_data
        assert config_manager.raw_config["custom"] == "value"
        assert "custom" in config_manager.raw_config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
