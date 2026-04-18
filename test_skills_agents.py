#!/usr/bin/env python3
"""
MaxBot Skills and Agents - 功能测试脚本

测试所有新实现的技能和 Agent 是否能正常工作
"""

import sys
import os

# 添加 maxbot 到路径
sys.path.insert(0, '/root/maxbot')

print("=" * 60)
print("🧪 MaxBot Skills and Agents - 功能测试")
print("=" * 60)
print()

# 测试计数
total_tests = 0
passed_tests = 0
failed_tests = 0

def run_test(test_name, test_func):
    """运行单个测试"""
    global total_tests, passed_tests, failed_tests
    total_tests += 1
    
    try:
        print(f"▶️  测试 {test_name}...")
        test_func()
        print(f"✅ {test_name} - 通过")
        passed_tests += 1
        return True
    except Exception as e:
        print(f"❌ {test_name} - 失败: {str(e)}")
        failed_tests += 1
        return False
    finally:
        print()

# ============================================================================
# 测试 1: Planner Agent
# ============================================================================

def test_planner_agent_basic():
    """测试 Planner Agent 基本功能"""
    from maxbot.agents.planner_agent import PlannerAgent
    
    # 创建 Planner Agent
    planner = PlannerAgent()
    
    # 验证属性
    assert planner.name == "planner", "Agent 名称不正确"
    assert len(planner.skills) > 0, "Agent 没有技能"
    
    print(f"   ✓ Planner Agent 创建成功")
    print(f"   ✓ Agent 名称: {planner.name}")
    print(f"   ✓ 拥有 {len(planner.skills)} 个技能: {', '.join(planner.skills)}")

def test_planner_agent_simple_task():
    """测试 Planner Agent 处理简单任务"""
    from maxbot.agents.planner_agent import PlannerAgent
    
    planner = PlannerAgent()
    
    # 创建简单任务计划
    plan = planner.create_plan("Fix memory leak")
    
    # 验证计划
    assert plan is not None, "计划为空"
    assert len(plan) > 0, "计划内容为空"
    assert "memory leak" in plan.lower(), "计划不包含任务描述"
    
    print(f"   ✓ 简单任务计划创建成功")
    print(f"   ✓ 计划长度: {len(plan)} 字符")

def test_planner_agent_medium_task():
    """测试 Planner Agent 处理中等复杂度任务"""
    from maxbot.agents.planner_agent import PlannerAgent
    
    planner = PlannerAgent()
    
    # 创建中等复杂度任务计划
    plan = planner.create_plan("Add user authentication to API")
    
    # 验证计划
    assert plan is not None, "计划为空"
    assert "Authentication" in plan or "auth" in plan.lower(), "计划缺少认证相关内容"
    assert "phase" in plan.lower(), "计划缺少阶段划分"
    
    print(f"   ✓ 中等复杂度任务计划创建成功")
    print(f"   ✓ 计划包含认证相关内容")

def test_planner_agent_complex_task():
    """测试 Planner Agent 处理复杂任务"""
    from maxbot.agents.planner_agent import PlannerAgent
    
    planner = PlannerAgent()
    
    # 创建复杂任务计划
    plan = planner.create_plan("Refactor gateway to use async/await")
    
    # 验证计划
    assert plan is not None, "计划为空"
    assert len(plan) > 100, "复杂任务计划太短"
    
    print(f"   ✓ 复杂任务计划创建成功")
    print(f"   ✓ 计划长度: {len(plan)} 字符")

def test_planner_agent_complexity_estimation():
    """测试复杂度估算"""
    from maxbot.agents.planner_agent import PlannerAgent
    
    planner = PlannerAgent()
    
    # 测试不同任务的复杂度
    low = planner._estimate_complexity("Fix typo")
    medium = planner._estimate_complexity("Add feature")
    high = planner._estimate_complexity("Major refactoring")
    
    assert low in ["low", "medium"], "低复杂度任务估算错误"
    assert medium in ["medium", "high"], "中等复杂度任务估算错误"
    assert high == "high", "高复杂度任务估算错误"
    
    print(f"   ✓ 复杂度估算正确")
    print(f"   ✓ 低复杂度: {low}")
    print(f"   ✓ 中等复杂度: {medium}")
    print(f"   ✓ 高复杂度: {high}")

# ============================================================================
# 测试 2: Security Reviewer Agent
# ============================================================================

def test_security_reviewer_agent_basic():
    """测试 Security Reviewer Agent 基本功能"""
    from maxbot.agents.security_reviewer_agent import SecurityReviewerAgent
    
    # 创建 Security Reviewer Agent
    reviewer = SecurityReviewerAgent()
    
    # 验证属性
    assert reviewer.name == "security-reviewer", "Agent 名称不正确"
    assert len(reviewer.skills) > 0, "Agent 没有技能"
    
    print(f"   ✓ Security Reviewer Agent 创建成功")
    print(f"   ✓ Agent 名称: {reviewer.name}")
    print(f"   ✓ 拥有 {len(reviewer.skills)} 个技能")

def test_security_reviewer_safe_code():
    """测试审查安全代码"""
    from maxbot.agents.security_reviewer_agent import SecurityReviewerAgent
    
    reviewer = SecurityReviewerAgent()
    
    # 安全代码示例
    safe_code = '''
def get_user(user_id):
    """Get user by ID with parameterized query"""
    return db.execute("SELECT * FROM users WHERE id = %s", (user_id,))
'''
    
    # 审查代码
    results = reviewer.review_code(safe_code, "safe_code.py")
    
    # 验证结果
    assert results is not None, "审查结果为空"
    assert "summary" in results, "缺少摘要"
    assert results["summary"]["critical"] == 0, "安全代码不应有 critical 问题"
    
    print(f"   ✓ 安全代码审查成功")
    print(f"   ✓ 发现 {results['summary']['total']} 个问题")

def test_security_reviewer_vulnerable_code():
    """测试审查有漏洞的代码"""
    from maxbot.agents.security_reviewer_agent import SecurityReviewerAgent
    
    reviewer = SecurityReviewerAgent()
    
    # 有漏洞的代码示例
    vulnerable_code = '''
def get_user(user_id):
    """Get user by ID - SQL INJECTION VULNERABILITY"""
    api_key = "sk-proj-1234567890"  # Hardcoded secret
    query = f"SELECT * FROM users WHERE id = {user_id}"  # SQL injection
    return db.execute(query)
'''
    
    # 审查代码
    results = reviewer.review_code(vulnerable_code, "vulnerable.py")
    
    # 验证结果
    assert results is not None, "审查结果为空"
    assert results["summary"]["critical"] > 0, "应检测到 critical 问题"
    assert len(results["findings"]) > 0, "应检测到安全问题"
    
    print(f"   ✓ 漏洞代码审查成功")
    print(f"   ✓ 检测到 {results['summary']['critical']} 个 critical 问题")
    print(f"   ✓ 总计 {results['summary']['total']} 个问题")

def test_security_reviewer_pattern_detection():
    """测试安全模式检测"""
    from maxbot.agents.security_reviewer_agent import SecurityReviewerAgent
    
    reviewer = SecurityReviewerAgent()
    
    # 测试各种安全模式
    test_code = '''
api_key = "sk-proj-test"  # Hardcoded secret
password = "123456"  # Hardcoded password
import os
os.system("rm -rf /")  # Command injection
hashlib.md5("data")  # Weak crypto
'''
    
    # 审查代码
    results = reviewer.review_code(test_code, "test_patterns.py")
    
    # 验证检测到多种问题
    assert results["summary"]["total"] >= 2, "应检测到多种安全问题"
    
    # 检查问题类型
    issue_types = [f["type"] for f in results["findings"]]
    print(f"   ✓ 检测到的问题类型: {', '.join(set(issue_types))}")

# ============================================================================
# 测试 3: Security Review System
# ============================================================================

def test_security_review_system_basic():
    """测试 Security Review System 基本功能"""
    from maxbot.security.security_review_system import SecurityReviewSystem
    
    # 创建 Security Review System
    system = SecurityReviewSystem("/root/maxbot")
    
    # 验证属性
    assert system is not None, "系统创建失败"
    assert len(system.security_checks) > 0, "系统没有安全检查配置"
    
    print(f"   ✓ Security Review System 创建成功")
    print(f"   ✓ 配置了 {len(system.security_checks)} 个安全检查")

def test_security_review_system_policy():
    """测试安全策略"""
    from maxbot.security.security_review_system import SecurityReviewSystem
    
    system = SecurityReviewSystem("/root/maxbot")
    
    # 验证安全策略
    assert system.security_policy is not None, "安全策略为空"
    assert "fail_on_critical" in system.security_policy, "缺少 fail_on_critical 策略"
    assert "fail_on_high" in system.security_policy, "缺少 fail_on_high 策略"
    
    print(f"   ✓ 安全策略配置成功")
    print(f"   ✓ Fail on critical: {system.security_policy['fail_on_critical']}")
    print(f"   ✓ Fail on high: {system.security_policy['fail_on_high']}")

def test_security_review_system_report_generation():
    """测试报告生成"""
    from maxbot.security.security_review_system import SecurityReviewSystem
    
    system = SecurityReviewSystem("/root/maxbot")
    
    # 模拟扫描结果
    mock_results = {
        "checks_run": ["test"],
        "total_issues": 2,
        "by_severity": {"critical": 1, "high": 1, "medium": 0, "low": 0},
        "findings": [
            {"check": "test", "severity": "critical", "message": "Test critical issue"},
            {"check": "test", "severity": "high", "message": "Test high issue"}
        ],
        "passed": False
    }
    
    # 生成报告
    report = system.format_security_report(mock_results)
    
    # 验证报告
    assert report is not None, "报告为空"
    assert len(report) > 0, "报告内容为空"
    assert "critical" in report.lower(), "报告缺少 critical 信息"
    assert "high" in report.lower(), "报告缺少 high 信息"
    
    print(f"   ✓ 报告生成成功")
    print(f"   ✓ 报告长度: {len(report)} 字符")

# ============================================================================
# 主测试流程
# ============================================================================

def main():
    """运行所有测试"""
    
    print("📋 测试计划:")
    print()
    
    # Planner Agent 测试
    print("🤖 Planner Agent 测试:")
    run_test("Planner Agent 基本功能", test_planner_agent_basic)
    run_test("Planner Agent 简单任务", test_planner_agent_simple_task)
    run_test("Planner Agent 中等复杂度任务", test_planner_agent_medium_task)
    run_test("Planner Agent 复杂任务", test_planner_agent_complex_task)
    run_test("Planner Agent 复杂度估算", test_planner_agent_complexity_estimation)
    
    # Security Reviewer Agent 测试
    print("🔒 Security Reviewer Agent 测试:")
    run_test("Security Reviewer Agent 基本功能", test_security_reviewer_agent_basic)
    run_test("Security Reviewer 安全代码", test_security_reviewer_safe_code)
    run_test("Security Reviewer 漏洞代码", test_security_reviewer_vulnerable_code)
    run_test("Security Reviewer 模式检测", test_security_reviewer_pattern_detection)
    
    # Security Review System 测试
    print("🔐 Security Review System 测试:")
    run_test("Security Review System 基本功能", test_security_review_system_basic)
    run_test("Security Review System 策略", test_security_review_system_policy)
    run_test("Security Review System 报告生成", test_security_review_system_report_generation)
    
    # 打印测试总结
    print("=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    print(f"总测试数: {total_tests}")
    print(f"✅ 通过: {passed_tests}")
    print(f"❌ 失败: {failed_tests}")
    print(f"📈 成功率: {(passed_tests/total_tests*100):.1f}%")
    print()
    
    if failed_tests == 0:
        print("🎉 所有测试通过！")
        return 0
    else:
        print(f"⚠️  {failed_tests} 个测试失败")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
