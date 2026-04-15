"""MaxBot CLI — 交互式命令行界面"""

from __future__ import annotations

import argparse
import json
import os
import sys

from maxbot import __version__
from maxbot.core import Agent, AgentConfig
from maxbot.tools import registry


def main():
    parser = argparse.ArgumentParser(
        prog="maxbot",
        description="MaxBot — 自我学习、自我构建的超级智能体",
    )
    parser.add_argument("--version", action="version", version=f"maxbot {__version__}")
    parser.add_argument("-m", "--model", default=None, help="模型名称 (默认: gpt-4o)")
    parser.add_argument("--provider", default=None, help="提供商: openai | anthropic")
    parser.add_argument("--base-url", default=None, help="API base URL (兼容接口)")
    parser.add_argument("--api-key", default=None, help="API Key")
    parser.add_argument("--max-iter", type=int, default=50, help="最大迭代次数")
    parser.add_argument("message", nargs="?", help="直接发送消息（非交互模式）")

    args = parser.parse_args()

    # 构建配置
    config = AgentConfig(
        model=args.model or os.getenv("MAXBOT_MODEL", "gpt-4o"),
        base_url=args.base_url or os.getenv("MAXBOT_BASE_URL"),
        api_key=args.api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
        max_iterations=args.max_iter,
    )

    if args.provider:
        config.provider = args.provider

    # 确保内置工具加载
    from maxbot.tools import registry as _r  # noqa: F811 — 触发导入

    agent = Agent(config=config, registry=registry)

    # 设置回调（终端输出）
    def on_tool_start(name, args):
        tool_args = json.dumps(args, ensure_ascii=False)
        if len(tool_args) > 80:
            tool_args = tool_args[:80] + "..."
        print(f"  🔧 {name}({tool_args})")

    def on_tool_end(name, result):
        preview = result[:100] if isinstance(result, str) else str(result)[:100]
        print(f"  ✅ → {preview}")

    agent.on_tool_start = on_tool_start
    agent.on_tool_end = on_tool_end

    # 非交互模式
    if args.message:
        response = agent.chat(args.message)
        print(response)
        return

    # 交互模式
    print(f"🤖 MaxBot v{__version__} — 模型: {config.model}")
    print(f"📦 已加载 {len(registry)} 个工具")
    print("输入消息开始对话，/quit 退出\n")

    while True:
        try:
            user_input = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input in ("/quit", "/exit", "/q"):
            print("再见！")
            break

        if user_input == "/tools":
            print(f"\n📦 已注册工具 ({len(registry)} 个):")
            for t in registry.list_tools():
                print(f"  - {t.name}: {t.description[:60]}")
            print()
            continue

        if user_input == "/reset":
            agent.reset()
            print("🔄 对话已重置\n")
            continue

        print("🤔 思考中...")
        response = agent.chat(user_input)
        print(f"\n🤖 {response}\n")


if __name__ == "__main__":
    main()
