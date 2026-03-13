"""
OpenBot Gateway - 基于 AgentScope Runtime 的多智能体 WebUI 服务
"""
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.pipeline import stream_printing_messages
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from openbot.agents.tool_manger import ToolKitManager
from openbot.agents.model_manager import ModelManager
from openbot.config import BotFlowConfig, ConfigManager
from openbot.gateway.botflow import BotFlow


# 全局 BotFlow 实例
_bot_flow: BotFlow = None


class MessageRequest(BaseModel):
    """消息请求模型"""
    message: str
    agent_name: str = "assistant"
    model_id: str = "doubao_auto"
    session_id: str = "default"
    user_id: str = "user"


class MessageResponse(BaseModel):
    """消息响应模型"""
    response: str
    agent_name: str
    session_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理服务生命周期资源"""
    global _bot_flow

    # 启动：初始化 BotFlow
    print("Initializing OpenBot Gateway...")

    # 加载配置
    config_path = os.path.join(
        os.getenv("OPENBOT_HOMESPACE", "E:\\src\\openbot\\.openbot"),
        "config",
        "config.json"
    )
    config_manager = ConfigManager(config_path)
    config = config_manager.config

    # 创建 BotFlow 实例
    _bot_flow = BotFlow(config)
    await _bot_flow.initialize()

    print(f"OpenBot Gateway initialized with {len(config.model_configs)} models")
    print(f"Available models: {list(config.model_configs.keys())}")

    yield  # 服务运行中

    # 关闭：清理资源
    print("Shutting down OpenBot Gateway...")
    _bot_flow = None


# 创建 AgentApp 实例
agent_app = AgentApp(
    app_name="OpenBot Gateway",
    app_description="基于 AgentScope Runtime 的多智能体 WebUI 服务",
    lifespan=lifespan,
    # 可以在这里配置 session 管理器
    # session_backend="redis",  # 或 "memory"
)


@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    """
    处理查询请求的核心逻辑

    Args:
        msgs: 消息列表
        request: AgentRequest 对象，包含 session_id, user_id 等
        **kwargs: 其他参数

    Yields:
        (msg, last): 流式输出消息和完成标志
    """
    global _bot_flow

    if not _bot_flow:
        raise RuntimeError("BotFlow not initialized")

    # 解析请求参数
    if isinstance(msgs, list) and len(msgs) > 0:
        user_message = msgs[-1].content if hasattr(msgs[-1], 'content') else str(msgs[-1])
    else:
        user_message = str(msgs)

    # 从 request 中获取参数
    agent_name = getattr(request, 'agent_name', 'assistant') if request else 'assistant'
    model_id = getattr(request, 'model_id', 'doubao_auto') if request else 'doubao_auto'
    session_id = request.session_id if request else 'default'
    user_id = request.user_id if request else 'user'

    print(f"[query_func] Received message: {user_message}")
    print(f"[query_func] Agent: {agent_name}, Model: {model_id}, Session: {session_id}")

    try:
        # 创建或获取智能体
        agent = _bot_flow.create_agent(
            name=agent_name,
            system_prompt="你是一个有用的智能助手",
            model_id=model_id
        )

        # 创建用户消息
        user_msg = Msg(
            name=user_id,
            content=user_message,
            role="user",
        )

        # 流式输出响应
        async for msg, last in stream_printing_messages(
            agents=[agent],
            coroutine_task=agent([user_msg]),
        ):
            yield msg, last

    except Exception as e:
        print(f"[query_func] Error: {str(e)}")
        raise


# WebUI 路由
from fastapi.responses import HTMLResponse
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)


manager = ConnectionManager()


@agent_app.get("/")
async def webui_root(request: Request):
    """WebUI 首页"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OpenBot Gateway</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .chat-box {
                height: 400px;
                overflow-y: auto;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                margin-bottom: 10px;
                background: #fafafa;
            }
            .message {
                margin: 10px 0;
                padding: 10px;
                border-radius: 5px;
            }
            .user {
                background: #e3f2fd;
                text-align: right;
            }
            .assistant {
                background: #f1f1f1;
            }
            input, select, button {
                padding: 10px;
                margin: 5px;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            input[type="text"] {
                flex: 1;
            }
            .controls {
                display: flex;
                gap: 10px;
                margin-bottom: 10px;
            }
            button {
                background: #007bff;
                color: white;
                border: none;
                cursor: pointer;
            }
            button:hover {
                background: #0056b3;
            }
            button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 OpenBot Gateway</h1>

            <div class="controls">
                <select id="modelSelect">
                    <option value="doubao_auto">Doubao</option>
                    <option value="openai_gpt4">GPT-4</option>
                </select>
                <input type="text" id="agentName" placeholder="Agent名称" value="assistant">
                <input type="text" id="sessionId" placeholder="会话ID" value="default">
            </div>

            <div class="chat-box" id="chatBox"></div>

            <div style="display: flex;">
                <input type="text" id="messageInput" placeholder="输入消息..." onkeypress="handleKeyPress(event)">
                <button onclick="sendMessage()" id="sendBtn">发送</button>
            </div>
        </div>

        <script>
            const ws = new WebSocket(`ws://${location.host}/ws/${Date.now()}`);
            const chatBox = document.getElementById('chatBox');
            const messageInput = document.getElementById('messageInput');
            const sendBtn = document.getElementById('sendBtn');
            const modelSelect = document.getElementById('modelSelect');
            const agentNameInput = document.getElementById('agentName');
            const sessionIdInput = document.getElementById('sessionId');

            let currentSessionId = sessionIdInput.value;
            let isProcessing = false;

            ws.onopen = () => {
                addMessage('system', '已连接到服务器');
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'chunk') {
                    appendToLastMessage(data.content);
                } else if (data.type === 'done') {
                    isProcessing = false;
                    sendBtn.disabled = false;
                    messageInput.disabled = false;
                } else if (data.type === 'error') {
                    addMessage('system', '错误: ' + data.content);
                    isProcessing = false;
                    sendBtn.disabled = false;
                    messageInput.disabled = false;
                } else if (data.type === 'session_start') {
                    currentSessionId = data.session_id;
                    sessionIdInput.value = currentSessionId;
                }
            };

            ws.onclose = () => {
                addMessage('system', '连接已关闭');
            };

            function handleKeyPress(event) {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage();
                }
            }

            async function sendMessage() {
                const message = messageInput.value.trim();
                if (!message || isProcessing) return;

                const modelId = modelSelect.value;
                const agentName = agentNameInput.value;
                const sessionId = sessionIdInput.value;

                // 添加用户消息到聊天框
                addMessage('user', message);
                messageInput.value = '';

                // 添加助手消息占位符
                addMessage('assistant', '');

                isProcessing = true;
                sendBtn.disabled = true;
                messageInput.disabled = true;

                // 发送到服务器
                ws.send(JSON.stringify({
                    type: 'message',
                    content: message,
                    model_id: modelId,
                    agent_name: agentName,
                    session_id: sessionId,
                    user_id: 'user'
                }));
            }

            function addMessage(role, content) {
                const div = document.createElement('div');
                div.className = 'message ' + role;
                div.id = 'msg-' + Date.now();
                div.textContent = role === 'user' ? '👤 ' + content : (role === 'assistant' ? '🤖 ' : '⚡ ') + content;
                chatBox.appendChild(div);
                chatBox.scrollTop = chatBox.scrollHeight;
            }

            function appendToLastMessage(content) {
                const lastMsg = chatBox.lastChild;
                if (lastMsg && lastMsg.className.includes('assistant')) {
                    lastMsg.textContent += content;
                    chatBox.scrollTop = chatBox.scrollHeight;
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@agent_app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket 端点用于实时对话"""
    await manager.connect(websocket, client_id)

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") != "message":
                continue

            user_message = message_data.get("content", "")
            model_id = message_data.get("model_id", "doubao_auto")
            agent_name = message_data.get("agent_name", "assistant")
            session_id = message_data.get("session_id", "default")
            user_id = message_data.get("user_id", "user")

            # 通知客户端开始新会话
            await manager.send_message(client_id, {
                "type": "session_start",
                "session_id": session_id
            })

            # 创建请求对象
            agent_request = AgentRequest(
                session_id=session_id,
                user_id=user_id,
                # 可以添加更多字段
            )

            try:
                # 调用 query_func 并流式返回结果
                async for msg, last in query_func(
                    self=None,
                    msgs=[Msg(name=user_id, content=user_message, role="user")],
                    request=agent_request,
                    agent_name=agent_name,
                    model_id=model_id,
                ):
                    if hasattr(msg, 'content'):
                        await manager.send_message(client_id, {
                            "type": "chunk",
                            "content": msg.content
                        })

                    if last:
                        await manager.send_message(client_id, {
                            "type": "done"
                        })

            except Exception as e:
                await manager.send_message(client_id, {
                    "type": "error",
                    "content": str(e)
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        print(f"Client {client_id} disconnected")


# API 端点（非流式）
@agent_app.post("/api/chat")
async def api_chat(request: MessageRequest):
    """非流式聊天 API"""
    global _bot_flow

    if not _bot_flow:
        return {"error": "Service not initialized"}

    try:
        agent = _bot_flow.create_agent(
            name=request.agent_name,
            system_prompt="你是一个有用的智能助手",
            model_id=request.model_id
        )

        user_msg = Msg(
            name=request.user_id,
            content=request.message,
            role="user",
        )

        reply = await agent([user_msg])

        return MessageResponse(
            response=reply.content if hasattr(reply, 'content') else str(reply),
            agent_name=request.agent_name,
            session_id=request.session_id
        )
    except Exception as e:
        return {"error": str(e)}


# 健康检查端点
@agent_app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "bot_flow_initialized": _bot_flow is not None
    }


if __name__ == "__main__":
    agent_app.run(host="0.0.0.0", port=8000)
