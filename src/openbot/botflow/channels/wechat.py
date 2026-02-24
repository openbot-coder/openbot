"""微信公众号通道实现"""

import logging
import hashlib
from typing import Optional
from xml.etree import ElementTree as ET

from fastapi import Request, Response

from .base import ChatChannel
from ..database import ChatMessage


logger = logging.getLogger(__name__)


class WeChatChannel(ChatChannel):
    """微信公众号通道"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        token: str,
        path: str = "/wechat"
    ):
        super().__init__(name="wechat")
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = token
        self.path = path
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    async def start(self) -> None:
        """启动微信通道"""
        self._running = True
        logger.info(f"WeChat channel started at {self.path}")

    async def stop(self) -> None:
        """停止微信通道"""
        self._running = False
        logger.info("WeChat channel stopped")

    async def send(self, message: ChatMessage) -> None:
        """发送消息（通过客服接口）"""
        logger.info(f"Send to {message.channel_id}: {message.content}")

    async def handle_verify(self, request: Request) -> Response:
        """处理微信服务器验证"""
        params = dict(request.query_params)
        signature = params.get("signature", "")
        timestamp = params.get("timestamp", "")
        nonce = params.get("nonce", "")
        echostr = params.get("echostr", "")

        if self._verify_signature(signature, timestamp, nonce):
            return Response(content=echostr, media_type="text/plain")
        return Response(content="Invalid signature", status_code=403)

    async def handle_message(self, request: Request) -> Response:
        """处理微信消息"""
        try:
            body = await request.body()
            xml_data = ET.fromstring(body)

            msg_type = xml_data.find("MsgType")
            if msg_type is None:
                return Response(content="success", media_type="text/plain")

            msg_type = msg_type.text
            from_user = xml_data.find("FromUserName")
            to_user = xml_data.find("ToUserName")
            content = xml_data.find("Content")

            if from_user is None or to_user is None:
                return Response(content="success", media_type="text/plain")

            from_user_id = from_user.text

            if msg_type == "text" and content is not None:
                text_content = content.text or ""
                msg = ChatMessage(
                    channel_id=f"wechat:{from_user_id}",
                    content=text_content,
                    role="user"
                )
                await self.on_receive(msg)

            return Response(content="success", media_type="text/plain")

        except Exception as e:
            logger.error(f"Error handling WeChat message: {e}")
            return Response(content="success", media_type="text/plain")

    def _verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        """验证微信签名"""
        if not all([self.token, timestamp, nonce]):
            return False

        tmp_list = [self.token, timestamp, nonce]
        tmp_list.sort()
        tmp_str = "".join(tmp_list)

        hashcode = hashlib.sha1(tmp_str.encode()).hexdigest()
        return hashcode == signature
