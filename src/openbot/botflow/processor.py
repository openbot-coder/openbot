from ..channels import Message

class MessageProcessor:
    def preprocess(self, message: Message) -> Message:
        """预处理：清理、格式化用户输入"""
        # 清理用户输入
        cleaned_content = message.content.strip()
        
        # 创建新的 Message 对象，保持其他属性不变
        return Message(
            content=cleaned_content,
            role=message.role,
            metadata=message.metadata
        )
    
    def postprocess(self, message: Message) -> Message:
        """后处理：格式化 AI 输出"""
        # 这里可以添加格式化逻辑，比如添加分隔符、格式化代码等
        # 目前返回原始消息
        return message