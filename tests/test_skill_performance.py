"""
测试技能系统性能
"""

import sys
from pathlib import Path
import time

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.skills import SkillManager


def test_matching_performance():
    """测试技能匹配性能"""
    print("=" * 70)
    print("测试 1: 技能匹配性能")
    print("=" * 70)

    sm = SkillManager()
    skills = sm.list_skills()

    print(f"✅ 加载 {len(skills)} 个技能")

    # 测试消息
    test_messages = [
        "帮我 review 代码",
        "创建一个新的 git 分支",
        "分析这个项目",
        "搜索今天的新闻",
        "代码格式化",
        "翻译这段文本",
        "向用户打招呼",
    ]

    # 第一次运行（冷启动）
    print("\n🧪 冷启动测试：")
    start_time = time.time()
    for msg in test_messages:
        matched = sm.match_skills(msg)
    cold_time = time.time() - start_time
    print(f"   处理 {len(test_messages)} 条消息: {cold_time:.4f} 秒")
    print(f"   平均每条: {cold_time / len(test_messages):.4f} 秒")

    # 第二次运行（热启动，使用缓存）
    print("\n🧪 热启动测试（使用缓存）：")
    start_time = time.time()
    for msg in test_messages:
        matched = sm.match_skills(msg)
    hot_time = time.time() - start_time
    print(f"   处理 {len(test_messages)} 条消息: {hot_time:.4f} 秒")
    print(f"   平均每条: {hot_time / len(test_messages):.4f} 秒")
    print(f"   加速比: {cold_time / hot_time:.2f}x")

    # 缓存统计
    cache_info = sm.match_skills.cache_info()
    print(f"\n📊 缓存统计:")
    print(f"   缓存命中: {cache_info.hits}")
    print(f"   缓存未命中: {cache_info.misses}")
    print(f"   当前缓存大小: {cache_info.currsize}")

    print("\n✅ 技能匹配性能测试通过\n")


def test_injection_performance():
    """测试技能内容注入性能"""
    print("=" * 70)
    print("测试 2: 技能内容注入性能")
    print("=" * 70)

    sm = SkillManager()

    test_messages = [
        "帮我 review 代码",
        "创建一个新的 git 分支",
        "分析这个项目",
    ]

    print(f"✅ 准备测试 {len(test_messages)} 条消息")

    # 测试注入性能
    start_time = time.time()
    for msg in test_messages:
        content = sm.get_injectable_content(msg, max_chars=4000)
    injection_time = time.time() - start_time

    print(f"   处理时间: {injection_time:.4f} 秒")
    print(f"   平均每条: {injection_time / len(test_messages):.4f} 秒")

    print("\n✅ 技能内容注入性能测试通过\n")


def test_index_performance():
    """测试索引构建性能"""
    print("=" * 70)
    print("测试 3: 索引构建性能")
    print("=" * 70)

    sm = SkillManager()
    skills = sm.list_skills()

    print(f"✅ 加载 {len(skills)} 个技能")

    # 测试索引构建
    start_time = time.time()
    sm._build_index()
    build_time = time.time() - start_time

    print(f"   索引构建时间: {build_time:.4f} 秒")
    print(f"   索引条目数: {len(sm._skills_index)}")

    print("\n✅ 索引构建性能测试通过\n")


def test_stats():
    """测试统计信息"""
    print("=" * 70)
    print("测试 4: 统计信息")
    print("=" * 70)

    sm = SkillManager()
    stats = sm.get_stats()

    print(f"✅ 技能统计信息:")
    print(f"   总技能数: {stats['total_skills']}")
    print(f"   总触发词数: {stats['total_triggers']}")
    print(f"   类别: {', '.join(stats['categories'])}")
    print(f"   缓存大小: {stats['cache_size']}")

    print("\n✅ 统计信息测试通过\n")


def test_reload_performance():
    """测试重新加载性能"""
    print("=" * 70)
    print("测试 5: 重新加载性能")
    print("=" * 70)

    sm = SkillManager()

    # 测试重新加载
    start_time = time.time()
    sm.reload_skills()
    reload_time = time.time() - start_time

    print(f"   重新加载时间: {reload_time:.4f} 秒")
    print(f"   加载技能数: {len(sm.list_skills())}")

    print("\n✅ 重新加载性能测试通过\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("技能系统性能测试")
    print("=" * 70 + "\n")

    test_matching_performance()
    test_injection_performance()
    test_index_performance()
    test_stats()
    test_reload_performance()

    print("=" * 70)
    print("✅ 所有性能测试完成！")
    print("=" * 70)
