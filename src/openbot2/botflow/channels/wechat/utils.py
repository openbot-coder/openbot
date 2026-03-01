#!/usr/bin/env python
# -*- encoding:utf-8 -*-

"""对企业微信发送给企业后台的消息加解密示例代码.
@copyright: Copyright (c) 1998-2020 Tencent Inc.
"""

import base64
import hashlib
import json
import logging
import random
import socket
import string
import struct
import sys
import time
from enum import IntEnum
from Crypto.Cipher import AES

"""
关于Crypto.Cipher模块，ImportError: No module named 'Crypto'解决方案
请到官方网站 https://www.dlitz.net/software/pycrypto/ 下载pycrypto。
下载后，按照README中的"Installation"小节的提示进行pycrypto安装。

pip install pycryptodome
"""


class WXBizMsgCryptCode(IntEnum):
    """企业微信消息加密密状态码"""

    OK = 0
    VALIDATESIGNATURE_ERROR = -40001
    PARSEJSON_ERROR = -40002
    COMPUTESIGNATURE_ERROR = -40003
    ILLEGALAESKEY_ERROR = -40004
    VALIDATECORPID_ERROR = -40005
    ENCRYPTAES_ERROR = -40006
    DECRYPTAESAES_ERROR = -40007
    ILLEGALBUFFER_ERROR = -40008
    DECODEBASE64_ERROR = -40009
    ENCODEBASE64_ERROR = -40010
    GENRETURNJSON_ERROR = -40011


class FormatException(Exception):
    pass


def throw_exception(message, exception_class=FormatException):
    """my define raise exception function"""
    raise exception_class(message)


class SHA1:
    """计算企业微信的消息签名接口"""

    def get_sha1(self, token, timestamp, nonce, encrypt):
        """用SHA1算法生成安全签名

        @param token:  票据
        @param timestamp: 时间戳
        @param encrypt: 密文
        @param nonce: 随机字符串
        @return: 安全签名
        """
        try:
            # 确保所有输入都是字符串类型
            if isinstance(encrypt, bytes):
                encrypt = encrypt.decode("utf-8")

            sortlist = [str(token), str(timestamp), str(nonce), str(encrypt)]
            sortlist.sort()
            sha = hashlib.sha1()
            sha.update("".join(sortlist).encode("utf-8"))
            return WXBizMsgCryptCode.OK, sha.hexdigest()

        except Exception as e:
            logging.error(f"SHA1 get_sha1 error: {e}")
            return WXBizMsgCryptCode.COMPUTESIGNATURE_ERROR, None


class JsonParse:
    """提供提取消息格式中的密文及生成回复消息格式的接口"""

    # json消息模板
    AES_TEXT_RESPONSE_TEMPLATE = """{
        "encrypt": "%(msg_encrypt)s",
        "msgsignature": "%(msg_signaturet)s",
        "timestamp": "%(timestamp)s",
        "nonce": "%(nonce)s"
    }"""

    def extract(self, jsontext):
        """提取出json数据包中的加密消息

        @param jsontext: 待提取的json字符串
        @return: 提取出的加密消息字符串
        """
        try:
            json_dict = json.loads(jsontext)
            return WXBizMsgCryptCode.OK, json_dict["encrypt"]
        except Exception as e:
            logging.error(f"JsonParse extract error: {e}")
            return WXBizMsgCryptCode.PARSEJSON_ERROR, None

    def generate(self, encrypt, signature, timestamp, nonce):
        """生成json消息

        @param encrypt: 加密后的消息密文
        @param signature: 安全签名
        @param timestamp: 时间戳
        @param nonce: 随机字符串
        @return: 生成的json字符串
        """
        resp_dict = {
            "msg_encrypt": encrypt,
            "msg_signaturet": signature,
            "timestamp": timestamp,
            "nonce": nonce,
        }
        resp_json = self.AES_TEXT_RESPONSE_TEMPLATE % resp_dict
        return resp_json


class PKCS7Encoder:
    """提供基于PKCS7算法的加解密接口"""

    block_size = 32

    def encode(self, text):
        """对需要加密的明文进行填充补位

        @param text: 需要进行填充补位操作的明文(bytes类型)
        @return: 补齐明文字符串(bytes类型)
        """
        text_length = len(text)
        # 计算需要填充的位数
        amount_to_pad = self.block_size - (text_length % self.block_size)
        if amount_to_pad == 0:
            amount_to_pad = self.block_size
        # 获得补位所用的字符
        pad = bytes([amount_to_pad])
        # 确保text是bytes类型
        if isinstance(text, str):
            text = text.encode("utf-8")
        return text + pad * amount_to_pad

    def decode(self, decrypted):
        """删除解密后明文的补位字符

        @param decrypted: 解密后的明文
        @return: 删除补位字符后的明文
        """
        pad = ord(decrypted[-1])
        if pad < 1 or pad > 32:
            pad = 0
        return decrypted[:-pad]


class Prpcrypt(object):
    """提供接收和推送给企业微信消息的加解密接口"""

    def __init__(self, key):
        # self.key = base64.b64decode(key+"=")
        self.key = key
        # 设置加解密模式为AES的CBC模式
        self.mode = AES.MODE_CBC

    def encrypt(self, text, receiveid):
        """对明文进行加密

        @param text: 需要加密的明文
        @return: 加密得到的字符串
        """
        # 16位随机字符串添加到明文开头
        text = text.encode()
        text = (
            self.get_random_str()
            + struct.pack("I", socket.htonl(len(text)))
            + text
            + receiveid.encode()
        )

        # 使用自定义的填充方式对明文进行补位填充
        pkcs7 = PKCS7Encoder()
        text = pkcs7.encode(text)
        # 加密
        cryptor = AES.new(self.key, self.mode, self.key[:16])
        try:
            ciphertext = cryptor.encrypt(text)
            # 使用BASE64对加密后的字符串进行编码
            return WXBizMsgCryptCode.OK, base64.b64encode(ciphertext)
        except Exception as e:
            logging.error(f"Prpcrypt encrypt error: {e}")
            return WXBizMsgCryptCode.ENCRYPTAES_ERROR, None

    def decrypt(self, text, receiveid):
        """对解密后的明文进行补位删除

        @param text: 密文
        @return: 删除填充补位后的明文
        """
        try:
            cryptor = AES.new(self.key, self.mode, self.key[:16])
            # 使用BASE64对密文进行解码，然后AES-CBC解密
            plain_text = cryptor.decrypt(base64.b64decode(text))
        except Exception as e:
            logging.error(f"Prpcrypt decrypt error: {e}")
            return WXBizMsgCryptCode.DECRYPTAESAES_ERROR, None
        try:
            pad = plain_text[-1]
            # 去掉补位字符串
            # pkcs7 = PKCS7Encoder()
            # plain_text = pkcs7.encode(plain_text)
            # 去除16位随机字符串
            content = plain_text[16:-pad]
            json_len = socket.ntohl(struct.unpack("I", content[:4])[0])
            json_content = content[4 : json_len + 4].decode("utf-8")
            from_receiveid = content[json_len + 4 :].decode("utf-8")
        except Exception as e:
            logging.error(f"Prpcrypt decrypt error: {e}")
            return WXBizMsgCryptCode.ILLEGALBUFFER_ERROR, None
        if from_receiveid != receiveid:
            logging.error(
                f"Prpcrypt decrypt error: receiveid not match, {receiveid}, {from_receiveid}"
            )
            return WXBizMsgCryptCode.VALIDATECORPID_ERROR, None
        return WXBizMsgCryptCode.OK, json_content

    def get_random_str(self):
        """随机生成16位字符串

        @return: 16位字符串
        """
        return str(random.randint(1000000000000000, 9999999999999999)).encode()


class WXBizJsonMsgCrypt(object):
    """提供企业微信消息的加解密接口"""

    # 构造函数
    def __init__(self, s_token, s_encoding_aes_key, s_receive_id):
        try:
            self.key = base64.b64decode(s_encoding_aes_key + "=")
            assert len(self.key) == 32
        except:
            raise FormatException("[error]: EncodingAESKey unvalid !")
        self.m_s_token = s_token
        self.m_s_receive_id = s_receive_id

        # 验证URL
        # @param sMsgSignature: 签名串，对应URL参数的msg_signature
        # @param sTimeStamp: 时间戳，对应URL参数的timestamp
        # @param sNonce: 随机串，对应URL参数的nonce
        # @param sEchoStr: 随机串，对应URL参数的echostr
        # @param sReplyEchoStr: 解密之后的echostr，当return返回0时有效
        # @return：成功0，失败返回对应的错误码

    def verify_url(
        self, s_msg_signature, s_time_stamp, s_nonce, s_echo_str
    ) -> tuple[int, str]:
        """验证URL签名是否正确"""
        sha1 = SHA1()
        # 计算安全签名
        ret, signature = sha1.get_sha1(
            self.m_s_token, s_time_stamp, s_nonce, s_echo_str
        )
        if ret != 0:
            return ret, None
        if not signature == s_msg_signature:
            return WXBizMsgCryptCode.VALIDATESIGNATURE_ERROR, None
        pc = Prpcrypt(self.key)
        ret, s_reply_echo_str = pc.decrypt(s_echo_str, self.m_s_receive_id)
        return ret, s_reply_echo_str

    def encrypt_msg(self, s_reply_msg: str, s_nonce: str, timestamp=None):
        """将企业回复用户的消息加密打包

        @param sReplyMsg: 企业号待回复用户的消息，json格式的字符串
        @param sTimeStamp: 时间戳，可以自己生成，也可以用URL参数的
            timestamp,如为None则自动用当前时间
        @param sNonce: 随机串，可以自己生成，也可以用URL参数的nonce
        sEncryptMsg: 加密后的可以直接回复用户的密文，包括
            msg_signature, timestamp, nonce, encrypt的json格式的字符串,
        return：成功0，sEncryptMsg,失败返回对应的错误码None
        """
        pc = Prpcrypt(self.key)
        ret, encrypt = pc.encrypt(s_reply_msg, self.m_s_receive_id)
        encrypt = encrypt.decode("utf-8")
        if ret != 0:
            return ret, None
        if timestamp is None:
            timestamp = str(int(time.time()))
        # 生成安全签名
        sha1 = SHA1()
        ret, signature = sha1.get_sha1(self.m_s_token, timestamp, s_nonce, encrypt)
        if ret != 0:
            return ret, None
        json_parse = JsonParse()
        return ret, json_parse.generate(encrypt, signature, timestamp, s_nonce)

    def decrypt_msg(self, s_post_data, s_msg_signature, s_time_stamp, s_nonce):
        # 检验消息的真实性，并且获取解密后的明文
        # @param sMsgSignature: 签名串，对应URL参数的msg_signature
        # @param sTimeStamp: 时间戳，对应URL参数的timestamp
        # @param sNonce: 随机串，对应URL参数的nonce
        # @param sPostData: 密文，对应POST请求的数据
        #  json_content: 解密后的原文，当return返回0时有效
        # @return: 成功0，失败返回对应的错误码
        # 验证安全签名
        json_parse = JsonParse()
        ret, encrypt = json_parse.extract(s_post_data)
        if ret != 0:
            return ret, None
        sha1 = SHA1()
        ret, signature = sha1.get_sha1(self.m_s_token, s_time_stamp, s_nonce, encrypt)
        if ret != 0:
            return ret, None
        if not signature == s_msg_signature:
            print("signature not match")
            print(signature)
            return WXBizMsgCryptCode.VALIDATESIGNATURE_ERROR, None
        pc = Prpcrypt(self.key)
        ret, json_content = pc.decrypt(encrypt, self.m_s_receive_id)
        return ret, json_content


def _generate_random_string(length):
    letters = string.ascii_letters + string.digits
    return "".join(random.choice(letters) for _ in range(length))


def _process_encrypted_image(image_url, aes_key_base64):
    """下载并解密加密图片

    参数:
        image_url: 加密图片的URL
        aes_key_base64: Base64编码的AES密钥(与回调加解密相同)

    返回:
        tuple: (status: bool, data: bytes/str)
               status为True时data是解密后的图片数据，
               status为False时data是错误信息
    """
    try:
        # 1. 下载加密图片
        logging.info("开始下载加密图片: %s", image_url)
        response = requests.get(image_url, timeout=15)
        response.raise_for_status()
        encrypted_data = response.content
        logging.info("图片下载成功，大小: %d 字节", len(encrypted_data))

        # 2. 准备AES密钥和IV
        if not aes_key_base64:
            raise ValueError("AES密钥不能为空")

        # Base64解码密钥 (自动处理填充)
        aes_key = base64.b64decode(aes_key_base64 + "=" * (-len(aes_key_base64) % 4))
        if len(aes_key) != 32:
            raise ValueError("无效的AES密钥长度: 应为32字节")

        iv = aes_key[:16]  # 初始向量为密钥前16字节

        # 3. 解密图片数据
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        decrypted_data = cipher.decrypt(encrypted_data)

        # 4. 去除PKCS#7填充 (Python 3兼容写法)
        pad_len = decrypted_data[-1]  # 直接获取最后一个字节的整数值
        if pad_len > 32:  # AES-256块大小为32字节
            raise ValueError("无效的填充长度 (大于32字节)")

        decrypted_data = decrypted_data[:-pad_len]
        logging.info("图片解密成功，解密后大小: %d 字节", len(decrypted_data))

        return True, decrypted_data

    except requests.exceptions.RequestException as e:
        error_msg = f"图片下载失败 : {str(e)}"
        logging.error(error_msg)
        return False, error_msg

    except ValueError as e:
        error_msg = f"参数错误 : {str(e)}"
        logging.error(error_msg)
        return False, error_msg

    except Exception as e:
        error_msg = f"图片处理异常 : {str(e)}"
        logging.error(error_msg)
        return False, error_msg


def make_text_stream(stream_id, content, finish):
    plain = {
        "msgtype": "stream",
        "stream": {"id": stream_id, "finish": finish, "content": content},
    }
    return json.dumps(plain, ensure_ascii=False)


def make_image_stream(stream_id, image_data, finish):
    image_md5 = hashlib.md5(image_data).hexdigest()
    image_base64 = base64.b64encode(image_data).decode("utf-8")

    plain = {
        "msgtype": "stream",
        "stream": {
            "id": stream_id,
            "finish": finish,
            "msg_item": [
                {
                    "msgtype": "image",
                    "image": {"base64": image_base64, "md5": image_md5},
                }
            ],
        },
    }
    return json.dumps(plain)


def encrypt_message(receiveid, nonce, timestamp, stream):
    logging.info(
        "开始加密消息，receiveid=%s, nonce=%s, timestamp=%s",
        receiveid,
        nonce,
        timestamp,
    )
    logging.debug("发送流消息: %s", stream)

    wxcpt = WXBizJsonMsgCrypt(TOKEN, ENCODING_AES_KEY, receiveid)
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
