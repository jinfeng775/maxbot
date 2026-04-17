# MaxBot 🤖

自我学习、自我构建的超级智能体。

## 设计理念

融合三大开源项目的精华：
- **Hermes** — 持久记忆、技能系统、多平台 Gateway
- **Claude Code** — 多 Agent 编排、精确代码编辑、Git 集成
- **OpenClaw** — 25+ 渠道适配器、插件 SDK、Gateway 架构

## 快速开始

```bash
# 安装
cd maxbot
pip install -e .

# 设置 API Key
export OPENAI_API_KEY="sk-..."
# 或用兼容接口
export MAXBOT_BASE_URL="http://localhost:8000/v1"

# 交互模式
maxbot

# 单次调用
maxbot "帮我搜索今天的新闻"

# 指定模型
maxbot -m gpt-4o --base-url https://api.openai.com/v1 "你好"
```

## 项目结构

```
maxbot/
├── core/                  # 核心引擎
│   ├── agent_loop.py      # Agent 循环（对话 → 工具调用 → 结果反馈）
│   ├── tool_registry.py   # 工具注册表（装饰器注册 + 自动发现）
│   ├── memory.py          # 持久记忆（SQLite + FTS5 全文搜索）
│   └── context.py         # 上下文管理（压缩、摘要、token 估算）
│
├── tools/                 # 内置工具
│   ├── file_tools.py      # 文件读写、搜索、补丁
│   ├── shell_tools.py     # Shell/Python 执行
│   ├── git_tools.py       # Git 操作
│   └── web_tools.py       # Web 搜索、网页抓取
│
├── gateway/               # 多平台网关（Phase 3）
│   ├── server.py          # HTTP/WS daemon
│   └── channels/          # 渠道适配器
│
├── multi_agent/           # 多 Agent 编排（Phase 2）
│   ├── coordinator.py     # 协调器
│   └── worker.py          # Worker Agent
│
├── knowledge/             # 知识吸收（Phase 4 — 核心创新）
│   ├── absorber.py        # 代码解析 → 能力提取
│   ├── skill_generator.py # 技能自动生成
│   └── sandbox.py         # 沙箱验证
│
├── skills/                # 可执行知识包
├── plugins/               # 插件扩展
├── cli/                   # CLI 界面
└── sessions/              # 会话管理
```

## 开发阶段

### Phase 1：骨架 ✅
- [x] Agent Loop（对话 + 工具调用循环）
- [x] 工具注册表（装饰器 + 自动发现 + 热加载）
- [x] 持久记忆（SQLite + FTS5）
- [x] 上下文管理
- [x] 内置工具（文件、Shell、Git、Web）
- [x] CLI 交互界面
- [x] **第一阶段重构完成**（详见 `docs/phase1_refactor_summary.md`）
  - 统一日志系统
  - 代码重复消除
  - 配置加载优化
  - 单元测试
  - 日志集成

### Phase 2：多 Agent ✅
- [x] 技能系统集成到 Agent 核心循环
- [x] 技能管理工具
- [x] 性能优化
- [x] 示例技能（code-review, git-workflow）
- [ ] Coordinator + Worker 编排（进行中）
- [ ] 子 Agent 委派
- [ ] 后台 Agent
- [ ] 精确代码编辑器

**第二阶段升级完成！**（详见 `docs/phase2_upgrade_summary.md`）

### Phase 3：Gateway（计划中）
- [ ] HTTP/WS Gateway
- [ ] 渠道适配器（微信、Telegram、Discord）
- [ ] 插件 SDK

### Phase 4：知识吸收（核心创新）
- [ ] tree-sitter 代码解析
- [ ] LLM 能力分析 → 工具生成
- [ ] 沙箱验证
- [ ] 自动注册

### Phase 5：自我改进（长期）
- [ ] 自我代码分析
- [ ] 补丁生成 + 测试
- [ ] 自动应用

## 添加工具

```python
# 在 maxbot/tools/ 下创建新文件
from maxbot.tools._registry import registry

@registry.tool(name="my_tool", description="我的工具")
def my_tool(arg: str) -> str:
    import json
    return json.dumps({"result": f"处理: {arg}"})
```

工具会自动发现并注册，无需修改任何配置。

## 许可证

MIT
