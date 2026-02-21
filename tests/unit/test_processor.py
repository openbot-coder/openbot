import pytest
from langchain_core.messages import HumanMessage, AIMessage
from openbot.botflow.processor import MessageProcessor


class TestMessageProcessor:
    """测试 MessageProcessor 类"""
    
    def test_preprocess_human_message(self):
        """测试预处理人类消息"""
        processor = MessageProcessor()
        message = HumanMessage(content="  Hello World  ", role="user", metadata={"key": "value"})
        processed_message = processor.preprocess(message)
        assert isinstance(processed_message, HumanMessage)
        assert processed_message.content == "Hello World"
        assert processed_message.role == "user"
        assert processed_message.metadata == {"key": "value"}
    
    def test_postprocess_ai_message(self):
        """测试后处理 AI 消息"""
        processor = MessageProcessor()
        message = AIMessage(content="  Hello from AI  ", role="assistant", metadata={"key": "value"})
        processed_message = processor.postprocess(message)
        assert isinstance(processed_message, AIMessage)
        assert processed_message.content == "Hello from AI"
        assert processed_message.role == "assistant"
        assert processed_message.metadata == {"key": "value"}
    
    def test_preprocess_with_empty_content(self):
        """测试预处理空内容消息"""
        processor = MessageProcessor()
        message = HumanMessage(content="   ", role="user")
        processed_message = processor.preprocess(message)
        assert isinstance(processed_message, HumanMessage)
        assert processed_message.content == ""
    
    def test_postprocess_with_empty_content(self):
        """测试后处理空内容消息"""
        processor = MessageProcessor()
        message = AIMessage(content="   ", role="assistant")
        processed_message = processor.postprocess(message)
        assert isinstance(processed_message, AIMessage)
        assert processed_message.content == ""
