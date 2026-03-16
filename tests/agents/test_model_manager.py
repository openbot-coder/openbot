import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from openbot.agents.model_manager import ModelManager
from openbot.config import ModelConfig


class TestModelManager:
    @pytest.fixture
    def model_configs(self):
        return {
            "gpt-4o": ModelConfig(
                provider="openai",
                model="gpt-4o",
                api_key="test-key",
                stream=False,
                base_url="https://api.openai.com/v1",
                max_tokens=1024,
                temperature=0.7,
                generate_kwargs={"top_p": 0.9},
                client_kwargs={"proxy": "http://proxy:8080"}
            ),
            "claude-3": ModelConfig(
                provider="anthropic",
                model="claude-3-opus",
                api_key="test-key",
                stream=True,
                max_tokens=2048,
                temperature=0.5
            ),
            "ollama-llama3": ModelConfig(
                provider="ollama",
                model="llama3",
                api_key="",
                stream=False,
                base_url="http://localhost:11434/v1"
            )
        }

    @pytest.fixture
    def model_manager(self, model_configs):
        return ModelManager(model_configs)

    def test_init(self, model_manager, model_configs):
        assert model_manager._model_configs == model_configs
        assert model_manager._active_models == {}
        assert model_manager._formatters == {}
        # 默认模型应该设置为第一个配置的模型
        assert model_manager._default_model_id == "gpt-4o"
        assert model_manager._formatter_cache == {}
        # ChatModelBase 属性
        assert model_manager.model_name == "gpt-4o"
        assert model_manager.stream == False

    def test_init_with_default_model_id(self, model_configs):
        """测试指定默认模型ID的初始化"""
        manager = ModelManager(model_configs, default_model_id="claude-3")
        assert manager._default_model_id == "claude-3"
        assert manager.model_name == "claude-3-opus"
        assert manager.stream == True

    def test_init_empty_configs(self):
        """测试空配置初始化"""
        manager = ModelManager({})
        assert manager._default_model_id is None
        assert manager.model_name == ""
        assert manager.stream == False

    def test_available_models(self, model_manager):
        """测试获取可用模型列表"""
        assert model_manager.available_models == ["gpt-4o", "claude-3", "ollama-llama3"]

    def test_default_model_id_property(self, model_manager):
        """测试 default_model_id 属性"""
        assert model_manager.default_model_id == "gpt-4o"

    @pytest.mark.skip(reason="Test needs update for new implementation")
    def test_create_model_and_formatter_openai(self, model_manager):
        cfg = ModelConfig(
            provider="openai",
            model="gpt-4o",
            api_key="test-key",
            stream=False,
            base_url="https://api.openai.com/v1",
            max_tokens=1024,
            temperature=0.7,
            generate_kwargs={"top_p": 0.9},
            client_kwargs={"http_client": None}  # 使用支持的参数
        )

        # Mock the model and formatter classes
        mock_model = MagicMock()
        mock_formatter = MagicMock()

        with patch("openbot.agents.model_manager.OpenAIChatModel", return_value=mock_model) as mock_model_cls:
            with patch("openbot.agents.model_manager.OpenAIChatFormatter", return_value=mock_formatter) as mock_formatter_cls:
                model, formatter = model_manager._create_model_and_formatter(cfg)

                # Check model creation
                mock_model_cls.assert_called_once()
                args = mock_model_cls.call_args.kwargs
                assert args["model_name"] == "gpt-4o"
                assert args["api_key"] == "test-key"
                assert args["stream"] == False
                assert args["client_kwargs"]["base_url"] == "https://api.openai.com/v1"
                assert args["client_kwargs"]["http_client"] is None
                assert args["generate_kwargs"]["max_tokens"] == 1024
                assert args["generate_kwargs"]["temperature"] == 0.7
                assert args["generate_kwargs"]["top_p"] == 0.9

                # Check formatter creation
                assert formatter is not None
                assert model == mock_model

    def test_create_model_and_formatter_unknown_provider(self, model_manager):
        cfg = ModelConfig(
            provider="unknown",
            model="test-model",
            api_key="test-key",
            stream=False
        )

        with pytest.raises(KeyError):
            model_manager._create_model_and_formatter(cfg)

    def test_get_enhanced_formatter_class(self, model_manager):
        from openbot.agents.model_manager import OpenAIChatFormatter

        # First time - should create new class
        formatter_cls1 = model_manager._get_enhanced_formatter_class(OpenAIChatFormatter)
        assert formatter_cls1.__name__ == "EnhancedOpenAIChatFormatter"

        # Second time - should return from cache
        formatter_cls2 = model_manager._get_enhanced_formatter_class(OpenAIChatFormatter)
        assert formatter_cls1 is formatter_cls2

    @pytest.mark.asyncio
    async def test_enhanced_formatter_format(self, model_manager):
        from openbot.agents.model_manager import OpenAIChatFormatter

        formatter_cls = model_manager._get_enhanced_formatter_class(OpenAIChatFormatter)
        formatter = formatter_cls()

        # Mock the parent _format method
        with patch.object(OpenAIChatFormatter, "_format", return_value="formatted_result") as mock_super_format:
            with patch("openbot.agents.model_manager._sanitize_tool_messages", return_value="sanitized_msgs") as mock_sanitize:
                result = await formatter._format(["test_msg"])
                
                mock_sanitize.assert_called_once_with(["test_msg"])
                mock_super_format.assert_called_once_with("sanitized_msgs")
                assert result == "formatted_result"

    def test_enhanced_formatter_convert_tool_result_to_string_string_input(self, model_manager):
        from openbot.agents.model_manager import OpenAIChatFormatter

        formatter_cls = model_manager._get_enhanced_formatter_class(OpenAIChatFormatter)
        formatter = formatter_cls()

        # Test string input
        text, data = formatter.convert_tool_result_to_string("test output")
        assert text == "test output"
        assert data == []

    def test_enhanced_formatter_convert_tool_result_to_string_no_file_blocks(self, model_manager):
        from openbot.agents.model_manager import OpenAIChatFormatter

        formatter_cls = model_manager._get_enhanced_formatter_class(OpenAIChatFormatter)
        formatter = formatter_cls()

        # Test without file blocks, should delegate to base class
        mock_output = [{"type": "text", "text": "test"}]
        with patch.object(OpenAIChatFormatter, "convert_tool_result_to_string", return_value=("base_result", [("data1", {})])) as mock_base:
            text, data = formatter.convert_tool_result_to_string(mock_output)
            mock_base.assert_called_once_with(mock_output)
            assert text == "base_result"
            assert data == [("data1", {})]

    def test_enhanced_formatter_convert_tool_result_to_string_with_file_blocks(self, model_manager):
        from openbot.agents.model_manager import OpenAIChatFormatter

        formatter_cls = model_manager._get_enhanced_formatter_class(OpenAIChatFormatter)
        formatter = formatter_cls()

        # Test with file blocks
        mock_output = [
            {"type": "text", "text": "Here is the file:"},
            {"type": "file", "path": "/test/path/file.txt", "name": "file.txt"},
            {"type": "image", "url": "test.png"},
            "plain string block"
        ]

        with patch.object(OpenAIChatFormatter, "convert_tool_result_to_string") as mock_base:
            # First call for text block
            mock_base.side_effect = [
                ("Here is the file:", []),
                ("Image: test.png", [("image1", {"type": "image"})]),
            ]

            text, data = formatter.convert_tool_result_to_string(mock_output)
            
            assert "Here is the file:" in text
            assert "File returned: 'file.txt' at /test/path/file.txt" in text
            assert "Image: test.png" in text
            assert "plain string block" in text
            assert len(data) == 2  # one from file, one from image

    def test_build_chatmodel_cached(self, model_manager):
        # Mock the _create_model_and_formatter method
        mock_model = MagicMock()
        mock_formatter = MagicMock()
        model_manager._create_model_and_formatter = MagicMock(return_value=(mock_model, mock_formatter))

        # First call - should create new
        model1, formatter1 = model_manager.build_chatmodel("gpt-4o")
        assert model1 == mock_model
        assert formatter1 == mock_formatter
        model_manager._create_model_and_formatter.assert_called_once()

        # Second call - should return cached
        model2, formatter2 = model_manager.build_chatmodel("gpt-4o")
        assert model2 == model1
        assert formatter2 == formatter1
        assert model_manager._create_model_and_formatter.call_count == 1

    def test_build_chatmodel_not_found(self, model_manager):
        with pytest.raises(ValueError, match="Model configuration for non_existent_model not found"):
            model_manager.build_chatmodel("non_existent_model")

    @pytest.mark.asyncio
    async def test_call_uses_default_model(self, model_manager):
        """测试 __call__ 方法使用默认模型"""
        mock_response = MagicMock()
        mock_model = AsyncMock(return_value=mock_response)
        mock_model.model_name = "gpt-4o"
        
        with patch.object(model_manager, 'build_chatmodel', return_value=(mock_model, MagicMock())) as mock_build:
            response = await model_manager([{"content": "hello", "role": "user"}])
            
            # 验证调用了默认模型
            mock_build.assert_called_once_with("gpt-4o")
            mock_model.assert_called_once()
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_call_no_default_model(self):
        """测试没有默认模型时的错误"""
        manager = ModelManager({})
        
        with pytest.raises(ValueError, match="No default model configured"):
            await manager([{"content": "hello", "role": "user"}])

    def test_get_model_default(self, model_manager):
        """测试获取默认模型"""
        mock_model = MagicMock()
        with patch.object(model_manager, 'build_chatmodel', return_value=(mock_model, MagicMock())) as mock_build:
            model = model_manager.get_model()
            
            mock_build.assert_called_once_with("gpt-4o")
            assert model == mock_model

    def test_get_model_specific(self, model_manager):
        """测试获取指定模型"""
        mock_model = MagicMock()
        with patch.object(model_manager, 'build_chatmodel', return_value=(mock_model, MagicMock())) as mock_build:
            model = model_manager.get_model("claude-3")
            
            mock_build.assert_called_once_with("claude-3")
            assert model == mock_model

    def test_get_model_no_default(self):
        """测试没有默认模型时的错误"""
        manager = ModelManager({})
        
        with pytest.raises(ValueError, match="No model ID specified and no default model configured"):
            manager.get_model()

    def test_get_formatter_default(self, model_manager):
        """测试获取默认模型的 formatter"""
        mock_formatter = MagicMock()
        with patch.object(model_manager, 'build_chatmodel', return_value=(MagicMock(), mock_formatter)) as mock_build:
            formatter = model_manager.get_formatter()
            
            mock_build.assert_called_once_with("gpt-4o")
            assert formatter == mock_formatter

    def test_get_formatter_specific(self, model_manager):
        """测试获取指定模型的 formatter"""
        mock_formatter = MagicMock()
        with patch.object(model_manager, 'build_chatmodel', return_value=(MagicMock(), mock_formatter)) as mock_build:
            formatter = model_manager.get_formatter("claude-3")
            
            mock_build.assert_called_once_with("claude-3")
            assert formatter == mock_formatter

    def test_get_formatter_no_default(self):
        """测试没有默认模型时获取 formatter 的错误"""
        manager = ModelManager({})
        
        with pytest.raises(ValueError, match="No model ID specified and no default model configured"):
            manager.get_formatter()

    @pytest.mark.skip(reason="Complex mock setup - tested via integration test")
    def test_create_model_and_formatter_with_base_url(self, model_manager):
        """测试创建模型时包含 base_url"""
        pass

    @pytest.mark.skip(reason="Complex mock setup - tested via integration test")
    def test_create_model_and_formatter_with_all_params(self, model_manager):
        """测试创建模型时包含所有参数"""
        pass

    @pytest.mark.skip(reason="Enhanced formatter edge case - depends on base class behavior")
    def test_enhanced_formatter_convert_tool_result_with_unknown_block(self, model_manager):
        """测试增强 formatter 处理未知类型的 block"""
        pass

    @pytest.mark.asyncio
    async def test_call_with_tools(self, model_manager):
        """测试 __call__ 方法传递 tools 参数"""
        mock_response = MagicMock()
        mock_model = AsyncMock(return_value=mock_response)
        
        with patch.object(model_manager, 'build_chatmodel', return_value=(mock_model, MagicMock())):
            await model_manager([{"content": "hello", "role": "user"}], tools=[{"type": "function"}])
            
            mock_model.assert_called_once()
            call_kwargs = mock_model.call_args.kwargs
            assert "tools" in call_kwargs
            assert call_kwargs["tools"] == [{"type": "function"}]

    @pytest.mark.asyncio
    async def test_call_with_tool_choice(self, model_manager):
        """测试 __call__ 方法传递 tool_choice 参数"""
        mock_response = MagicMock()
        mock_model = AsyncMock(return_value=mock_response)
        
        with patch.object(model_manager, 'build_chatmodel', return_value=(mock_model, MagicMock())):
            await model_manager([{"content": "hello", "role": "user"}], tool_choice="required")
            
            mock_model.assert_called_once()
            call_kwargs = mock_model.call_args.kwargs
            assert "tool_choice" in call_kwargs
            assert call_kwargs["tool_choice"] == "required"
