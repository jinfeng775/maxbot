"""
微信（WeChat）渠道适配器 — 基于 iLink Bot API

参考 Hermes gateway/platforms/weixin.py 实现。

核心流程：
1. QR 扫码登录 → 获取 bot_token + account_id
2. 长轮询 getupdates 接收消息
3. 通过 context_token 回复
4. 媒体文件通过 AES-128-ECB 加密 CDN 传输

依赖：aiohttp, cryptography
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import mimetypes
import os
import re
import secrets
import struct
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional, Tuple
from urllib.parse import quote

from maxbot.gateway.channels.base import (
    ChannelAdapter,
    InboundMessage,
    MessageType,
    OutboundMessage,
)

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# ── 常量 ──────────────────────────────────────────────────

ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"
WEIXIN_CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"
ILINK_APP_ID = "bot"
CHANNEL_VERSION = "2.2.0"
ILINK_APP_CLIENT_VERSION = (2 << 16) | (2 << 8) | 0

EP_GET_UPDATES = "ilink/bot/getupdates"
EP_SEND_MESSAGE = "ilink/bot/sendmessage"
EP_SEND_TYPING = "ilink/bot/sendtyping"
EP_GET_CONFIG = "ilink/bot/getconfig"
EP_GET_UPLOAD_URL = "ilink/bot/getuploadurl"
EP_GET_BOT_QR = "ilink/bot/get_bot_qrcode"
EP_GET_QR_STATUS = "ilink/bot/get_qrcode_status"

LONG_POLL_TIMEOUT_MS = 35_000
API_TIMEOUT_MS = 15_000
CONFIG_TIMEOUT_MS = 10_000
QR_TIMEOUT_MS = 35_000

MAX_CONSECUTIVE_FAILURES = 3
RETRY_DELAY_SECONDS = 2
BACKOFF_DELAY_SECONDS = 30
SESSION_EXPIRED_ERRCODE = -14
MESSAGE_DEDUP_TTL_SECONDS = 300

# 消息类型
ITEM_TEXT = 1
ITEM_IMAGE = 2
ITEM_VOICE = 3
ITEM_FILE = 4
ITEM_VIDEO = 5

MSG_TYPE_USER = 1
MSG_TYPE_BOT = 2
MSG_STATE_FINISH = 2

TYPING_START = 1
TYPING_STOP = 2

# 媒体类型
MEDIA_IMAGE = 1
MEDIA_VIDEO = 2
MEDIA_FILE = 3
MEDIA_VOICE = 4


# ── 工具函数 ──────────────────────────────────────────────

def _pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def _aes128_ecb_encrypt(plaintext: bytes, key: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(_pkcs7_pad(plaintext)) + encryptor.finalize()


def _aes128_ecb_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    if not padded:
        return padded
    pad_len = padded[-1]
    if 1 <= pad_len <= 16 and padded.endswith(bytes([pad_len]) * pad_len):
        return padded[:-pad_len]
    return padded


def _aes_padded_size(size: int) -> int:
    return ((size + 1 + 15) // 16) * 16


def _random_wechat_uin() -> str:
    value = struct.unpack(">I", secrets.token_bytes(4))[0]
    return base64.b64encode(str(value).encode("utf-8")).decode("ascii")


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _headers(token: Optional[str], body: str) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Content-Length": str(len(body.encode("utf-8"))),
        "X-WECHAT-UIN": _random_wechat_uin(),
        "iLink-App-Id": ILINK_APP_ID,
        "iLink-App-ClientVersion": str(ILINK_APP_CLIENT_VERSION),
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _base_info() -> dict[str, Any]:
    return {"channel_version": CHANNEL_VERSION}


# ── 去重器 ────────────────────────────────────────────────

class _Deduplicator:
    def __init__(self, ttl: float = MESSAGE_DEDUP_TTL_SECONDS):
        self._seen: dict[str, float] = {}
        self._ttl = ttl

    def is_duplicate(self, msg_id: str) -> bool:
        now = time.time()
        # 清理过期
        self._seen = {k: v for k, v in self._seen.items() if now - v < self._ttl}
        if msg_id in self._seen:
            return True
        self._seen[msg_id] = now
        return False


# ── Context Token 存储 ────────────────────────────────────

class _ContextTokenStore:
    """持久化 context_token，用于回复消息"""

    def __init__(self, store_dir: Path):
        self._dir = store_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, str] = {}
        self._load()

    def _path(self) -> Path:
        return self._dir / "context_tokens.json"

    def _load(self):
        p = self._path()
        if p.exists():
            try:
                self._cache = json.loads(p.read_text())
            except Exception:
                self._cache = {}

    def _save(self):
        try:
            self._path().write_text(json.dumps(self._cache, ensure_ascii=False))
        except Exception:
            pass

    def get(self, user_id: str) -> Optional[str]:
        return self._cache.get(user_id)

    def set(self, user_id: str, token: str):
        self._cache[user_id] = token
        self._save()


# ── API 函数 ──────────────────────────────────────────────

async def _api_post(
    session: "aiohttp.ClientSession",
    *,
    base_url: str,
    endpoint: str,
    payload: dict[str, Any],
    token: Optional[str],
    timeout_ms: int,
) -> dict[str, Any]:
    body = _json_dumps({**payload, "base_info": _base_info()})
    url = f"{base_url.rstrip('/')}/{endpoint}"
    timeout = aiohttp.ClientTimeout(total=int(timeout_ms) / 1000)
    async with session.post(url, data=body, headers=_headers(token, body), timeout=timeout) as resp:
        raw = await resp.text()
        if not resp.ok:
            raise RuntimeError(f"iLink POST {endpoint} HTTP {resp.status}: {raw[:200]}")
        return json.loads(raw)


async def _api_get(
    session: "aiohttp.ClientSession",
    *,
    base_url: str,
    endpoint: str,
    timeout_ms: int,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{endpoint}"
    headers = {
        "iLink-App-Id": ILINK_APP_ID,
        "iLink-App-ClientVersion": str(ILINK_APP_CLIENT_VERSION),
    }
    timeout = aiohttp.ClientTimeout(total=int(timeout_ms) / 1000)
    async with session.get(url, headers=headers, timeout=timeout) as resp:
        raw = await resp.text()
        if not resp.ok:
            raise RuntimeError(f"iLink GET {endpoint} HTTP {resp.status}: {raw[:200]}")
        return json.loads(raw)


async def _get_updates(
    session: "aiohttp.ClientSession",
    *,
    base_url: str,
    token: str,
    sync_buf: str,
    timeout_ms: int,
) -> dict[str, Any]:
    try:
        return await _api_post(
            session,
            base_url=base_url,
            endpoint=EP_GET_UPDATES,
            payload={"get_updates_buf": sync_buf},
            token=token,
            timeout_ms=timeout_ms,
        )
    except asyncio.TimeoutError:
        return {"ret": 0, "msgs": [], "get_updates_buf": sync_buf}


async def _send_message(
    session: "aiohttp.ClientSession",
    *,
    base_url: str,
    token: str,
    to: str,
    text: str,
    context_token: Optional[str],
    client_id: str,
) -> None:
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    message: dict[str, Any] = {
        "from_user_id": "",
        "to_user_id": to,
        "client_id": client_id,
        "message_type": MSG_TYPE_BOT,
        "message_state": MSG_STATE_FINISH,
        "item_list": [{"type": ITEM_TEXT, "text_item": {"text": text}}],
    }
    if context_token:
        message["context_token"] = context_token
    await _api_post(
        session,
        base_url=base_url,
        endpoint=EP_SEND_MESSAGE,
        payload={"msg": message},
        token=token,
        timeout_ms=API_TIMEOUT_MS,
    )


async def _get_config(
    session: "aiohttp.ClientSession",
    *,
    base_url: str,
    token: str,
    user_id: str,
    context_token: Optional[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {"ilink_user_id": user_id}
    if context_token:
        payload["context_token"] = context_token
    return await _api_post(
        session,
        base_url=base_url,
        endpoint=EP_GET_CONFIG,
        payload=payload,
        token=token,
        timeout_ms=CONFIG_TIMEOUT_MS,
    )


async def _send_typing(
    session: "aiohttp.ClientSession",
    *,
    base_url: str,
    token: str,
    to_user_id: str,
    typing_ticket: str,
    status: int,
) -> None:
    await _api_post(
        session,
        base_url=base_url,
        endpoint=EP_SEND_TYPING,
        payload={
            "ilink_user_id": to_user_id,
            "typing_ticket": typing_ticket,
            "status": status,
        },
        token=token,
        timeout_ms=CONFIG_TIMEOUT_MS,
    )


async def _get_upload_url(
    session: "aiohttp.ClientSession",
    *,
    base_url: str,
    token: str,
    to_user_id: str,
    media_type: int,
    filekey: str,
    rawsize: int,
    rawfilemd5: str,
    filesize: int,
    aeskey_hex: str,
) -> dict[str, Any]:
    return await _api_post(
        session,
        base_url=base_url,
        endpoint=EP_GET_UPLOAD_URL,
        payload={
            "to_user_id": to_user_id,
            "media_type": media_type,
            "filekey": filekey,
            "rawsize": rawsize,
            "rawfilemd5": rawfilemd5,
            "filesize": filesize,
            "aeskey": aeskey_hex,
        },
        token=token,
        timeout_ms=API_TIMEOUT_MS,
    )


async def _upload_ciphertext(
    session: "aiohttp.ClientSession",
    *,
    ciphertext: bytes,
    upload_url: str,
) -> str:
    async with session.post(
        upload_url,
        data=ciphertext,
        headers={"Content-Type": "application/octet-stream"},
        timeout=aiohttp.ClientTimeout(total=60),
    ) as resp:
        if not resp.ok:
            raise RuntimeError(f"CDN upload failed: HTTP {resp.status}")
        data = await resp.json()
        return str(data.get("encrypted_query_param") or "")


async def _download_bytes(
    session: "aiohttp.ClientSession",
    *,
    url: str,
    timeout_seconds: float = 30.0,
) -> bytes:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as resp:
        resp.raise_for_status()
        return await resp.read()


async def _download_and_decrypt_media(
    session: "aiohttp.ClientSession",
    *,
    cdn_base_url: str,
    encrypted_query_param: Optional[str],
    aes_key_b64: Optional[str],
    full_url: Optional[str],
    timeout_seconds: float = 30.0,
) -> bytes:
    if full_url:
        raw = await _download_bytes(session, url=full_url, timeout_seconds=timeout_seconds)
    elif encrypted_query_param:
        url = f"{cdn_base_url.rstrip('/')}/download?encrypted_query_param={quote(encrypted_query_param, safe='')}"
        raw = await _download_bytes(session, url=url, timeout_seconds=timeout_seconds)
    else:
        raise ValueError("no download URL available")

    if aes_key_b64:
        try:
            decoded = base64.b64decode(aes_key_b64)
            if len(decoded) == 16:
                key = decoded
            elif len(decoded) == 32:
                text = decoded.decode("ascii", errors="ignore")
                key = bytes.fromhex(text) if text and all(c in "0123456789abcdefABCDEF" for c in text) else decoded[:16]
            else:
                key = decoded[:16]
            return _aes128_ecb_decrypt(raw, key)
        except Exception:
            return raw
    return raw


# ── Markdown 清理 ─────────────────────────────────────────

_FENCE_RE = re.compile(r"^```([^\n`]*)\s*$")
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TABLE_RULE_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")


def _normalize_markdown(content: str) -> str:
    """清理 markdown 为微信友好格式"""
    if not content:
        return ""
    lines = content.split("\n")
    out = []
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        m = _HEADER_RE.match(line)
        if m:
            out.append(f"**{m.group(2).strip()}**")
            continue
        if _TABLE_RULE_RE.match(line):
            continue
        out.append(line)
    return "\n".join(out)


def _split_for_delivery(content: str, max_len: int = 4000) -> list[str]:
    """按长度拆分长消息"""
    if len(content) <= max_len:
        return [content]
    chunks = []
    while content:
        if len(content) <= max_len:
            chunks.append(content)
            break
        # 优先在换行处切分
        cut = content.rfind("\n", 0, max_len)
        if cut < max_len // 2:
            cut = max_len
        chunks.append(content[:cut])
        content = content[cut:].lstrip("\n")
    return chunks


# ── QR 登录 ───────────────────────────────────────────────

async def qr_login(
    store_dir: Path,
    *,
    bot_type: str = "3",
    timeout_seconds: int = 480,
) -> Optional[dict[str, str]]:
    """
    扫码登录微信 iLink Bot API

    Returns: {"account_id", "token", "base_url", "user_id"} 或 None
    """
    if not AIOHTTP_AVAILABLE:
        raise RuntimeError("aiohttp is required")

    async with aiohttp.ClientSession(trust_env=True) as session:
        try:
            qr_resp = await _api_get(
                session,
                base_url=ILINK_BASE_URL,
                endpoint=f"{EP_GET_BOT_QR}?bot_type={bot_type}",
                timeout_ms=QR_TIMEOUT_MS,
            )
        except Exception as e:
            print(f"❌ 获取二维码失败: {e}")
            return None

        qrcode_value = str(qr_resp.get("qrcode") or "")
        qrcode_url = str(qr_resp.get("qrcode_img_content") or "")
        if not qrcode_value:
            print("❌ 二维码响应缺少 qrcode")
            return None

        print("\n请使用微信扫描以下二维码：")
        url_to_show = qrcode_url or qrcode_value
        print(url_to_show)

        try:
            import qrcode as qr_mod
            qr = qr_mod.QRCode()
            qr.add_data(url_to_show)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
        except ImportError:
            print("（安装 qrcode 库可在终端显示二维码: pip install qrcode）")

        deadline = time.time() + timeout_seconds
        current_base_url = ILINK_BASE_URL
        refresh_count = 0

        while time.time() < deadline:
            try:
                status_resp = await _api_get(
                    session,
                    base_url=current_base_url,
                    endpoint=f"{EP_GET_QR_STATUS}?qrcode={qrcode_value}",
                    timeout_ms=QR_TIMEOUT_MS,
                )
            except (asyncio.TimeoutError, Exception):
                await asyncio.sleep(1)
                continue

            status = str(status_resp.get("status") or "wait")
            if status == "wait":
                pass  # 等待扫码
            elif status == "scaned":
                print("\n已扫码，请在微信里确认...")
            elif status == "scaned_but_redirect":
                redirect_host = str(status_resp.get("redirect_host") or "")
                if redirect_host:
                    current_base_url = f"https://{redirect_host}"
            elif status == "expired":
                refresh_count += 1
                if refresh_count > 3:
                    print("\n二维码多次过期，请重新执行。")
                    return None
                print(f"\n二维码已过期，正在刷新... ({refresh_count}/3)")
                try:
                    qr_resp = await _api_get(
                        session,
                        base_url=ILINK_BASE_URL,
                        endpoint=f"{EP_GET_BOT_QR}?bot_type={bot_type}",
                        timeout_ms=QR_TIMEOUT_MS,
                    )
                    qrcode_value = str(qr_resp.get("qrcode") or "")
                    qrcode_url = str(qr_resp.get("qrcode_img_content") or "")
                    if qrcode_url:
                        print(qrcode_url)
                except Exception as e:
                    print(f"❌ 刷新二维码失败: {e}")
                    return None
            elif status == "confirmed":
                account_id = str(status_resp.get("ilink_bot_id") or "")
                token = str(status_resp.get("bot_token") or "")
                base_url = str(status_resp.get("baseurl") or ILINK_BASE_URL)
                user_id = str(status_resp.get("ilink_user_id") or "")
                if not account_id or not token:
                    print("❌ 登录凭证不完整")
                    return None

                # 保存凭证
                cred = {
                    "account_id": account_id,
                    "token": token,
                    "base_url": base_url,
                    "user_id": user_id,
                    "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                cred_path = store_dir / "weixin_credentials.json"
                store_dir.mkdir(parents=True, exist_ok=True)
                cred_path.write_text(json.dumps(cred, indent=2, ensure_ascii=False))
                try:
                    cred_path.chmod(0o600)
                except OSError:
                    pass

                print(f"\n✅ 微信连接成功! account_id={account_id}")
                return cred

            await asyncio.sleep(1)

        print("\n微信登录超时。")
        return None


# ── 微信渠道适配器 ────────────────────────────────────────

class WeixinChannel(ChannelAdapter):
    """
    微信渠道 — 基于 iLink Bot API 长轮询

    配置方式：
    1. 首次运行调用 qr_login() 获取凭证
    2. 或设置环境变量 WEIXIN_ACCOUNT_ID, WEIXIN_TOKEN, WEIXIN_BASE_URL
    3. 或传入 account_id, token, base_url 参数
    """

    MAX_MESSAGE_LENGTH = 4000

    def __init__(
        self,
        account_id: str | None = None,
        token: str | None = None,
        base_url: str | None = None,
        cdn_base_url: str | None = None,
        store_dir: str | Path | None = None,
    ):
        if not AIOHTTP_AVAILABLE:
            raise ImportError("需要安装 aiohttp: pip install aiohttp")
        if not CRYPTO_AVAILABLE:
            raise ImportError("需要安装 cryptography: pip install cryptography")

        self._store_dir = Path(store_dir) if store_dir else Path.home() / ".maxbot" / "weixin"
        self._store_dir.mkdir(parents=True, exist_ok=True)

        # 加载凭证
        self._account_id = (account_id or os.getenv("WEIXIN_ACCOUNT_ID", "")).strip()
        self._token = (token or os.getenv("WEIXIN_TOKEN", "")).strip()
        self._base_url = (base_url or os.getenv("WEIXIN_BASE_URL", ILINK_BASE_URL)).strip().rstrip("/")
        self._cdn_base_url = (cdn_base_url or os.getenv("WEIXIN_CDN_BASE_URL", WEIXIN_CDN_BASE_URL)).strip().rstrip("/")

        # 如果没有 token，尝试从保存的凭证加载
        if not self._token:
            cred_path = self._store_dir / "weixin_credentials.json"
            if cred_path.exists():
                try:
                    cred = json.loads(cred_path.read_text())
                    self._token = str(cred.get("token") or "").strip()
                    self._account_id = str(cred.get("account_id") or self._account_id).strip()
                    self._base_url = str(cred.get("base_url") or self._base_url).strip().rstrip("/")
                except Exception:
                    pass

        self._session: Optional["aiohttp.ClientSession"] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._running = False
        self._dedup = _Deduplicator()
        self._token_store = _ContextTokenStore(self._store_dir)
        self._message_callback: Optional[Callable] = None
        self._message_queue: Optional[asyncio.Queue[InboundMessage]] = None
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._typing_tickets: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "weixin"

    @property
    def display_name(self) -> str:
        return "微信"

    @property
    def capabilities(self) -> list[str]:
        return ["text", "image", "file", "audio", "video"]

    async def connect(self) -> bool:
        """启动长轮询"""
        if not self._token or not self._account_id:
            raise ValueError(
                "微信凭证未配置。请先调用 qr_login() 或设置 WEIXIN_ACCOUNT_ID + WEIXIN_TOKEN"
            )

        self._main_loop = asyncio.get_running_loop()
        self._message_queue = asyncio.Queue()
        self._session = aiohttp.ClientSession(trust_env=True)
        self._running = True

        # 恢复 context tokens
        self._token_store._load()

        # 启动长轮询
        self._poll_task = asyncio.create_task(self._poll_loop(), name="weixin-poll")
        return True

    async def disconnect(self):
        """断开连接"""
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def send_message(self, message: OutboundMessage) -> bool:
        """发送消息到微信"""
        if not self._session or not self._token:
            return False

        chat_id = message.chat_id
        context_token = self._token_store.get(chat_id)

        # 文本消息
        if message.message_type == MessageType.TEXT or message.content:
            text = _normalize_markdown(message.content)
            chunks = _split_for_delivery(text, self.MAX_MESSAGE_LENGTH)
            try:
                for chunk in chunks:
                    if not chunk.strip():
                        continue
                    client_id = f"maxbot-weixin-{uuid.uuid4().hex}"
                    await _send_message(
                        self._session,
                        base_url=self._base_url,
                        token=self._token,
                        to=chat_id,
                        text=chunk,
                        context_token=context_token,
                        client_id=client_id,
                    )
            except Exception as e:
                print(f"❌ 微信发送失败: {e}")
                return False

        # 媒体文件
        if message.media_path:
            try:
                await self._send_file(chat_id, message.media_path, message.content)
            except Exception as e:
                print(f"❌ 微信媒体发送失败: {e}")
                return False

        return True

    def on_message_callback(self, callback: Callable):
        """注册消息回调"""
        self._message_callback = callback

    async def receive_stream(self) -> AsyncIterator[InboundMessage]:
        """消息接收流"""
        if not self._message_queue:
            return
        while True:
            try:
                msg = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                yield msg
            except asyncio.TimeoutError:
                continue

    # ── 长轮询 ──────────────────────────────────────────

    async def _poll_loop(self):
        """长轮询主循环"""
        assert self._session is not None
        sync_buf = ""
        sync_buf_path = self._store_dir / "sync_buf.txt"
        if sync_buf_path.exists():
            try:
                sync_buf = sync_buf_path.read_text().strip()
            except Exception:
                pass

        timeout_ms = LONG_POLL_TIMEOUT_MS
        consecutive_failures = 0

        while self._running:
            try:
                response = await _get_updates(
                    self._session,
                    base_url=self._base_url,
                    token=self._token,
                    sync_buf=sync_buf,
                    timeout_ms=timeout_ms,
                )

                suggested_timeout = response.get("longpolling_timeout_ms")
                if suggested_timeout:
                    try:
                        timeout_ms = int(suggested_timeout)
                    except (ValueError, TypeError):
                        pass

                ret = response.get("ret", 0)
                errcode = response.get("errcode", 0)

                if ret not in (0, None) or errcode not in (0, None):
                    if ret == SESSION_EXPIRED_ERRCODE or errcode == SESSION_EXPIRED_ERRCODE:
                        print("❌ 微信会话已过期，暂停 10 分钟")
                        await asyncio.sleep(600)
                        consecutive_failures = 0
                        continue
                    consecutive_failures += 1
                    delay = BACKOFF_DELAY_SECONDS if consecutive_failures >= MAX_CONSECUTIVE_FAILURES else RETRY_DELAY_SECONDS
                    print(f"⚠️ 微信 getUpdates 失败 (ret={ret}, errcode={errcode}) {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}")
                    await asyncio.sleep(delay)
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        consecutive_failures = 0
                    continue

                consecutive_failures = 0
                new_sync_buf = str(response.get("get_updates_buf") or "")
                if new_sync_buf:
                    sync_buf = new_sync_buf
                    try:
                        sync_buf_path.write_text(sync_buf)
                    except Exception:
                        pass

                # 处理消息
                for msg_data in response.get("msgs") or []:
                    asyncio.create_task(self._process_message(msg_data))

            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_failures += 1
                print(f"❌ 微信轮询错误 ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): {e}")
                delay = BACKOFF_DELAY_SECONDS if consecutive_failures >= MAX_CONSECUTIVE_FAILURES else RETRY_DELAY_SECONDS
                await asyncio.sleep(delay)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    consecutive_failures = 0

    # ── 消息处理 ─────────────────────────────────────────

    async def _process_message(self, message: dict[str, Any]):
        """处理单条入站消息"""
        try:
            sender_id = str(message.get("from_user_id") or "").strip()
            if not sender_id or sender_id == self._account_id:
                return

            message_id = str(message.get("message_id") or "").strip()
            if message_id and self._dedup.is_duplicate(message_id):
                return

            # 判断群聊/私聊
            room_id = str(message.get("room_id") or message.get("chat_room_id") or "").strip()
            to_user_id = str(message.get("to_user_id") or "").strip()
            is_group = bool(room_id) or (
                to_user_id and self._account_id and to_user_id != self._account_id
                and message.get("msg_type") == 1
            )
            chat_id = (room_id if is_group else sender_id) or sender_id

            # 保存 context_token
            context_token = str(message.get("context_token") or "").strip()
            if context_token:
                self._token_store.set(sender_id, context_token)
                # 异步获取 typing ticket
                asyncio.create_task(self._maybe_fetch_typing_ticket(sender_id, context_token))

            # 提取文本和媒体
            item_list = message.get("item_list") or []
            text = ""
            media_paths = []
            media_types = []

            for item in item_list:
                item_type = item.get("type")
                if item_type == ITEM_TEXT:
                    t = (item.get("text_item") or {}).get("text", "")
                    if t:
                        text += t
                elif item_type == ITEM_IMAGE:
                    path = await self._download_media(item, "image_item", ".jpg")
                    if path:
                        media_paths.append(path)
                        media_types.append("image/jpeg")
                elif item_type == ITEM_VOICE:
                    path = await self._download_media(item, "voice_item", ".silk")
                    if path:
                        media_paths.append(path)
                        media_types.append("audio/silk")
                elif item_type == ITEM_FILE:
                    file_item = item.get("file_item") or {}
                    filename = str(file_item.get("file_name") or "document.bin")
                    ext = Path(filename).suffix or ".bin"
                    path = await self._download_media(file_item, "media", ext)
                    if path:
                        media_paths.append(path)
                        media_types.append("application/octet-stream")
                elif item_type == ITEM_VIDEO:
                    path = await self._download_media(item, "video_item", ".mp4")
                    if path:
                        media_paths.append(path)
                        media_types.append("video/mp4")

            if not text and not media_paths:
                return

            # 确定消息类型
            msg_type = MessageType.TEXT
            if media_types:
                mt = media_types[0]
                if mt.startswith("image/"):
                    msg_type = MessageType.IMAGE
                elif mt.startswith("audio/"):
                    msg_type = MessageType.AUDIO
                elif mt.startswith("video/"):
                    msg_type = MessageType.VIDEO
                else:
                    msg_type = MessageType.FILE

            inbound = InboundMessage(
                channel="weixin",
                channel_message_id=message_id,
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_id,  # iLink API 不返回昵称
                message_type=msg_type,
                content=text,
                media_path=media_paths[0] if media_paths else "",
                is_group=is_group,
                raw=message,
            )

            # 分发到队列和回调
            if self._main_loop and self._main_loop.is_running():
                if self._message_callback:
                    self._main_loop.call_soon_threadsafe(
                        self._schedule_callback, inbound
                    )
                if self._message_queue:
                    self._main_loop.call_soon_threadsafe(
                        self._message_queue.put_nowait, inbound
                    )

        except Exception as e:
            print(f"❌ 微信消息处理失败: {e}")

    def _schedule_callback(self, inbound: InboundMessage):
        """安全调度回调到主循环"""
        if self._message_callback and self._main_loop:
            asyncio.ensure_future(self._message_callback(inbound), loop=self._main_loop)

    async def _download_media(self, item: dict, key: str, ext: str) -> Optional[str]:
        """下载并解密媒体文件"""
        if not self._session:
            return None
        media_ref = item.get(key) or {}
        if isinstance(media_ref, dict):
            inner_media = media_ref.get("media") or media_ref
        else:
            inner_media = item
        try:
            data = await _download_and_decrypt_media(
                self._session,
                cdn_base_url=self._cdn_base_url,
                encrypted_query_param=inner_media.get("encrypt_query_param"),
                aes_key_b64=inner_media.get("aes_key"),
                full_url=inner_media.get("full_url"),
                timeout_seconds=60.0,
            )
            # 缓存到临时文件
            fd, path = tempfile.mkstemp(suffix=ext, prefix="maxbot-weixin-")
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            return path
        except Exception as e:
            print(f"⚠️ 微信媒体下载失败: {e}")
            return None

    async def _maybe_fetch_typing_ticket(self, user_id: str, context_token: Optional[str]):
        """获取 typing ticket（用于发送"正在输入"）"""
        if user_id in self._typing_tickets or not self._session:
            return
        try:
            resp = await _get_config(
                self._session,
                base_url=self._base_url,
                token=self._token,
                user_id=user_id,
                context_token=context_token,
            )
            ticket = str(resp.get("typing_ticket") or "")
            if ticket:
                self._typing_tickets[user_id] = ticket
        except Exception:
            pass

    async def _send_file(self, chat_id: str, path: str, caption: str = ""):
        """上传并发送文件"""
        assert self._session is not None

        plaintext = Path(path).read_bytes()
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        filekey = secrets.token_hex(16)
        aes_key = secrets.token_bytes(16)
        rawsize = len(plaintext)
        rawfilemd5 = hashlib.md5(plaintext).hexdigest()

        if mime.startswith("image/"):
            media_type = MEDIA_IMAGE
        elif mime.startswith("video/"):
            media_type = MEDIA_VIDEO
        elif mime.startswith("audio/") or path.endswith(".silk"):
            media_type = MEDIA_VOICE
        else:
            media_type = MEDIA_FILE

        upload_resp = await _get_upload_url(
            self._session,
            base_url=self._base_url,
            token=self._token,
            to_user_id=chat_id,
            media_type=media_type,
            filekey=filekey,
            rawsize=rawsize,
            rawfilemd5=rawfilemd5,
            filesize=_aes_padded_size(rawsize),
            aeskey_hex=aes_key.hex(),
        )

        upload_param = str(upload_resp.get("upload_param") or "")
        upload_full_url = str(upload_resp.get("upload_full_url") or "")
        ciphertext = _aes128_ecb_encrypt(plaintext, aes_key)

        if upload_full_url:
            upload_url = upload_full_url
        elif upload_param:
            cdn_base = self._cdn_base_url.rstrip("/")
            upload_url = f"{cdn_base}/upload?encrypted_query_param={quote(upload_param, safe='')}&filekey={quote(filekey, safe='')}"
        else:
            raise RuntimeError("getUploadUrl 未返回上传地址")

        encrypted_query_param = await _upload_ciphertext(
            self._session, ciphertext=ciphertext, upload_url=upload_url
        )

        # 发送文字说明
        context_token = self._token_store.get(chat_id)
        if caption:
            client_id = f"maxbot-weixin-{uuid.uuid4().hex}"
            await _send_message(
                self._session,
                base_url=self._base_url,
                token=self._token,
                to=chat_id,
                text=_normalize_markdown(caption),
                context_token=context_token,
                client_id=client_id,
            )

        # 构造媒体消息
        aes_key_for_api = base64.b64encode(aes_key.hex().encode("ascii")).decode("ascii")
        media_item = self._build_media_item(
            media_type, encrypted_query_param, aes_key_for_api, len(ciphertext), rawsize, Path(path).name, rawfilemd5,
        )

        client_id = f"maxbot-weixin-{uuid.uuid4().hex}"
        await _api_post(
            self._session,
            base_url=self._base_url,
            endpoint=EP_SEND_MESSAGE,
            payload={
                "msg": {
                    "from_user_id": "",
                    "to_user_id": chat_id,
                    "client_id": client_id,
                    "message_type": MSG_TYPE_BOT,
                    "message_state": MSG_STATE_FINISH,
                    "item_list": [media_item],
                    **({"context_token": context_token} if context_token else {}),
                }
            },
            token=self._token,
            timeout_ms=API_TIMEOUT_MS,
        )

    def _build_media_item(
        self, media_type: int, encrypt_query_param: str, aes_key_for_api: str,
        ciphertext_size: int, plaintext_size: int, filename: str, rawfilemd5: str,
    ) -> dict:
        if media_type == MEDIA_IMAGE:
            return {
                "type": ITEM_IMAGE,
                "image_item": {
                    "media": {
                        "encrypt_query_param": encrypt_query_param,
                        "aes_key": aes_key_for_api,
                        "encrypt_type": 1,
                    },
                    "mid_size": ciphertext_size,
                },
            }
        if media_type == MEDIA_VIDEO:
            return {
                "type": ITEM_VIDEO,
                "video_item": {
                    "media": {
                        "encrypt_query_param": encrypt_query_param,
                        "aes_key": aes_key_for_api,
                        "encrypt_type": 1,
                    },
                    "video_size": ciphertext_size,
                    "video_md5": rawfilemd5,
                },
            }
        if media_type == MEDIA_VOICE:
            return {
                "type": ITEM_VOICE,
                "voice_item": {
                    "media": {
                        "encrypt_query_param": encrypt_query_param,
                        "aes_key": aes_key_for_api,
                        "encrypt_type": 1,
                    },
                    "playtime": 0,
                },
            }
        return {
            "type": ITEM_FILE,
            "file_item": {
                "media": {
                    "encrypt_query_param": encrypt_query_param,
                    "aes_key": aes_key_for_api,
                    "encrypt_type": 1,
                },
                "file_name": filename,
                "len": str(plaintext_size),
            },
        }
