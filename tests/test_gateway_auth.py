#!/usr/bin/env python3
"""
MaxBot 网关认证测试
测试认证鉴权系统
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from maxbot.gateway.auth import AuthManager, TokenInfo


def test_api_key_management():
    """测试 API Key 管理"""
    print("\n" + "=" * 70)
    print("测试 1: API Key 管理")
    print("=" * 70)
    
    auth = AuthManager()
    
    # 添加 API Key
    api_key = "test-api-key-12345"
    auth.add_api_key(api_key)
    print(f"✅ API Key 已添加")
    
    # 验证 API Key
    is_valid = auth.verify_api_key(api_key)
    print(f"✅ API Key 验证: {is_valid}")
    assert is_valid, "API Key 验证失败"
    
    # 验证无效 API Key
    is_invalid = auth.verify_api_key("invalid-key")
    print(f"✅ 无效 API Key 验证: {not is_invalid}")
    assert not is_invalid, "无效 API Key 应该验证失败"
    
    # 移除 API Key
    auth.remove_api_key(api_key)
    print(f"✅ API Key 已移除")
    
    # 验证已移除的 API Key
    is_valid_after_removal = auth.verify_api_key(api_key)
    print(f"✅ 移除后验证: {not is_valid_after_removal}")
    assert not is_valid_after_removal, "已移除的 API Key 应该验证失败"
    
    print("\n✅ API Key 管理测试通过")


def test_token_generation():
    """测试 Token 生成"""
    print("\n" + "=" * 70)
    print("测试 2: Token 生成")
    print("=" * 70)
    
    auth = AuthManager()
    
    # 添加 API Key
    api_key = "test-api-key-67890"
    auth.add_api_key(api_key)
    
    # 生成 Token
    token = auth.generate_token(api_key, ttl=3600)
    print(f"✅ Token 已生成")
    print(f"   Token: {token[:20]}...")
    
    # 验证 Token
    is_valid = auth.verify_token(token)
    print(f"✅ Token 验证: {is_valid}")
    assert is_valid, "Token 验证失败"
    
    # 获取 Token 信息
    token_info = auth.get_token_info(token)
    print(f"✅ Token 信息获取成功")
    print(f"   API Key: {token_info.api_key[:20]}...")
    print(f"   创建时间: {token_info.created_at}")
    print(f"   过期时间: {token_info.expires_at}")
    
    print("\n✅ Token 生成测试通过")


def test_token_expiration():
    """测试 Token 过期"""
    print("\n" + "=" * 70)
    print("测试 3: Token 过期")
    print("=" * 70)
    
    auth = AuthManager()
    
    # 添加 API Key
    api_key = "test-api-key-expire"
    auth.add_api_key(api_key)
    
    # 生成短期 Token（1 秒后过期）
    token = auth.generate_token(api_key, ttl=1)
    print(f"✅ 短期 Token 已生成（1 秒后过期）")
    
    # 立即验证
    is_valid = auth.verify_token(token)
    print(f"✅ 立即验证: {is_valid}")
    assert is_valid, "Token 应该立即有效"
    
    # 等待 2 秒
    import time
    time.sleep(2)
    
    # 验证过期
    is_expired = auth.verify_token(token)
    print(f"✅ 2 秒后验证: {not is_expired}")
    assert not is_expired, "Token 应该已过期"
    
    print("\n✅ Token 过期测试通过")


def test_token_revocation():
    """测试 Token 撤销"""
    print("\n" + "=" * 70)
    print("测试 4: Token 撤销")
    print("=" * 70)
    
    auth = AuthManager()
    
    # 添加 API Key
    api_key = "test-api-key-revoke"
    auth.add_api_key(api_key)
    
    # 生成 Token
    token = auth.generate_token(api_key)
    print(f"✅ Token 已生成")
    
    # 验证 Token
    is_valid = auth.verify_token(token)
    print(f"✅ 撤销前验证: {is_valid}")
    assert is_valid, "Token 应该有效"
    
    # 撤销 Token
    revoked = auth.revoke_token(token)
    print(f"✅ Token 撤销: {revoked}")
    assert revoked, "Token 撤销失败"
    
    # 验证已撤销的 Token
    is_valid_after_revoke = auth.verify_token(token)
    print(f"✅ 撤销后验证: {not is_valid_after_revoke}")
    assert not is_valid_after_revoke, "已撤销的 Token 应该验证失败"
    
    print("\n✅ Token 撤销测试通过")


def test_token_metadata():
    """测试 Token 元数据"""
    print("\n" + "=" * 70)
    print("测试 5: Token 元数据")
    print("=" * 70)
    
    auth = AuthManager()
    
    # 添加 API Key
    api_key = "test-api-key-metadata"
    auth.add_api_key(api_key)
    
    # 生成带元数据的 Token
    metadata = {
        "user_id": "user123",
        "role": "admin",
        "permissions": ["read", "write"],
    }
    token = auth.generate_token(api_key, metadata=metadata)
    print(f"✅ 带元数据的 Token 已生成")
    
    # 获取 Token 信息
    token_info = auth.get_token_info(token)
    print(f"✅ Token 信息获取成功")
    print(f"   用户 ID: {token_info.metadata.get('user_id')}")
    print(f"   角色: {token_info.metadata.get('role')}")
    print(f"   权限: {token_info.metadata.get('permissions')}")
    
    # 验证元数据
    assert token_info.metadata == metadata, "元数据不匹配"
    
    print("\n✅ Token 元数据测试通过")


def test_auth_stats():
    """测试认证统计"""
    print("\n" + "=" * 70)
    print("测试 6: 认证统计")
    print("=" * 70)
    
    auth = AuthManager()
    
    # 获取初始统计
    stats = auth.get_stats()
    print(f"✅ 初始统计")
    print(f"   API Key 数: {stats['api_keys_count']}")
    print(f"   Token 数: {stats['tokens_count']}")
    
    # 添加 API Key
    auth.add_api_key("api-key-1")
    auth.add_api_key("api-key-2")
    
    # 生成 Token
    token1 = auth.generate_token("api-key-1")
    token2 = auth.generate_token("api-key-2")
    
    # 获取更新后的统计
    stats = auth.get_stats()
    print(f"✅ 更新后统计")
    print(f"   API Key 数: {stats['api_keys_count']}")
    print(f"   Token 数: {stats['tokens_count']}")
    
    assert stats['api_keys_count'] == 2, "API Key 数量不匹配"
    assert stats['tokens_count'] == 2, "Token 数量不匹配"
    
    print("\n✅ 认证统计测试通过")


def test_cleanup_expired_tokens():
    """测试清理过期 Token"""
    print("\n" + "=" * 70)
    print("测试 7: 清理过期 Token")
    print("=" * 70)
    
    auth = AuthManager()
    
    # 添加 API Key
    api_key = "test-api-key-cleanup"
    auth.add_api_key(api_key)
    
    # 生成多个 Token（部分过期）
    token1 = auth.generate_token(api_key, ttl=3600)  # 1 小时后过期
    token2 = auth.generate_token(api_key, ttl=1)     # 1 秒后过期
    token3 = auth.generate_token(api_key, ttl=3600)  # 1 小时后过期
    
    print(f"✅ 已生成 3 个 Token（1 个即将过期）")
    
    # 等待 2 秒
    import time
    time.sleep(2)
    
    # 清理过期 Token
    cleaned = auth.clean_expired_tokens()
    print(f"✅ 已清理 {cleaned} 个过期 Token")
    
    # 验证剩余 Token
    stats = auth.get_stats()
    print(f"✅ 剩余 Token 数: {stats['tokens_count']}")
    
    assert stats['tokens_count'] == 2, "应该剩余 2 个 Token"
    
    print("\n✅ 清理过期 Token 测试通过")


def main():
    print("\n" + "=" * 70)
    print("MaxBot 网关认证测试")
    print("=" * 70)
    
    try:
        test_api_key_management()
        test_token_generation()
        test_token_expiration()
        test_token_revocation()
        test_token_metadata()
        test_auth_stats()
        test_cleanup_expired_tokens()
        
        print("\n" + "=" * 70)
        print("✅ 所有测试完成！")
        print("=" * 70)
        return 0
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
