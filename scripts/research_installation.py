#!/usr/bin/env python3
"""
安装前快速调研工具

帮助快速了解项目的前置条件和依赖关系。
"""

import sys
import re
import json
import subprocess
from pathlib import Path

def get_github_info(repo_url):
    """获取 GitHub 仓库信息"""
    try:
        # 解析仓库 URL
        if 'github.com' not in repo_url:
            return None
        
        parts = repo_url.split('github.com/')[-1].split('/')
        if len(parts) < 2:
            return None
        
        user, repo = parts[0], parts[1]
        
        # 获取 README
        readme_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/README.md"
        pyproject_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/pyproject.toml"
        
        import urllib.request
        import urllib.error
        
        try:
            with urllib.request.urlopen(readme_url, timeout=10) as response:
                readme = response.read().decode('utf-8')
        except urllib.error.URLError:
            readme = ""
        
        try:
            with urllib.request.urlopen(pyproject_url, timeout=10) as response:
                pyproject = response.read().decode('utf-8')
        except urllib.error.URLError:
            pyproject = ""
        
        return {
            "user": user,
            "repo": repo,
            "readme": readme,
            "pyproject": pyproject,
        }
    except Exception as e:
        print(f"❌ 获取 GitHub 信息失败: {e}")
        return None

def analyze_dependencies(pyproject):
    """分析依赖"""
    dependencies = []
    
    if not pyproject:
        return dependencies
    
    # 解析 pyproject.toml
    in_deps = False
    for line in pyproject.split('\n'):
        line = line.strip()
        
        if 'dependencies' in line.lower():
            in_deps = True
            continue
        
        if in_deps:
            if line.startswith(']') or line.startswith('['):
                if not line.startswith('"'):
                    in_deps = False
                    continue
            
            if line.startswith('"'):
                # 提取包名
                match = re.match(r'"([^>=<~]+)', line)
                if match:
                    dependencies.append(match.group(1))
    
    return dependencies

def analyze_api_requirements(readme):
    """分析 API 密钥要求"""
    api_keywords = {
        'openai': ['openai', 'gpt', 'api key', 'apikey', 'api-key'],
        'anthropic': ['anthropic', 'claude', 'api key', 'apikey'],
        'google': ['google', 'gemini', 'api key', 'apikey'],
        'other': ['api key', 'apikey', 'api-key', 'api_token'],
    }
    
    found_apis = {}
    readme_lower = readme.lower()
    
    for api_type, keywords in api_keywords.items():
        for keyword in keywords:
            if keyword in readme_lower:
                found_apis[api_type] = True
                break
    
    return list(found_apis.keys())

def analyze_system_dependencies(readme):
    """分析系统依赖"""
    system_keywords = {
        'hermes': ['hermes', 'hermes-agent'],
        'docker': ['docker', 'docker-compose'],
        'kubernetes': ['kubernetes', 'k8s'],
        'redis': ['redis'],
        'mongodb': ['mongodb', 'mongo'],
        'postgresql': ['postgresql', 'postgres'],
        'mysql': ['mysql'],
    }
    
    found_systems = {}
    readme_lower = readme.lower()
    
    for system, keywords in system_keywords.items():
        for keyword in keywords:
            if keyword in readme_lower:
                found_systems[system] = True
                break
    
    return list(found_systems.keys())

def check_current_environment():
    """检查当前环境"""
    env_info = {}
    
    # Python 版本
    try:
        result = subprocess.run(
            ['python3', '--version'],
            capture_output=True,
            text=True
        )
        env_info['python_version'] = result.stdout.strip()
    except Exception:
        env_info['python_version'] = 'Unknown'
    
    # 已安装的包
    try:
        result = subprocess.run(
            ['pip', 'list', '--format=json'],
            capture_output=True,
            text=True
        )
        packages = json.loads(result.stdout)
        env_info['installed_packages'] = [pkg['name'] for pkg in packages]
    except Exception:
        env_info['installed_packages'] = []
    
    # 环境变量
    env_info['env_vars'] = {
        'OPENAI_API_KEY': 'OPENAI_API_KEY' in subprocess.os.environ,
        'ANTHROPIC_API_KEY': 'ANTHROPIC_API_KEY' in subprocess.os.environ,
        'HERMES_AGENT_REPO': 'HERMES_AGENT_REPO' in subprocess.os.environ,
    }
    
    return env_info

def generate_report(repo_url):
    """生成调研报告"""
    print("=" * 70)
    print("🔍 安装前调研报告")
    print("=" * 70)
    
    # 获取 GitHub 信息
    print(f"\n📦 仓库: {repo_url}")
    github_info = get_github_info(repo_url)
    
    if not github_info:
        print("❌ 无法获取仓库信息")
        return
    
    print(f"✅ 成功获取仓库信息")
    
    # 分析依赖
    print(f"\n📋 依赖分析:")
    dependencies = analyze_dependencies(github_info['pyproject'])
    if dependencies:
        for dep in dependencies:
            print(f"  • {dep}")
    else:
        print("  ⚠️  未找到依赖信息")
    
    # 分析 API 要求
    print(f"\n🔑 API 密钥要求:")
    api_requirements = analyze_api_requirements(github_info['readme'])
    if api_requirements:
        for api in api_requirements:
            print(f"  • {api}")
    else:
        print("  ℹ️  未找到 API 密钥要求")
    
    # 分析系统依赖
    print(f"\n🖥️  系统依赖:")
    system_dependencies = analyze_system_dependencies(github_info['readme'])
    if system_dependencies:
        for system in system_dependencies:
            print(f"  • {system}")
    else:
        print("  ℹ️  未找到系统依赖")
    
    # 检查当前环境
    print(f"\n💻 当前环境:")
    env_info = check_current_environment()
    print(f"  • Python: {env_info['python_version']}")
    print(f"  • 已安装包: {len(env_info['installed_packages'])} 个")
    
    # 检查依赖是否已安装
    print(f"\n✅ 依赖检查:")
    missing_deps = []
    for dep in dependencies:
        if dep in env_info['installed_packages']:
            print(f"  ✅ {dep}: 已安装")
        else:
            print(f"  ❌ {dep}: 未安装")
            missing_deps.append(dep)
    
    # 检查 API 密钥是否已设置
    print(f"\n🔑 API 密钥检查:")
    if 'openai' in api_requirements:
        if env_info['env_vars']['OPENAI_API_KEY']:
            print(f"  ✅ OPENAI_API_KEY: 已设置")
        else:
            print(f"  ❌ OPENAI_API_KEY: 未设置")
    
    if 'anthropic' in api_requirements:
        if env_info['env_vars']['ANTHROPIC_API_KEY']:
            print(f"  ✅ ANTHROPIC_API_KEY: 已设置")
        else:
            print(f"  ❌ ANTHROPIC_API_KEY: 未设置")
    
    # 检查系统依赖
    print(f"\n🖥️  系统依赖检查:")
    if 'hermes' in system_dependencies:
        if env_info['env_vars']['HERMES_AGENT_REPO']:
            print(f"  ✅ HERMES_AGENT_REPO: 已设置")
        else:
            print(f"  ❌ HERMES_AGENT_REPO: 未设置")
    
    # 生成建议
    print(f"\n💡 安装建议:")
    
    if missing_deps:
        print(f"  ⚠️  缺少依赖: {', '.join(missing_deps)}")
        print(f"     建议先安装: pip install {' '.join(missing_deps)}")
    
    if 'openai' in api_requirements and not env_info['env_vars']['OPENAI_API_KEY']:
        print(f"  ⚠️  需要 OpenAI API 密钥")
        print(f"     建议设置: export OPENAI_API_KEY='sk-...'")
    
    if 'anthropic' in api_requirements and not env_info['env_vars']['ANTHROPIC_API_KEY']:
        print(f"  ⚠️  需要 Anthropic API 密钥")
        print(f"     建议设置: export ANTHROPIC_API_KEY='sk-ant-...'")
    
    if 'hermes' in system_dependencies and not env_info['env_vars']['HERMES_AGENT_REPO']:
        print(f"  ⚠️  需要 Hermes Agent")
        print(f"     建议先安装 Hermes Agent")
    
    # 保存报告
    report = {
        "repository": repo_url,
        "dependencies": dependencies,
        "api_requirements": api_requirements,
        "system_dependencies": system_dependencies,
        "current_environment": env_info,
        "missing_dependencies": missing_deps,
    }
    
    report_file = Path("installation_research_report.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 报告已保存到: {report_file}")
    
    print(f"\n" + "=" * 70)
    print("✅ 调研完成")
    print("=" * 70)

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法: python3 research_installation.py <github-repo-url>")
        print("示例: python3 research_installation.py https://github.com/NousResearch/hermes-agent-self-evolution")
        sys.exit(1)
    
    repo_url = sys.argv[1]
    generate_report(repo_url)

if __name__ == "__main__":
    main()
