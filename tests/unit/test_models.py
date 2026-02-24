"""Tests for openbot.agents.models module"""

import pytest
import random
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from openbot.agents.models import ModelManager
from openbot.config import ModelConfig


class TestModelManager:
    """Test ModelManager class"""

    def test_init_default(self):
        """Test ModelManager initialization with default values"""
        manager = ModelManager()
        
        assert manager._default_model == ""
        assert manager._strategy == "auto"
        assert manager._chat_models == {}

    def test_init_with_params(self):
        """Test ModelManager initialization with custom values"""
        manager = ModelManager(strategy="manual", default_model="test-model")
        
        assert manager._default_model == "test-model"
        assert manager._strategy == "manual"
        assert manager._chat_models == {}

    @patch('openbot.agents.models.init_chat_model')
    def test_add_model_with_config(self, mock_init_chat_model):
        """Test adding model with ModelConfig"""
        manager = ModelManager()
        mock_model = Mock()
        mock_init_chat_model.return_value = mock_model
        
        config = ModelConfig(
            model_provider="openai",
            model="gpt-4",
            api_key="test-key",
            temperature=0.5
        )
        
        manager.add_model("gpt4", config)
        
        assert "gpt4" in manager._chat_models
        mock_init_chat_model.assert_called_once()
        assert manager._default_model == "gpt4"  # First model becomes default

    def test_add_model_with_base_model(self):
        """Test adding model with BaseChatModel directly"""
        manager = ModelManager()
        mock_model = Mock()
        
        manager.add_model("custom", mock_model)
        
        assert manager._chat_models["custom"] == mock_model
        assert manager._default_model == "custom"

    def test_add_model_multiple(self):
        """Test adding multiple models"""
        manager = ModelManager()
        mock_model1 = Mock()
        mock_model2 = Mock()
        
        manager.add_model("model1", mock_model1)
        manager.add_model("model2", mock_model2)
        
        assert len(manager._chat_models) == 2
        assert manager._default_model == "model1"  # First one is default

    def test_add_model_with_is_default(self):
        """Test adding model with is_default flag"""
        manager = ModelManager()
        mock_model1 = Mock()
        mock_model2 = Mock()
        
        manager.add_model("model1", mock_model1)
        manager.add_model("model2", mock_model2, is_default=True)
        
        assert manager._default_model == "model2"

    def test_get_model_default(self):
        """Test getting default model"""
        manager = ModelManager()
        mock_model = Mock()
        manager.add_model("default", mock_model)
        
        result = manager.get_model()
        
        assert result == mock_model

    def test_get_model_by_name(self):
        """Test getting model by name"""
        manager = ModelManager()
        mock_model1 = Mock()
        mock_model2 = Mock()
        manager.add_model("model1", mock_model1)
        manager.add_model("model2", mock_model2)
        
        result = manager.get_model("model2")
        
        assert result == mock_model2

    def test_get_model_not_found(self):
        """Test getting non-existent model"""
        manager = ModelManager()
        
        result = manager.get_model("nonexistent")
        
        assert result is None

    def test_get_model_auto_strategy(self):
        """Test auto strategy selects random model"""
        manager = ModelManager(strategy="auto")
        mock_model1 = Mock()
        mock_model2 = Mock()
        manager.add_model("model1", mock_model1)
        manager.add_model("model2", mock_model2)
        
        # Mock random.choice to return predictable result
        with patch('random.choice', return_value="model2"):
            result = manager.get_model("auto")
        
        assert result == mock_model2

    def test_get_model_auto_excludes_default(self):
        """Test auto strategy excludes default model from selection"""
        manager = ModelManager(strategy="auto")
        mock_model1 = Mock()
        mock_model2 = Mock()
        mock_model3 = Mock()
        manager.add_model("default", mock_model1)
        manager.add_model("model2", mock_model2)
        manager.add_model("model3", mock_model3)
        
        # Mock random.choice to verify it receives correct options
        with patch('random.choice') as mock_choice:
            mock_choice.return_value = "model2"
            manager.get_model("auto")
            
            # Should only include model2 and model3 (excluding default)
            options = mock_choice.call_args[0][0]
            assert "default" not in options
            assert "model2" in options
            assert "model3" in options

    def test_list_models_empty(self):
        """Test listing models when empty"""
        manager = ModelManager()
        
        result = manager.list_models()
        
        assert result == {}

    def test_list_models_with_models(self):
        """Test listing models with added models"""
        manager = ModelManager()
        mock_model1 = Mock()
        mock_model2 = Mock()
        manager.add_model("model1", mock_model1)
        manager.add_model("model2", mock_model2)
        
        result = manager.list_models()
        
        assert len(result) == 2
        assert result["model1"] == mock_model1
        assert result["model2"] == mock_model2

    def test_list_models_returns_dict_copy(self):
        """Test that list_models returns the internal dict"""
        manager = ModelManager()
        mock_model = Mock()
        manager.add_model("test", mock_model)
        
        result = manager.list_models()
        
        # Should return the same dict reference
        assert result is manager._chat_models


class TestModelManagerEdgeCases:
    """Test ModelManager edge cases"""

    def test_add_model_overwrite_existing(self):
        """Test that adding model with same name overwrites"""
        manager = ModelManager()
        mock_model1 = Mock()
        mock_model2 = Mock()
        
        manager.add_model("same", mock_model1)
        manager.add_model("same", mock_model2)
        
        assert manager._chat_models["same"] == mock_model2

    def test_get_model_empty_manager(self):
        """Test getting model from empty manager"""
        manager = ModelManager()
        
        result = manager.get_model()
        
        assert result is None

    def test_add_model_empty_name(self):
        """Test adding model with empty name"""
        manager = ModelManager()
        mock_model = Mock()
        
        manager.add_model("", mock_model)
        
        assert "" in manager._chat_models

    @patch('openbot.agents.models.init_chat_model')
    def test_add_model_config_exception(self, mock_init_chat_model):
        """Test handling exception during model initialization"""
        manager = ModelManager()
        mock_init_chat_model.side_effect = Exception("Init failed")
        
        config = ModelConfig(model="gpt-4")
        
        with pytest.raises(Exception, match="Init failed"):
            manager.add_model("failing", config)


class TestToolFunctionsImport:
    """Test that tool functions can be imported from models module"""

    def test_import_get_current_time(self):
        """Test get_current_time can be imported"""
        from openbot.agents.models import get_current_time
        
        result = get_current_time()
        assert isinstance(result, str)

    def test_import_remove_file(self):
        """Test remove_file can be imported"""
        from openbot.agents.models import remove_file
        
        # Just verify it's callable
        assert callable(remove_file)

    def test_import_run_bash_command(self):
        """Test run_bash_command can be imported"""
        from openbot.agents.models import run_bash_command
        
        # Just verify it's callable
        assert callable(run_bash_command)


class TestModelManagerIntegration:
    """Integration tests for ModelManager"""

    @patch('openbot.agents.models.init_chat_model')
    def test_full_workflow(self, mock_init_chat_model):
        """Test complete ModelManager workflow"""
        # Setup
        manager = ModelManager(strategy="manual")
        mock_model1 = Mock()
        mock_model2 = Mock()
        mock_init_chat_model.return_value = mock_model1
        
        # Add models
        config1 = ModelConfig(model="gpt-4")
        manager.add_model("gpt4", config1, is_default=True)
        manager.add_model("custom", mock_model2)
        
        # Verify
        assert manager.list_models() == {"gpt4": mock_model1, "custom": mock_model2}
        assert manager.get_model() == mock_model1  # Default
        assert manager.get_model("custom") == mock_model2
        
        # Test auto strategy
        with patch('random.choice', return_value="custom"):
            auto_model = manager.get_model("auto")
            assert auto_model == mock_model2
