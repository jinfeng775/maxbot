"""CLI 接口"""

from __future__ import annotations

import argparse
import os
from datetime import datetime

import sys
from pathlib import Path

from maxbot import __version__
from maxbot.core import Agent, AgentConfig
from maxbot.tools import registry


def _format_session_time(ts: float | None) -> str:
    if ts is None:
        return "未知时间"

    dt = datetime.fromtimestamp(ts)
    now = datetime.now()
    delta = now - dt

    if delta.total_seconds() < 60:
        return "刚刚"
    if delta.total_seconds() < 3600:
        minutes = max(1, int(delta.total_seconds() // 60))
        return f"{minutes} 分钟前"

    today = now.date()
    target_day = dt.date()
    if target_day == today:
        return f"今天 {dt.strftime('%H:%M')}"
    if (today - target_day).days == 1:
        return f"昨天 {dt.strftime('%H:%M')}"
    return dt.strftime("%Y-%m-%d %H:%M")


def load_env_file():
    """从 ~/.maxbot/.env 加载环境变量"""
    env_path = Path.home() / ".maxbot" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def main():
    parser = argparse.ArgumentParser(
        prog="maxbot",
        description="MaxBot — 自我学习、自我构建的超级智能体",
    )
    parser.add_argument("--version", action="version", version=f"maxbot {__version__}")
    parser.add_argument("-m", "--model", default=None, help="模型名称")
    parser.add_argument("--provider", default=None, help="提供商: openai | anthropic")
    parser.add_argument("--base-url", default=None, help="API base URL (兼容接口)")
    parser.add_argument("--api-key", default=None, help="API Key")
    parser.add_argument("--max-iter", type=int, default=50, help="最大迭代次数")
    parser.add_argument("--no-tools", action="store_true", help="禁用所有工具")
    parser.add_argument("--system", default=None, help="自定义 system prompt")
    parser.add_argument("message", nargs="?", help="直接发送消息（非交互模式）")

    args = parser.parse_args()

    # 加载环境变量
    load_env_file()

    # 构建配置
    config = AgentConfig(
        model=args.model or os.getenv("MAXBOT_MODEL", "mimo-v2-pro"),
        base_url=args.base_url or os.getenv("MAXBOT_BASE_URL"),
        api_key=args.api_key or os.getenv("MAXBOT_API_KEY"),
        max_iterations=args.max_iter,
    )
    if args.system:
        config.system_prompt = args.system
    if args.provider:
        config.provider = args.provider

    # 确保内置工具加载
    from maxbot.tools import registry as _r  # noqa: F811

    tool_registry = registry if not args.no_tools else type(registry)()
    agent = Agent(config=config, registry=tool_registry)

    # 非交互模式
    if args.message:
        response = agent.run(args.message)
        print(response)
        return

    # 交互模式
    print(f"🤖 MaxBot v{__version__}")
    print(f"   模型: {config.model}")
    print(f"   工具: {len(tool_registry)} 个")
    print()
    print("  输入消息开始对话")
    print("  /help 查看命令 | /quit 退出")
    print()

    while True:
        try:
            user_input = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        # 命令处理
        if user_input in ("/quit", "/exit", "/q"):
            print("再见！")
            break

        if user_input == "/help":
            print("""
  命令列表:
    /help                  显示此帮助
    /new                   开启新会话
    /reset                 重置当前上下文（保留历史）
    /sessions              列出历史会话
    /resume [id]           恢复指定历史会话；无参数时列出最近会话
    /delete_session <id>   删除指定历史会话
    /tools                 列出所有可用工具
    /stats                 显示会话统计
    /history               显示对话历史摘要
    /model <name>          切换模型
    /quit                  退出
            """)
            continue

        if user_input == "/tools":
            print(f"\n  已注册工具 ({len(tool_registry)} 个):")
            for t in tool_registry.list_tools():
                desc = t.description[:50] + ("..." if len(t.description) > 50 else "")
                print(f"    • {t.name}: {desc}")
            print()
            continue

        if user_input == "/new":
            old_session_id = agent.config.session_id
            new_session_id = agent.new_session()
            print(f"  ✨ 新会话已开启（旧会话 {old_session_id} 已保留，当前会话 {new_session_id}）\n")
            continue

        if user_input == "/reset":
            agent.reset()
            print("  🔄 当前上下文已重置（会话历史仍保留）\n")
            continue

        if user_input == "/sessions":
            sessions = agent.list_sessions()
            print(f"\n  📚 历史会话 ({len(sessions)} 个):")
            for idx, session in enumerate(sessions[:20], 1):
                title = session.get("title") or "(无标题)"
                updated = _format_session_time(session.get("updated_at"))
                print(f"    {idx}. {session['session_id']} | {title} | {updated}")
            print()
            continue

        if user_input == "/resume":
            sessions = agent.list_sessions()
            print(f"\n  📚 最近会话 ({len(sessions)} 个):")
            for idx, session in enumerate(sessions[:20], 1):
                title = session.get("title") or "(无标题)"
                updated = _format_session_time(session.get("updated_at"))
                print(f"    {idx}. {session['session_id']} | {title} | {updated}")
            print("\n  用法: /resume <session_id>\n")
            continue

        if user_input.startswith("/resume "):
            target_session_id = user_input[8:].strip()
            if not target_session_id:
                print("  ⚠️ 用法: /resume <session_id>\n")
                continue
            if agent.resume_session(target_session_id):
                print(f"  ♻️ 已恢复会话 {target_session_id}\n")
            else:
                print(f"  ⚠️ 未找到会话 {target_session_id}\n")
            continue

        if user_input.startswith("/delete_session "):
            target_session_id = user_input[len("/delete_session "):].strip()
            if not target_session_id:
                print("  ⚠️ 用法: /delete_session <session_id>\n")
                continue
            if agent.delete_session(target_session_id):
                print(f"  🗑️ 已删除会话 {target_session_id}\n")
            else:
                print(f"  ⚠️ 未找到会话 {target_session_id}\n")
            continue

        if user_input == "/stats":
            messages = agent.get_messages()
            print(f"\n  📊 会话统计:")
            print(f"    总消息数: {len(messages)}")
            print(f"    会话轮询次数: {agent._conversation_turns}")
            if messages:
                from collections import Counter
                roles = Counter(m.role for m in messages)
                for role, count in roles.items():
                    print(f"    {role}: {count}")
            print()
            continue

        if user_input == "/history":
            messages = agent.get_messages()
            print(f"\n  📜 对话历史 ({len(messages)} 条):")
            for i, m in enumerate(messages[-10:], 1):
                content = m.content[:60] if hasattr(m, 'content') else str(m)[:60]
                print(f"    {i}. [{m.role}] {content}")
            print()
            continue

        if user_input.startswith("/model "):
            new_model = user_input[7:].strip()
            config.model = new_model
            agent._client = None  # 重建客户端
            print(f"  模型已切换: {new_model}\n")
            continue

        # 普通对话
        print("  🤔 思考中...")
        response = agent.run(user_input)
        print(f"\n  🤖 {response}\n")


if __name__ == "__main__":
    main()
