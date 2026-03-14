from pathlib import Path
import json
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
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


class MessageRequest(BaseModel):
    message: str
    agent_name: str = "assistant"
    model_id: str = "doubao_auto"
    session_id: str = "default"
    user_id: str = "user"


class MessageResponse(BaseModel):
    response: str
    agent_name: str
    session_id: str


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


class BotFlow:
    def __init__(self, homespace: str | Path = "~/.openbot/"):
        self.homespace = Path(homespace).expanduser()
        self.ensure_homespace()

        config_manager = ConfigManager(self.homespace / "config/config.json")
        self.config = config_manager.config

        self.model_manager = ModelManager(self.config.model_configs)
        self.toolkit_manager = ToolKitManager()

        self._initialized = False
        self.connection_manager = ConnectionManager()

        # 创建 AgentApp 实例
        self._app = AgentApp(
            app_name="OpenBot Gateway",
            app_description="基于 AgentScope Runtime 的多智能体 WebUI 服务",
            lifespan=self.lifespan,
        )

        # 注册路由
        self._register_routes()

    @property
    def app(self) -> AgentApp:
        return self._app

    @property
    def toolkit(self):
        return self.toolkit_manager._toolkit

    def ensure_homespace(self):
        """Ensure the homespace exists"""
        if not self.homespace.exists():
            self.homespace.mkdir(parents=True, exist_ok=True)

        for subdir in ["config", "skills", "memory", "rules", "resources"]:
            (self.homespace / subdir).mkdir(parents=True, exist_ok=True)

        if not (self.homespace / "config/config.json").exists():
            default_config = BotFlowConfig()
            with open(self.homespace / "config/config.json", "w") as f:
                f.write(default_config.model_dump_json(indent=4))

    async def initialize(self):
        """Async initialization to register skill directories"""
        if self._initialized:
            return

        self.toolkit_manager.register_buildin_tools()
        self.toolkit_manager.register_db_tools()

        try:
            with open(self.config.mcp_config_path, "r") as f:
                mcp_config = json.load(f)
                self.toolkit_manager.register_mcp_tools(mcp_config)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

        await self.toolkit_manager.register_skill_dir(self.homespace / "skills")

        self._initialized = True

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """Async lifespan to initialize resources"""
        await self.initialize()
        try:
            yield
        finally:
            if hasattr(self.model_manager, "cleanup"):
                self.model_manager.cleanup()
            if hasattr(self.toolkit_manager, "cleanup"):
                self.toolkit_manager.cleanup()

    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """处理查询请求的核心逻辑"""
        if not self._initialized:
            raise RuntimeError("BotFlow not initialized")

        if isinstance(msgs, list) and len(msgs) > 0:
            user_message = (
                msgs[-1].content if hasattr(msgs[-1], "content") else str(msgs[-1])
            )
        else:
            user_message = str(msgs)

        agent_name = kwargs.get(
            "agent_name",
            getattr(request, "agent_name", "assistant") if request else "assistant",
        )
        model_id = kwargs.get(
            "model_id",
            getattr(request, "model_id", "doubao_auto") if request else "doubao_auto",
        )
        session_id = getattr(request, "session_id", "default") if request else "default"
        user_id = getattr(request, "user_id", "user") if request else "user"

        print(f"[query_func] Received message: {user_message}")
        print(
            f"[query_func] Agent: {agent_name}, Model: {model_id}, Session: {session_id}"
        )

        try:
            agent = self.create_agent(
                name=agent_name,
                system_prompt="你是一个有用的智能助手",
                model_id=model_id,
            )

            user_msg = Msg(name=user_id, content=user_message, role="user")

            async for msg, last in stream_printing_messages(
                agents=[agent],
                coroutine_task=agent([user_msg]),
            ):
                yield msg, last

        except Exception as e:
            print(f"[query_func] Error: {str(e)}")
            raise

    def _get_webui_html(self) -> str:
        return """<!DOCTYPE html>
<html>
<head>
    <title>OpenBot Gateway</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .chat-box { height: 400px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px; padding: 10px; margin-bottom: 10px; background: #fafafa; }
        .message { margin: 10px 0; padding: 10px; border-radius: 5px; }
        .user { background: #e3f2fd; text-align: right; }
        .assistant { background: #f1f1f1; }
        input, select, button { padding: 10px; margin: 5px; border: 1px solid #ddd; border-radius: 5px; }
        input[type="text"] { flex: 1; }
        .controls { display: flex; gap: 10px; margin-bottom: 10px; }
        button { background: #007bff; color: white; border: none; cursor: pointer; }
        button:hover { background: #0056b3; }
        button:disabled { background: #ccc; cursor: not-allowed; }
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
        ws.onopen = () => { addMessage('system', '已连接到服务器'); };
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'chunk') { appendToLastMessage(data.content); }
            else if (data.type === 'done') { isProcessing = false; sendBtn.disabled = false; messageInput.disabled = false; }
            else if (data.type === 'error') { addMessage('system', '错误: ' + data.content); isProcessing = false; sendBtn.disabled = false; messageInput.disabled = false; }
            else if (data.type === 'session_start') { currentSessionId = data.session_id; sessionIdInput.value = currentSessionId; }
        };
        ws.onclose = () => { addMessage('system', '连接已关闭'); };
        function handleKeyPress(event) { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); } }
        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message || isProcessing) return;
            const modelId = modelSelect.value;
            const agentName = agentNameInput.value;
            const sessionId = sessionIdInput.value;
            addMessage('user', message);
            messageInput.value = '';
            addMessage('assistant', '');
            isProcessing = true;
            sendBtn.disabled = true;
            messageInput.disabled = true;
            ws.send(JSON.stringify({ type: 'message', content: message, model_id: modelId, agent_name: agentName, session_id: sessionId, user_id: 'user' }));
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
            if (lastMsg && lastMsg.className.includes('assistant')) { lastMsg.textContent += content; chatBox.scrollTop = chatBox.scrollHeight; }
        }
    </script>
</body>
</html>"""

    def _register_routes(self):
        """注册所有路由"""
        app = self._app

        @app.get("/webui")
        async def webui_root(request: Request):
            return HTMLResponse(content=self._get_webui_html())

        @app.websocket("/ws/{client_id}")
        async def websocket_endpoint(websocket: WebSocket, client_id: str):
            await self.connection_manager.connect(websocket, client_id)
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

                    await self.connection_manager.send_message(
                        client_id, {"type": "session_start", "session_id": session_id}
                    )

                    agent_request = AgentRequest(session_id=session_id, user_id=user_id)

                    try:
                        async for msg, last in self.query_func(
                            msgs=[Msg(name=user_id, content=user_message, role="user")],
                            request=agent_request,
                            agent_name=agent_name,
                            model_id=model_id,
                        ):
                            if hasattr(msg, "content"):
                                await self.connection_manager.send_message(
                                    client_id, {"type": "chunk", "content": msg.content}
                                )
                            if last:
                                await self.connection_manager.send_message(
                                    client_id, {"type": "done"}
                                )
                    except Exception as e:
                        await self.connection_manager.send_message(
                            client_id, {"type": "error", "content": str(e)}
                        )

            except WebSocketDisconnect:
                self.connection_manager.disconnect(client_id)

        @app.post("/process")
        async def process_endpoint(
            request: AgentRequest,
            message: str = None,
            agent_name: str = "assistant",
            model_id: str = "doubao_auto",
        ):
            if not self._initialized:
                return {"error": "Service not initialized"}

            try:
                if message:
                    user_message = message
                elif hasattr(request, "input") and request.input:
                    if isinstance(request.input, list) and len(request.input) > 0:
                        last_msg = request.input[-1]
                        if hasattr(last_msg, "content"):
                            user_message = last_msg.content
                        elif isinstance(last_msg, dict):
                            user_message = last_msg.get("content", str(last_msg))
                        else:
                            user_message = str(last_msg)
                    else:
                        user_message = str(request.input)
                else:
                    return {"error": "No message provided"}

                agent_name_to_use = getattr(request, "agent_name", agent_name)
                model_id_to_use = getattr(request, "model_id", model_id)
                session_id = getattr(request, "session_id", "default")
                user_id = getattr(request, "user_id", "user")

                agent = self.create_agent(
                    name=agent_name_to_use,
                    system_prompt="你是一个有用的智能助手",
                    model_id=model_id_to_use,
                )

                user_msg = Msg(name=user_id, content=user_message, role="user")
                reply = await agent([user_msg])

                response_content = (
                    reply.content if hasattr(reply, "content") else str(reply)
                )

                return {
                    "status": "completed",
                    "response": {
                        "content": response_content,
                        "agent_name": agent_name_to_use,
                        "session_id": session_id,
                    },
                }

            except Exception as e:
                return {"status": "error", "error": str(e)}

        @app.post("/process/stream")
        async def process_stream_endpoint(
            request: AgentRequest,
            message: str = None,
            agent_name: str = "assistant",
            model_id: str = "doubao_auto",
        ):
            if not self._initialized:
                yield 'data: {"status":"error","error":"Service not initialized"}\n\n'
                return

            try:
                if message:
                    user_message = message
                elif hasattr(request, "input") and request.input:
                    if isinstance(request.input, list) and len(request.input) > 0:
                        last_msg = request.input[-1]
                        if hasattr(last_msg, "content"):
                            user_message = last_msg.content
                        elif isinstance(last_msg, dict):
                            user_message = last_msg.get("content", str(last_msg))
                        else:
                            user_message = str(last_msg)
                    else:
                        user_message = str(request.input)
                else:
                    yield 'data: {"status":"error","error":"No message provided"}\n\n'
                    return

                agent_name_to_use = getattr(request, "agent_name", agent_name)
                model_id_to_use = getattr(request, "model_id", model_id)
                session_id = getattr(request, "session_id", "default")
                user_id = getattr(request, "user_id", "user")

                agent = self.create_agent(
                    name=agent_name_to_use,
                    system_prompt="你是一个有用的智能助手",
                    model_id=model_id_to_use,
                )

                user_msg = Msg(name=user_id, content=user_message, role="user")

                yield f'data: {{"status":"processing","session_id":"{session_id}"}}\n\n'

                async for msg, last in stream_printing_messages(
                    agents=[agent],
                    coroutine_task=agent([user_msg]),
                ):
                    if hasattr(msg, "content"):
                        yield f'data: {{"status":"in_progress","content":"{msg.content}"}}\n\n'

                    if last:
                        yield f'data: {{"status":"completed","agent_name":"{agent_name_to_use}","session_id":"{session_id}"}}\n\n'

            except Exception as e:
                yield f'data: {{"status":"error","error":"{str(e)}"}}\n\n'

        @app.get("/health")
        async def health_check():
            return {"status": "healthy", "service": "AgentScope Runtime"}

    async def run(self, host: str = "0.0.0.0", port: int = 8000):
        """启动服务"""
        await self._app.run(host=host, port=port)

    def create_agent(
        self,
        name: str,
        system_prompt: str,
        model_id: str,
        max_iters: int = 100,
        verbose: bool = False,
        stream: bool = True,
    ) -> ReActAgent:
        model, formatter = self.model_manager.build_chatmodel(model_id)
        return ReActAgent(
            name=name,
            model=model,
            sys_prompt=system_prompt,
            toolkit=self.toolkit_manager._toolkit,
            memory=InMemoryMemory(),
            formatter=formatter,
            max_iters=max_iters,
            print_hint_msg=False,
        )


if __name__ == "__main__":
    from agentscope.message import Msg

    async def main():
        bot_flow = BotFlow("E:\\src\\openbot\\.openbot")
        await bot_flow.initialize()
        agent = bot_flow.create_agent("test_agent", "你是一个智能助手", "doubao_auto")
        while True:
            user_input = input("用户: ")
            if user_input.lower() in ["exit", "quit"]:
                break
            msg = Msg(name="user", content=user_input, role="user")
            reply = await agent.reply([msg])
            print(reply)

    import asyncio

    asyncio.run(main())
