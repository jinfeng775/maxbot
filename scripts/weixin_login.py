#!/usr/bin/env python3
"""
微信扫码登录 — 获取 MaxBot 微信凭证

用法：
    python3 scripts/weixin_login.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path

async def main():
    from maxbot.gateway.channels.weixin import qr_login

    store_dir = Path.home() / ".maxbot" / "weixin"
    print("正在获取微信登录二维码...\n")

    result = await qr_login(store_dir)

    if result:
        print(f"\n✅ 凭证已保存到: {store_dir / 'weixin_credentials.json'}")
        print(f"   account_id: {result['account_id']}")
        print(f"   base_url:   {result['base_url']}")
        print(f"\n重启 Gateway 即可生效:")
        print(f"   cd /root/maxbot && python3 scripts/start_gateway.py")
    else:
        print("\n❌ 登录失败")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
