"""微信聊天通道"""

import asyncio
import json
import logging
from typing import Optional, Callable, Any
from fastapi import FastAPI, HTTPException, Request, APIRouter
from fastapi.responses import Response
from openbot.botflow.channels.base import ChatChannel, ChatMessage, ContentType
from openbot.botflow.channels.wechat.utils import (
    WXBizJsonMsgCrypt,
    make_text_stream,
    encrypt_message,
)


class WeChatBotChatChannel(ChatChannel):
    """微信聊天通道抽象基类"""

    def __init__(self, s_token: str, s_encoding_aes_key: str) -> None:
        self._name = "wechat"
        self._message_handler: Optional[Callable] = None
        self._running = False
        self._token = s_token
        self._encoding_aes_key = s_encoding_aes_key
        self._router = self._init_router()
        self._stream_queue = asyncio.Queue()
        self._prefix = ""

    @property
    def channel_id(self) -> str:
        """通道ID"""
        return f"Channel[{self._name}]@{self._prefix}"

    def _init_router(self) -> APIRouter:
        """初始化路由"""
        router = APIRouter()

        @router.get("/")
        async def verify_url(
            request: Request,
            msg_signature: str,
            timestamp: str,
            nonce: str,
            echostr: str,
        ):
            return await self._verify_url(
                request, msg_signature, timestamp, nonce, echostr
            )

        @router.post("/")
        async def handle_message(
            request: Request, msg_signature: str, timestamp: str, nonce: str
        ):
            return await self._handle_message(request, msg_signature, timestamp, nonce)

        print(router.routes)
        return router

    def install_router(self, fastapi_app: FastAPI, prefix: str = "/wechat") -> None:
        """安装路由"""
        self._prefix = prefix
        fastapi_app.include_router(self._router, prefix=self._prefix)
        print(fastapi_app.routes)

    async def _verify_url(
        self,
        request: Request,
        msg_signature: str,
        timestamp: str,
        nonce: str,
        echostr: str,
    ) -> Response:
        """处理验证 URL 请求"""
        # 企业创建的自能机器人的 VerifyUrl 请求, receiveid 是空串

        print(
            f"_verify_url called with: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}, echostr={echostr}"
        )

        # 检查参数是否存在
        if not all([msg_signature, timestamp, nonce, echostr]):
            print("Missing parameters")
            return Response(
                content="Missing parameters", status_code=400, media_type="text/plain"
            )

        try:
            wxcpt = WXBizJsonMsgCrypt(self._token, self._encoding_aes_key, "")
            ret, echostr = wxcpt.verify_url(msg_signature, timestamp, nonce, echostr)

            if ret != 0:
                print(f"Verification failed with code: {ret}")
                echostr = "verify fail"
            else:
                print("Verification successful")
        except Exception as e:
            print(f"Error during verification: {e}")
            return Response(
                content="Error during verification",
                status_code=500,
                media_type="text/plain",
            )

        return Response(content=echostr, media_type="text/plain")

    async def _handle_message(
        self, request: Request, msg_signature: str, timestamp: str, nonce: str
    ) -> None:
        """处理消息请求"""

        wxcpt = WXBizJsonMsgCrypt(self._token, self._encoding_aes_key, "")
        if not all([msg_signature, timestamp, nonce]):
            raise HTTPException(status_code=400, detail="缺少必要参数")

        post_data = await request.body()

        ret, msg = wxcpt.decrypt_msg(post_data, msg_signature, timestamp, nonce)
        if ret != 0:
            raise HTTPException(status_code=400, detail="解密失败")

        chatmessage = self._parser_wxmsg(msg)
        if chatmessage.content_type == ContentType.STREAM:
            try:
                # 从队列中获取回复消息
                reply_message = await asyncio.wait_for(
                    self._stream_queue.get(), timeout=5.0
                )  # 增加超时时间
                stream_id = reply_message.metadata.get(
                    "stream_id", chatmessage.metadata.get("stream_id", "")
                )
                finish = reply_message.metadata.get("finish", False)
                content = reply_message.content
                print(
                    f"Got reply message: stream_id={stream_id}, finish={finish}, content={content}"
                )
            except asyncio.TimeoutError:
                stream_id = chatmessage.metadata.get("stream_id", "")
                content = "Sorry, I'm having trouble processing your request. Please try again later."
                finish = True
                print(f"Timeout waiting for reply message, stream_id={stream_id}")
            stream = make_text_stream(stream_id, content, finish)
            resp = self._encrypt_message("", nonce, timestamp, stream)
            return Response(content=resp, media_type="text/plain")

        elif chatmessage.content_type == ContentType.TEXT:
            stream_id = chatmessage.msg_id
            finish = False
            stream = make_text_stream(stream_id, chatmessage.content, finish)
            resp = self._encrypt_message("", nonce, timestamp, stream)
            return Response(content=resp, media_type="text/plain")

    def _parser_wxmsg(self, msg: str) -> ChatMessage:
        """解析微信消息"""
        data = json.loads(msg)
        if "msgtype" not in data:
            raise HTTPException(status_code=400, detail="unknown msgtype")

        if data["msgtype"] == "stream":
            return ChatMessage(
                channel_id=self.channel_id,
                content=data["stream"]["id"],
                role="user",
                content_type=ContentType.STREAM,
                metadata={
                    "stream_id": data["stream"]["id"],
                    "finish": False,
                },
            )
        msg = ChatMessage(
            channel_id=self.channel_id,
            content=data["text"]["content"],
            role="user",
            content_type=data["msgtype"],
        )
        return msg

    def _encrypt_message(self, receiveid, nonce, timestamp, stream) -> dict:

        wxcpt = WXBizJsonMsgCrypt(self._token, self._encoding_aes_key, receiveid)
        ret, resp = wxcpt.encrypt_msg(stream, nonce, timestamp)
        if ret != 0:
            logging.error("加密失败，错误码: %d", ret)
            return

        stream_id = json.loads(stream)["stream"]["id"]
        finish = json.loads(stream)["stream"]["finish"]
        logging.info(
            "回调处理完成, 返回加密的流消息, stream_id=%s, finish=%s", stream_id, finish
        )
        logging.debug("加密后的消息: %s", resp)

        return resp

    def set_message_handler(self, handler: Callable[[ChatMessage], Any]):
        """设置消息处理器"""
        self._message_handler = handler

    async def start(self) -> None:
        """启动通道"""
        self._running = True

    async def stop(self) -> None:
        """停止通道"""
        self._running = False

    async def send(self, message: ChatMessage) -> None:
        """发送消息"""
        # 直接将消息放入队列，不需要解析
        # 确保消息包含必要的字段
        if "stream_id" not in message.metadata:
            message.metadata["stream_id"] = message.msg_id
        if "finish" not in message.metadata:
            message.metadata["finish"] = False
        self._stream_queue.put_nowait(message)

    async def on_receive(self, message: ChatMessage) -> None:
        """接收消息回调"""
        if self._message_handler:
            await self._message_handler(message)


if __name__ == "__main__":
    import uvicorn

    # app = FastAPI(debug=True,)
    TOKEN = "HTvuP"
    ENCODING_AES_KEY = "pQfseXJ7XLEc9jFyF6aa826CN8Qwuirr8fdh5I89LsT"
    channel = WeChatBotChatChannel(TOKEN, ENCODING_AES_KEY)
    # channel.install_router(app)

    uvicorn.run(channel._router, host="0.0.0.0", port=8000)
