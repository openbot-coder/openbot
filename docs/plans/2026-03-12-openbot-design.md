# OpenBot 设计文档

## 1. 项目概述
OpenBot 是一个基于 `AgentScope` 和 `AgentScope-Runtime` 的模块化机器人框架。它旨在提供一个统一的接口来创建、管理和部署智能代理，并支持多渠道接入和强大的资源管理功能。

## 2. 核心架构
项目采用模块化单体架构，分为两个主要模块：
- **`agents`**: 负责 Agent 的逻辑定义、子代理实现及统一创建接口。
- **`gateway`**: 负责对外提供服务接口、管理资源（Memory, Skills, MCP）以及多渠道消息转发。

## 3. 模块设计

### 3.1 `agents` 模块
- **`templates/`**: 存储预置的 Prompt 模板、Skills 定义、Memory 配置。这些内容在系统启动时会拷贝到 `~/.openbot/`。
- **`subagents/`**: 存放具体的子代理实现类。
- **`factory.py`**: 提供 `create_agent(config: dict)` 统一接口，根据配置动态实例化 Agent。

### 3.2 `gateway` 模块
集成 `agentscope-runtime`，复用其内置的 FastAPI、WebSocket 和 OpenAI 兼容接口能力。
- **任务调度 (`scheduler/`)**:
    - **Custom Scheduler**: 自研的简单异步任务调度器，负责执行周期性任务（如清理会话、状态同步）。
- **资源管理 (`manager/`)**:
    - **Memory**: 管理短期会话（Session）和长期记忆。
    - **Skills**: 动态加载和注册 `~/.openbot/skills/` 下的工具。
    - **MCP**: 使用 `AgentScope` 的 `Toolkit` 实现对 Stdio 和 HTTP MCP 客户端的支持。
- **多渠道适配 (`channels/`)**:
    - 适配飞书、微信、QQ 等外部渠道，实现消息的接收与回复转发。

### 3.3 `core` 模块
- **`initializer.py`**: 负责环境初始化，确保 `agents/templates/` 下的内容正确同步到 `~/.openbot/`。

## 4. 技术栈
- **核心框架**: [AgentScope](https://github.com/modelscope/agentscope) & [AgentScope-Runtime](https://github.com/modelscope/agentscope-runtime)
- **Web 服务**: FastAPI (由 AgentScope-Runtime 集成)
- **任务调度**: 自研异步任务调度器 (基于 asyncio)
- **MCP 支持**: AgentScope Toolkit (StdioClient, HttpClient)
- **依赖管理**: uv

## 5. 数据流向
1. 外部请求（WS/API/Channel）进入 `gateway`。
2. `gateway` 获取或创建对应的 `session`。
3. `gateway` 调用 `agents.factory.create_agent` 获取 Agent 实例。
4. Agent 调用 `gateway` 管理的 `skills` 或 `MCP` 工具完成任务。
5. 结果通过 `gateway` 返回给请求方。
