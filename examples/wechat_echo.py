from mem0 import Memory
import os
from mem0.configs.base import MemoryConfig, VectorStoreConfig, LlmConfig, EmbedderConfig,

print(MemoryConfig(
    vector_store=VectorStoreConfig(
        provider='chroma',
        configs=ChromaDbConfig(
            db_path=os.path.join(mem0_dir, "chroma_db"),
        ),
    ),
    llm=None,
    embedder=None,
    graph_store=None,
    reranker=None,
    version="v1.1"
))

# 初始化（无需大模型）
mem0_dir = os.path.join(os.path.dirname(__file__), "mem0_data")
memory = Memory(
    config=MemoryConfig(
        vector_store=VectorStoreConfig(
            model='local',
        ),
        llm=None,
        embedder=None,
        graph_store=None,
        reranker=None,
        version="v1.1",
        
    ),
)

# 存储记忆
memory.add({"user_id": "user123", "content": "用户喜欢喝美式咖啡"})

# 检索记忆
memories = memory.search("用户喜欢的饮品", user_id="user123")
print(memories)