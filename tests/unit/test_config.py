import os
import pytest
from openbot.config import ConfigManager, OpenbotConfig


def test_config_manager_default():
    """测试默认配置"""
    config_manager = ConfigManager()
    config = config_manager.get()
    assert isinstance(config, OpenbotConfig)
    assert config.model_configs == {}
    assert config.agent_config.name == "openbot"
    assert "console" in config.channels
    assert config.channels["console"].enabled


def test_config_manager_load_file():
    """测试从文件加载配置"""
    config_path = "examples/config.json"
    config_manager = ConfigManager(config_path)
    config = config_manager.get()
    assert isinstance(config, OpenbotConfig)
    assert "doubao-seed-2-0-pro-260215" in config.model_configs
    assert "mimo-v2-flash" in config.model_configs
    assert "console" in config.channels
    assert config.channels["console"].enabled


def test_config_env_var_substitution():
    """测试环境变量替换"""
    import tempfile
    import json
    
    # 设置环境变量
    os.environ["TEST_API_KEY"] = "test-secret-key"
    
    temp_config = {
        "model_configs": {
            "test": {
                "model_provider": "openai",
                "model": "gpt-4o",
                "api_key": "${TEST_API_KEY}",
                "temperature": 0.7
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(temp_config, f)
        temp_config_path = f.name
    
    try:
        config_manager = ConfigManager(temp_config_path)
        config = config_manager.get()
        assert config.model_configs["test"].api_key == "test-secret-key"
    finally:
        # 清理
        import os
        os.unlink(temp_config_path)
        del os.environ["TEST_API_KEY"]


def test_config_manager_nonexistent_file():
    """测试加载不存在的文件"""
    # 使用不存在的文件路径
    config_manager = ConfigManager("nonexistent_config.json")
    config = config_manager.get()
    assert isinstance(config, OpenbotConfig)
    # 应该返回默认配置
    assert config.model_configs == {}
