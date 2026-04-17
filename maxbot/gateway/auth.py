"""
认证鉴权系统

提供 API Key 认证、Token 管理和权限控制
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from maxbot.utils.logger import get_logger

# 获取认证日志器
logger = get_logger("auth")


@dataclass
class TokenInfo:
    """Token 信息"""
    token: str
    api_key: str
    created_at: float
    expires_at: float | None = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AuthManager:
    """
    认证管理器

    功能：
    - API Key 验证
    - Token 生成和验证
    - 权限检查
    """

    def __init__(self):
        """初始化认证管理器"""
        self._api_keys: set[str] = set()
        self._tokens: dict[str, TokenInfo] = {}
        self._default_token_ttl = 3600  # 默认 Token 有效期：1 小时

    def add_api_key(self, api_key: str):
        """
        添加 API Key

        Args:
            api_key: API Key
        """
        # 存储 API Key 的哈希值（不存储明文）
        api_key_hash = self._hash_api_key(api_key)
        self._api_keys.add(api_key_hash)
        logger.info(f"API Key 已添加: {api_key[:8]}...")

    def remove_api_key(self, api_key: str):
        """
        移除 API Key

        Args:
            api_key: API Key
        """
        api_key_hash = self._hash_api_key(api_key)
        if api_key_hash in self._api_keys:
            self._api_keys.remove(api_key_hash)
            logger.info(f"API Key 已移除: {api_key[:8]}...")

    def verify_api_key(self, api_key: str) -> bool:
        """
        验证 API Key

        Args:
            api_key: API Key

        Returns:
            是否有效
        """
        api_key_hash = self._hash_api_key(api_key)
        return api_key_hash in self._api_keys

    def generate_token(
        self,
        api_key: str,
        ttl: int | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        生成 Token

        Args:
            api_key: API Key
            ttl: 有效期（秒），None 表示使用默认值
            metadata: 元数据

        Returns:
            Token
        """
        # 验证 API Key
        if not self.verify_api_key(api_key):
            raise ValueError("无效的 API Key")

        # 生成 Token
        token = secrets.token_urlsafe(32)

        # 计算过期时间
        if ttl is None:
            ttl = self._default_token_ttl

        expires_at = time.time() + ttl if ttl > 0 else None

        # 保存 Token 信息
        self._tokens[token] = TokenInfo(
            token=token,
            api_key=api_key,
            created_at=time.time(),
            expires_at=expires_at,
            metadata=metadata or {},
        )

        logger.info(f"Token 已生成: {token[:16]}...")
        return token

    def verify_token(self, token: str) -> bool:
        """
        验证 Token

        Args:
            token: Token

        Returns:
            是否有效
        """
        if token not in self._tokens:
            logger.warning(f"Token 不存在: {token[:16]}...")
            return False

        token_info = self._tokens[token]

        # 检查是否过期
        if token_info.expires_at and token_info.expires_at < time.time():
            logger.warning(f"Token 已过期: {token[:16]}...")
            del self._tokens[token]
            return False

        return True

    def revoke_token(self, token: str) -> bool:
        """
        撤销 Token

        Args:
            token: Token

        Returns:
            是否成功
        """
        if token in self._tokens:
            del self._tokens[token]
            logger.info(f"Token 已撤销: {token[:16]}...")
            return True
        return False

    def get_token_info(self, token: str) -> TokenInfo | None:
        """
        获取 Token 信息

        Args:
            token: Token

        Returns:
            Token 信息
        """
        if not self.verify_token(token):
            return None
        return self._tokens.get(token)

    def clean_expired_tokens(self) -> int:
        """
        清理过期 Token

        Returns:
            清理的数量
        """
        now = time.time()
        expired_tokens = [
            token
            for token, info in self._tokens.items()
            if info.expires_at and info.expires_at < now
        ]

        for token in expired_tokens:
            del self._tokens[token]

        if expired_tokens:
            logger.info(f"已清理 {len(expired_tokens)} 个过期 Token")

        return len(expired_tokens)

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息
        """
        return {
            "api_keys_count": len(self._api_keys),
            "tokens_count": len(self._tokens),
            "default_token_ttl": self._default_token_ttl,
        }

    @staticmethod
    def _hash_api_key(api_key: str) -> str:
        """
        计算 API Key 的哈希值

        Args:
            api_key: API Key

        Returns:
            哈希值
        """
        return hashlib.sha256(api_key.encode()).hexdigest()


# ==================== 便捷函数 ====================

def create_auth_manager() -> AuthManager:
    """
    创建认证管理器

    Returns:
        认证管理器实例
    """
    return AuthManager()
