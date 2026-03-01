"""飞书通道"""

import logging
import json
import time
import hmac
import hashlib
import asyncio
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, Response
import httpx
import websockets
from openbot.channels.base import Channel
from openbot.common.config import ChannelConfig
from openbot.common.datamodel import Question, Answer, ContentType
from openbot.agents.core import OpenBotAgent


class FeishuChannel(Channel):
    """飞书通道"""

    def __init__(self, config: ChannelConfig, agent: OpenBotAgent):
        super().__init__(config)
        self.agent = agent
        self.app_id = self.params.get("app_id", "")
        self.app_secret = self.params.get("app_secret", "")
        self.verification_token = self.params.get("verification_token", "")
        self.encrypt_key = self.params.get("encrypt_key", "")
        self.access_token = ""
        self.token_expire_time = 0
        self.ws = None
        self.ws_task = None
        self.running = False

    async def start(self):
        """启动通道"""
        if not self.enabled:
            return

        # 检查配置是否完整
        if not self.app_id or not self.app_secret:
            logging.warning("飞书通道配置不完整，跳过启动")
            return

        # 获取访问令牌
        await self._get_access_token()

        # 启动WebSocket长连接
        self.running = True
        self.ws_task = asyncio.create_task(self._run_websocket())

        logging.info(f"飞书通道已启动，路径: {self.path}")

    async def stop(self):
        """停止通道"""
        if not self.enabled:
            return

        self.running = False
        if self.ws_task:
            self.ws_task.cancel()
        if self.ws:
            await self.ws.close()

        logging.info("飞书通道已停止")

    async def _get_access_token(self):
        """获取访问令牌"""
        try:
            url = (
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            )
            headers = {"Content-Type": "application/json"}
            data = {"app_id": self.app_id, "app_secret": self.app_secret}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data)
                result = response.json()

            if result.get("code") == 0:
                self.access_token = result.get("tenant_access_token")
                self.token_expire_time = time.time() + result.get("expire", 3600)
                logging.info("获取飞书访问令牌成功")
            else:
                logging.error(f"获取飞书访问令牌失败: {result.get('msg')}")
        except Exception as e:
            logging.error(f"获取飞书访问令牌出错: {e}", exc_info=True)

    async def _refresh_access_token(self):
        """刷新访问令牌"""
        if time.time() >= self.token_expire_time - 300:  # 提前5分钟刷新
            await self._get_access_token()

    async def _get_websocket_url(self):
        """获取WebSocket连接地址"""
        try:
            url = "https://open.feishu.cn/open-apis/im/v1/ws/badge"
            headers = {"Authorization": "Bearer {}".format(self.access_token)}

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                result = response.json()

            if result.get("code") == 0:
                return result.get("data", {}).get("wss_url")
            else:
                logging.error(f"获取WebSocket连接地址失败: {result.get('msg')}")
                return None
        except Exception as e:
            logging.error(f"获取WebSocket连接地址出错: {e}", exc_info=True)
            return None

    async def _run_websocket(self):
        """运行WebSocket长连接"""
        while self.running:
            try:
                # 刷新访问令牌
                await self._refresh_access_token()

                # 获取WebSocket连接地址
                ws_url = await self._get_websocket_url()
                if not ws_url:
                    await asyncio.sleep(5)
                    continue

                # 建立WebSocket连接
                logging.info(f"正在连接飞书WebSocket: {ws_url}")
                async with websockets.connect(ws_url) as self.ws:
                    logging.info("飞书WebSocket连接成功")

                    # 发送ping消息保持连接
                    ping_task = asyncio.create_task(self._send_ping())

                    # 接收和处理消息
                    async for message in self.ws:
                        await self._handle_websocket_message(message)

                    # 取消ping任务
                    ping_task.cancel()

            except websockets.exceptions.WebSocketException as e:
                logging.error(f"WebSocket连接出错: {e}")
            except Exception as e:
                logging.error(f"WebSocket运行出错: {e}", exc_info=True)
            finally:
                self.ws = None
                if self.running:
                    logging.info("正在重连飞书WebSocket...")
                    await asyncio.sleep(5)

    async def _send_ping(self):
        """发送ping消息保持连接"""
        while self.running and self.ws:
            try:
                await self.ws.send(json.dumps({"type": "ping"}))
                await asyncio.sleep(30)
            except Exception as e:
                logging.error(f"发送ping消息出错: {e}")
                break

    async def _handle_websocket_message(self, message: str):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "event":
                # 处理事件消息
                event = data.get("event")
                event_type = event.get("header", {}).get("event_type")

                if event_type == "im.message.receive_v1":
                    message_data = event.get("event", {})
                    message_type = message_data.get("message", {}).get("message_type")
                    chat_type = message_data.get("message", {}).get("chat_type")

                    if chat_type == "p2p" and message_type == "text":
                        content = json.loads(
                            message_data.get("message", {}).get("content", "{}")
                        ).get("text", "")
                        user_id = (
                            message_data.get("sender", {})
                            .get("sender_id", {})
                            .get("open_id")
                        )
                        message_id = message_data.get("message", {}).get("message_id")

                        # 处理消息
                        answer = await self.handle_message(
                            {
                                "message_id": message_id,
                                "user_id": user_id,
                                "content": content,
                                "chat_type": chat_type,
                            }
                        )

                        # 回复消息
                        if answer:
                            await self.reply_message(message_id, answer.content)
            elif msg_type == "pong":
                # 处理pong消息
                pass
            elif msg_type == "error":
                # 处理错误消息
                logging.error(f"WebSocket错误: {data.get('message')}")
        except Exception as e:
            logging.error(f"处理WebSocket消息出错: {e}", exc_info=True)

    async def handle_message(self, message: Dict[str, Any]) -> Optional[Answer]:
        """处理消息

        Args:
            message: 消息内容

        Returns:
            回答内容
        """
        try:
            content = message.get("content", "")
            user_id = message.get("user_id", "")
            message_id = message.get("message_id", "")

            # 创建问题对象
            question = Question(
                content=content,
                content_type=ContentType.TEXT,
                user_id=user_id,
                channel_id=self.name,
                metadata={"message_id": message_id},
            )

            # 调用智能体处理问题
            answer_future = await self.agent.ask(question)
            answer = await answer_future.result()

            return answer
        except Exception as e:
            logging.error(f"处理飞书消息出错: {e}", exc_info=True)
            return None

    async def reply_message(self, message_id: str, content: str):
        """回复消息

        Args:
            message_id: 消息ID
            content: 回复内容
        """
        try:
            # 刷新访问令牌
            await self._refresh_access_token()

            url = "https://open.feishu.cn/open-apis/im/v1/messages/{}/reply".format(
                message_id
            )
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            }
            data = {"content": json.dumps({"text": content}), "msg_type": "text"}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data)
                result = response.json()

            if result.get("code") == 0:
                logging.info(f"回复飞书消息成功: {message_id}")
            else:
                logging.error(f"回复飞书消息失败: {result.get('msg')}")
        except Exception as e:
            logging.error(f"回复飞书消息出错: {e}", exc_info=True)

    def _verify_signature(self, headers, body):
        """验证签名

        Args:
            headers: 请求头
            body: 请求体

        Returns:
            bool: 是否验证通过
        """
        try:
            timestamp = headers.get("X-Lark-Request-Timestamp")
            nonce = headers.get("X-Lark-Request-Nonce")
            signature = headers.get("X-Lark-Signature")

            if not timestamp or not nonce or not signature:
                return False

            # 构建签名字符串
            signature_string = timestamp + nonce + body.decode("utf-8")

            # 计算签名
            h = hmac.new(
                self.verification_token.encode("utf-8"),
                signature_string.encode("utf-8"),
                hashlib.sha256,
            )
            expected_signature = h.hexdigest()

            return signature == expected_signature
        except Exception as e:
            logging.error(f"验证签名出错: {e}", exc_info=True)
            return False

    def get_webhook_handler(self):
        """获取Webhook处理器

        Returns:
            Webhook处理器函数
        """

        async def webhook_handler(request: Request):
            try:
                body = await request.body()
                headers = dict(request.headers)

                # 验证签名
                if not self._verify_signature(headers, body):
                    raise HTTPException(status_code=401, detail="Invalid signature")

                # 解析消息
                event = json.loads(body.decode("utf-8"))

                # 处理消息事件
                if event.get("header", {}).get("event_type") == "im.message.receive_v1":
                    message = event.get("event", {})
                    message_type = message.get("message", {}).get("message_type")
                    chat_type = message.get("message", {}).get("chat_type")

                    if chat_type == "p2p" and message_type == "text":
                        content = json.loads(
                            message.get("message", {}).get("content", "{}")
                        ).get("text", "")
                        user_id = (
                            message.get("sender", {})
                            .get("sender_id", {})
                            .get("open_id")
                        )
                        message_id = message.get("message", {}).get("message_id")

                        # 处理消息
                        answer = await self.handle_message(
                            {
                                "message_id": message_id,
                                "user_id": user_id,
                                "content": content,
                                "chat_type": chat_type,
                            }
                        )

                        # 回复消息
                        if answer:
                            await self.reply_message(message_id, answer.content)

                # 返回成功响应
                return Response(
                    content=json.dumps({"code": 0, "msg": "success"}),
                    media_type="application/json",
                )
            except Exception as e:
                logging.error(f"处理飞书Webhook出错: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")

        return webhook_handler
