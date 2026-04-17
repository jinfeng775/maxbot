# 安装前调研指南

## 📋 为什么需要调研？

在安装任何软件包或集成系统之前，必须先了解其前置条件和依赖关系。这可以避免：
- ❌ 安装后发现缺少必要的 API 密钥
- ❌ 需要安装其他依赖包
- ❌ 系统环境不兼容
- ❌ 浪费时间和资源

---

## 🔍 调研清单

### 1. 基本信息
- [ ] **项目名称**: 
- [ ] **GitHub 链接**: 
- [ ] **官方文档**: 
- [ ] **维护状态**: (活跃/维护中/已停止)

### 2. 前置条件
- [ ] **Python 版本要求**: 
- [ ] **操作系统要求**: 
- [ ] **依赖的包**: 
- [ ] **依赖的系统库**: 

### 3. API 密钥要求
- [ ] **是否需要 API 密钥**: (是/否)
- [ ] **需要的 API 类型**: (OpenAI/Anthropic/其他)
- [ ] **API 密钥获取方式**: 
- [ ] **API 费用**: 
- [ ] **是否有免费额度**: 

### 4. 依赖的系统
- [ ] **是否需要其他系统**: (是/否)
- [ ] **需要的系统名称**: 
- [ ] **系统安装要求**: 
- [ ] **系统配置要求**: 

### 5. 安装方式
- [ ] **安装方式**: (pip/pip install -e/其他)
- [ ] **安装命令**: 
- [ ] **是否需要编译**: (是/否)
- [ ] **安装时间估计**: 

### 6. 配置要求
- [ ] **是否需要配置文件**: (是/否)
- [ ] **配置文件位置**: 
- [ ] **环境变量要求**: 
- [ ] **配置示例**: 

### 7. 测试要求
- [ ] **是否有测试用例**: (是/否)
- [ ] **测试运行方式**: 
- [ ] **测试依赖**: 

### 8. 卸载方式
- [ ] **卸载命令**: 
- [ ] **需要清理的文件**: 
- [ ] **需要清理的配置**: 

---

## 📝 本次经验总结

### Hermes Agent Self-Evolution 调研（应该做的）

#### ✅ 已了解的信息
- 项目名称: Hermes Agent Self-Evolution
- GitHub 链接: https://github.com/NousResearch/hermes-agent-self-evolution
- Python 版本: >=3.10
- 依赖包: dspy, openai, pyyaml, click, rich

#### ❌ 未了解的信息（导致问题）
1. **API 密钥要求**
   - 需要 OpenAI API 密钥
   - 没有提前准备
   - 导致无法使用完整功能

2. **依赖的系统**
   - 依赖 Hermes Agent 仓库
   - 需要设置 HERMES_AGENT_REPO 环境变量
   - 没有提前安装 Hermes Agent

3. **安装复杂度**
   - 需要完整安装才能使用 DSPy + GEPA
   - 只能使用回退实现
   - 功能受限

4. **成本考虑**
   - 每次优化运行约 $2-10
   - 没有提前评估成本
   - 可能超出预算

---

## 🔬 调研方法

### 1. 查看 README
```bash
# 克隆或下载项目
git clone <repository-url>
cd <project-name>

# 查看 README
cat README.md

# 查看安装说明
cat INSTALL.md 2>/dev/null || cat docs/install.md 2>/dev/null
```

### 2. 查看 pyproject.toml 或 setup.py
```bash
# 查看依赖
cat pyproject.toml | grep -A 20 "dependencies"
cat setup.py | grep -A 20 "install_requires"
```

### 3. 查看文档
```bash
# 查看文档目录
ls docs/

# 查看快速开始
cat docs/quickstart.md 2>/dev/null
cat docs/getting_started.md 2>/dev/null
```

### 4. 查看 GitHub Issues
```bash
# 访问 GitHub Issues 页面
# 搜索 "install", "setup", "requirements", "api key"
```

### 5. 查看示例代码
```bash
# 查看示例目录
ls examples/

# 查看示例代码
cat examples/*.py | head -50
```

### 6. 测试安装
```bash
# 创建虚拟环境
python3 -m venv test_env
source test_env/bin/activate

# 尝试安装
pip install -e .

# 查看安装的包
pip list

# 检查导入
python3 -c "import <package_name>; print('OK')"

# 清理
deactivate
rm -rf test_env
```

---

## ✅ 安装前检查步骤

### 步骤 1: 查看项目信息
```bash
# 查看 README
curl -s https://raw.githubusercontent.com/<user>/<repo>/main/README.md | head -100

# 查看依赖
curl -s https://raw.githubusercontent.com/<user>/<repo>/main/pyproject.toml | grep -A 20 "dependencies"
```

### 步骤 2: 检查 API 密钥要求
```bash
# 搜索 API 相关内容
curl -s https://raw.githubusercontent.com/<user>/<repo>/main/README.md | grep -i "api"

# 查看配置示例
curl -s https://raw.githubusercontent.com/<user>/<repo>/main/docs/config.md 2>/dev/null
```

### 步骤 3: 检查依赖系统
```bash
# 搜索依赖相关内容
curl -s https://raw.githubusercontent.com/<user>/<repo>/main/README.md | grep -i "depend\|require\|hermes"
```

### 步骤 4: 检查当前环境
```bash
# Python 版本
python3 --version

# 已安装的包
pip list

# 环境变量
env | grep -i "api\|hermes\|repo"
```

### 步骤 5: 评估可行性
```bash
# 检查是否有必要的 API 密钥
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ 缺少 OPENAI_API_KEY"
else
    echo "✅ OPENAI_API_KEY 已设置"
fi

# 检查依赖系统
if command -v hermes &> /dev/null; then
    echo "✅ Hermes 已安装"
else
    echo "❌ Hermes 未安装"
fi
```

---

## 📋 调研模板

### 项目调研表

```markdown
# 项目名称: [项目名称]

## 基本信息
- **GitHub**: [链接]
- **文档**: [链接]
- **维护状态**: [活跃/维护中/已停止]
- **最后更新**: [日期]

## 前置条件
- **Python 版本**: [版本]
- **操作系统**: [系统]
- **依赖包**: [包列表]
- **系统库**: [库列表]

## API 密钥
- **是否需要**: [是/否]
- **API 类型**: [OpenAI/Anthropic/其他]
- **获取方式**: [链接]
- **费用**: [费用信息]
- **免费额度**: [额度信息]

## 依赖系统
- **是否需要**: [是/否]
- **系统名称**: [名称]
- **安装要求**: [要求]
- **配置要求**: [配置]

## 安装
- **安装方式**: [pip/其他]
- **安装命令**: [命令]
- **是否编译**: [是/否]
- **安装时间**: [时间]

## 配置
- **配置文件**: [位置]
- **环境变量**: [变量列表]
- **配置示例**: [示例]

## 测试
- **测试命令**: [命令]
- **测试依赖**: [依赖]

## 卸载

- **卸载命令**: [命令]
- **清理文件**: [文件列表]
- **清理配置**: [配置列表]

## 成本评估
- **安装成本**: [时间/资源]
- **运行成本**: [费用]
- **维护成本**: [时间/资源]

## 风险评估
- **兼容性风险**: [风险]
- **安全风险**: [风险]
- **维护风险**: [风险]

## 结论
- **是否推荐安装**: [是/否]
- **推荐理由**: [理由]
- **注意事项**: [注意事项]
```

---

## 🚀 下次安装流程

### 1. 调研阶段 (30分钟)
- [ ] 查看 README 和文档
- [ ] 检查前置条件
- [ ] 检查 API 密钥要求
- [ ] 检查依赖系统
- [ ] 评估填写调研表

### 2. 准备阶段 (15分钟)
- [ ] 准备 API 密钥（如果需要）
- [ ] 安装依赖系统（如果需要）
- [ ] 准备配置文件
- [ ] 创建备份

### 3. 测试阶段 (15分钟)
- [ ] 创建测试环境
- [ ] 尝试安装
- [ ] 运行测试
- [ ] 验证功能

### 4. 安装阶段 (10分钟)
- [ ] 正式安装
- [ ] 配置系统
- [ ] 验证安装
- [ ] 记录安装日志

### 5. 验证阶段 (10分钟)
- [ ] 功能测试
- [ ] 性能测试
- [ ] 兼容性测试
- [ ] 记录测试结果

---

## 📊 调研工具

### 自动调研脚本

```python
#!/usr/bin/env python3
"""
自动调研工具
"""

import requests
import re
import json
from pathlib import Path

def research_github_repo(repo_url):
    """调研 GitHub 仓库"""
    # 解析仓库 URL
    user, repo = repo_url.split('github.com/')[-1].split('/')
    
    # 获取 README
    readme_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/README.md"
    readme = requests.get(readme_url).text
    
    # 获取 pyproject.toml
    pyproject_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/pyproject.toml"
    pyproject = requests.get(pyproject_url).text
    
    # 分析依赖
    dependencies = []
    for line in pyproject.split('\n'):
        if 'dependencies' in line.lower():
            continue
        if line.strip().startswith('"'):
            dep = line.strip().strip('"').split('>')[0].split('<')[0].split('=')[0]
            dependencies.append(dep)
    
    # 分析 API 要求
    api_requirements = []
    api_keywords = ['api key', 'apikey', 'api-key', 'openai', 'anthropic']
    for keyword in api_keywords:
        if keyword.lower() in readme.lower():
            api_requirements.append(keyword)
    
    # 分析依赖系统
    system_dependencies = []
    system_keywords = ['hermes', 'docker', 'kubernetes', 'redis', 'mongodb']
    for keyword in system_keywords:
        if keyword.lower() in readme.lower():
            system_dependencies.append(keyword)
    
    return {
        "repository": repo_url,
        "dependencies": dependencies,
        "api_requirements": api_requirements,
        "system_dependencies": system_dependencies,
    }

# 使用示例
result = research_github_repo("https://github.com/NousResearch/hermes-agent-self-evolution")
print(json.dumps(result, indent=2))
```

---

## 📚 参考资料

### 通用调研资源
- [GitHub 官方文档](https://docs.github.com/)
- [Python 包索引 (PyPI)](https://pypi.org/)
- [OpenAI API 文档](https://platform.openai.com/docs)
- [Anthropic API 文档](https://docs.anthropic.com/)

### 调研工具
- [GitHub CLI](https://cli.github.com/)
- [pip-tools](https://github.com/jazzband/pip-tools)
- [pip-audit](https://github.com/pypa/pip-audit)

---

## ✅ 总结

### 调研的重要性
1. **避免意外**: 提前了解所有要求
2. **节省时间**: 避免反复安装卸载
3. **控制成本**: 提前评估费用
4. **降低风险**: 了解潜在问题

### 调研的关键点
1. ✅ 查看 README 和文档
2. ✅ 检查 API 密钥要求
3. ✅ 检查依赖系统
4. ✅ 评估成本和风险
5. ✅ 准备测试环境

### 下次安装前
1. 🔍 使用调研清单
2. 📝 填写调研表
3. ✅ 完成所有检查
4. 🚀 按流程安装

---

**文档版本**: 1.0  
**最后更新**: 2026-04-17  
**维护者**: MaxBot Team

---

## 💡 记住

> "在安装之前，先调研清楚。这能节省你大量的时间和麻烦。"

---

**下次安装前，请务必使用此调研指南！** 📋
