from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, AnyMessage


class MessageProcessor:
    def preprocess(self, message: HumanMessage) -> HumanMessage:
        """预处理：清理、格式化用户输入"""
        # 清理用户输入
        cleaned_content = message.content.strip()

        # 创建新的 Message 对象，保持其他属性不变
        if hasattr(message, "dict"):
            # 对于 Pydantic 模型，使用 dict() 方法获取所有属性
            message_dict = message.dict()
            message_dict["content"] = cleaned_content
            return message.__class__(**message_dict)
        else:
            # 对于普通对象，只传递已知属性
            return message.__class__(
                content=cleaned_content, role=message.role, metadata=message.metadata
            )

    def postprocess(self, message: AnyMessage) -> AnyMessage:
        """后处理：格式化、添加元数据"""
        # 格式化消息内容
        formatted_content = message.content.strip()
        message.content = formatted_content

        # 创建新的 Message 对象，保持其他属性不变
        return message
