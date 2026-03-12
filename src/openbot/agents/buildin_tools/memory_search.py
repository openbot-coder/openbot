# -*- coding: utf-8 -*-
"""用于在记忆文件中进行语义检索的工具。"""

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock


def create_memory_search_tool(memory_manager):
    """创建绑定 memory_manager 的 memory_search 工具函数。

    Args:
        memory_manager: 用于搜索的 MemoryManager 实例

    Returns:
        可注册为工具的异步函数
    """

    async def memory_search(
        query: str,
        max_results: int = 5,
        min_score: float = 0.1,
    ) -> ToolResponse:
        """
        对 MEMORY.md 与 memory/*.md 文件进行语义检索。

        在回答关于过往工作、决策、日期、人物、偏好或待办的问题前应先调用本工具。
        返回带有文件路径和行号的高相关片段。

        Args:
            query (`str`):
                用于查找相关记忆片段的语义查询。
            max_results (`int`, optional):
                返回的最大结果数。默认 5。
            min_score (`float`, optional):
                结果最小相似度分数。默认 0.1。

        Returns:
            `ToolResponse`:
                包含路径、行号与内容的格式化搜索结果。
        """
        if memory_manager is None:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text="错误：记忆管理器未启用。",
                    ),
                ],
            )

        try:
            # memory_manager.memory_search 已返回 ToolResponse
            return await memory_manager.memory_search(
                query=query,
                max_results=max_results,
                min_score=min_score,
            )

        except Exception as e:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"错误：记忆搜索失败\n{e}",
                    ),
                ],
            )

    return memory_search
