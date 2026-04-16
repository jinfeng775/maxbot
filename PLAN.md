# MaxBot 开发计划

> 自我学习、自我构建的超级智能体
> 
> 技术来源：Hermes + Claude Code + OpenClaw
> 
> 语言：Python 统一

---

## 总览

| 阶段 | 内容 | 状态 | 完成日期 |
|------|------|------|----------|
| Phase 0 | 项目骨架 & 核心引擎 | ✅ 已完成 | 2026-04-15 |
| Phase 1 | 工具系统完善 | ✅ 已完成 | 2026-04-15 |
| Phase 2 | 代码编辑引擎 | ✅ 已完成 | 2026-04-15 |
| Phase 3 | 多 Agent 编排 | ✅ 已完成 | 2026-04-15 |
| Phase 4 | Gateway 多平台 | ✅ 已完成 | 2026-04-15 |
| Phase 5 | 知识吸收系统 | ✅ 已完成 | 2026-04-16 |
| Phase 6 | 自我进化 + 审批委员会 | ✅ 已完成 | 2026-04-16 |
| Phase 7 | 插件 SDK | 🔲 未开始 | — |
| Phase 8 | 生产就绪 | 🔲 未开始 | — |

---

## Phase 0：项目骨架 ✅

**状态：已完成** `2026-04-15`

- [x] 项目结构设计（融合三家架构）
- [x] pyproject.toml 配置
- [x] 核心包初始化
- [x] Git 仓库初始化
- [x] 测试框架搭建

---

## Phase 1：核心引擎 & 工具系统 ✅

**状态：已完成** `2026-04-15`

### 1.1 Agent Loop ✅
- [x] `core/agent_loop.py` — 对话循环
  - [x] OpenAI 兼容 API 调用
  - [x] 工具调用解析 & 执行
  - [x] 消息格式统一（Message dataclass）
  - [x] 迭代控制（max_iterations）
  - [x] 回调机制（on_tool_start/end）

**参考来源：**
- Hermes `run_agent.py` — 核心循环、消息格式
- Claude Code — tool_use 流程、迭代控制

### 1.2 工具注册表 ✅
- [x] `core/tool_registry.py`
  - [x] ToolDef 数据类（name/description/parameters/handler/toolset）
  - [x] `@registry.tool()` 装饰器注册
  - [x] 自动扫描 `maxbot/tools/` 包
  - [x] OpenAI function calling schema 生成
  - [x] 工具调用 & 错误处理
  - [x] 热重载 `hot_reload()`
  - [x] 动态注册/卸载

**参考来源：**
- Hermes `tools/registry.py` — 装饰器 + 自动发现
- Claude Code `tools.ts` — 工具分类

### 1.3 持久记忆 ✅
- [x] `core/memory.py`
  - [x] SQLite 存储
  - [x] FTS5 全文搜索（+ LIKE 中文回退）
  - [x] CRUD 操作（set/get/delete/search/list）
  - [x] 分类管理（category）
  - [x] 导出文本格式（注入 system prompt）

**参考来源：**
- Hermes `hermes_state.py` — SQLite FTS5

### 1.4 上下文管理 ✅
- [x] `core/context.py`
  - [x] Token 估算（中英文混合）
  - [x] 消息统计
  - [x] 历史压缩（保留 system + 最近 N 条）
  - [x] 自动生成摘要

**参考来源：**
- Hermes `context_compressor.py`
- Claude Code `services/compact/`

### 1.5 内置工具 ✅
- [x] `tools/file_tools.py` — 5 个工具
  - [x] read_file / write_file / search_files / patch_file / list_files
- [x] `tools/shell_tools.py` — 2 个工具
  - [x] shell / exec_python
- [x] `tools/git_tools.py` — 5 个工具
  - [x] git_status / git_diff / git_log / git_commit / git_branch
- [x] `tools/web_tools.py` — 2 个工具
  - [x] web_search / web_fetch
- [x] `tools/code_execution.py` — execute_code 沙箱
  - [x] 文件 RPC：沙箱脚本通过 maxbot_tools 模块调父进程工具
  - [x] 可用工具：read_file, write_file, search_files, shell, web_search 等
  - [x] 内置辅助：json_parse, shell_quote, retry
  - [x] 只返回 stdout，中间工具调用不进 context window

**参考来源：**
- Hermes `code_execution_tool.py` — UDS/文件 RPC 模式

**共 18+ 个工具，全部自动注册。**

### 1.6 CLI 交互界面 ✅
- [x] `cli/__init__.py` — 交互式 REPL
- [x] `cli/main.py` — 入口点

### 1.7 会话管理 ✅
- [x] `sessions/__init__.py` — SessionStore（SQLite）

### 1.8 测试 ✅
- [x] tests/test_core.py — 16 个测试
- [x] tests/test_execute_code.py — 8 个测试（含多步工具链）

---

## Phase 2：代码编辑引擎 ✅

**状态：已完成** `2026-04-15`
**参考来源：Claude Code `FileEditTool/` + `NotebookEditTool/`**

### 2.1 精确代码编辑器 ✅
- [x] `tools/code_editor.py`
  - [x] old_string / new_string 精确替换（CC 风格）
  - [x] Diff 预览（替换前展示差异）
  - [x] 批量编辑（code_edit_multi）
  - [x] 多处匹配检测（不盲目替换）
  - [x] 撤销支持（文件历史记录）
  - [x] 引号标准化（花引号 ↔ 直引号）
  - [x] 结构化 patch 生成

### 2.2 Notebook 编辑 ✅
- [x] `tools/notebook_tools.py`
  - [x] 读取 .ipynb 文件
  - [x] 编辑指定 cell
  - [x] 插入/删除 cell
  - [x] 列出 cell 信息

### 2.3 代码分析 ✅
- [x] `tools/code_analysis.py`
  - [x] AST 解析（Python ast 模块）
  - [x] 函数/类/导入提取
  - [x] 项目结构分析
  - [x] 多语言启发式分析（JS/TS/Go/Rust）

### 2.4 测试 ✅
- [x] tests/test_phase2.py — 29 个测试

---

## Phase 3：多 Agent 编排 ✅

**状态：已完成** `2026-04-15`
**参考来源：Claude Code `AgentTool/` + `coordinator/` + `runAgent.ts`**

### 3.1 子 Agent 委派 ✅
- [x] `multi_agent/__init__.py` — AgentDelegate
  - [x] 从主 Agent 派生子 Agent（隔离上下文）
  - [x] 工具子集控制（allowed_tools 白名单）
  - [x] system prompt 继承 + 扩展
  - [x] 同步执行 `run()` + 异步后台执行 `run_background()`

### 3.2 Coordinator 模式 ✅
- [x] Coordinator — 任务编排器
  - [x] 子任务定义（SubTask，含 depends_on）
  - [x] 按依赖关系排序执行
  - [x] 并行执行无依赖任务
  - [x] 自动拆分 `orchestrate_auto()`（LLM 驱动）

### 3.3 Worker Pool ✅
- [x] WorkerPool — 管理多个并行 Worker

### 3.4 工具 Schema ✅
- [x] spawn_agent / spawn_agents_parallel / agent_status

### 3.5 测试 ✅
- [x] tests/test_phase3.py — 16 个测试

---

## Phase 4：Gateway 多平台 ✅

**状态：已完成** `2026-04-15`
**参考来源：OpenClaw `gateway/` + `channels/` + `plugins/`**

### 4.1 Gateway 服务 ✅
- [x] `gateway/server.py` — FastAPI HTTP 服务
  - [x] REST API：/chat, /tools, /sessions, /batch
  - [x] WebSocket 实时对话
  - [x] API Key 认证鉴权
  - [x] 会话管理（创建/重置/删除/列表）

### 4.2 渠道适配器 ✅
- [x] `gateway/channels/base.py` — ChannelAdapter 基类
- [x] `gateway/channels/http_channel.py` — HTTP 渠道
- [x] `gateway/channels/telegram.py` — Telegram Bot 渠道

### 4.3 测试 ✅
- [x] tests/test_phase4.py — 15 个测试

---

## Phase 5：知识吸收系统 ⭐ 核心创新

**状态：✅ 已完成** `2026-04-16`
**来源：原创（三家都没有）**

### 5.1 代码解析引擎
- [x] `knowledge/code_parser.py`
  - [x] 多语言解析
    - [x] Python — stdlib ast 模块（精确）
    - [x] JavaScript / TypeScript — 正则启发式
    - [x] Go — 正则启发式
    - [x] Rust — 正则启发式
  - [x] 项目结构扫描（目录树、语言分布、依赖图）
  - [x] 入口点识别（main 函数、__main__、CLI 入口）
  - [x] 函数签名提取（参数、类型、默认值、返回类型）
  - [x] 类/方法/装饰器提取
  - [x] 项目摘要生成（summarize_structure）

### 5.2 能力抽象器
- [x] `knowledge/capability_extractor.py`
  - [x] 启发式提取（基于 docstring + 函数签名）
  - [x] LLM 驅動分析（`extract_from_repo(use_llm=True)`）
  - [x] 自动生成工具定义（JSON Schema 格式）
  - [x] **handler 代码生成（真正可执行）**
    - [x] 自动添加 absorbed repo 到 sys.path
    - [x] from module import function 直接调用
    - [x] 参数正确映射 + 返回值 JSON 序列化
  - [x] 批量处理（整个项目一次分析）
  - [x] 指纹去重

### 5.3 技能工厂
- [x] `knowledge/skill_factory.py`
  - [x] 自动生成 SKILL.md（含 YAML frontmatter）
  - [x] 自动生成 handler 脚本
  - [x] 版本管理（技能更新时保留旧版 +1）
  - [x] 冲突检测（同名技能 + 同源检测）

### 5.4 沙箱验证
- [x] `knowledge/sandbox_validator.py`
  - [x] 静态安全扫描（危险模式检测：eval/subprocess/shutil 等）
  - [x] AST 级安全分析（危险函数调用检测）
  - [x] 语法验证
  - [x] 自动化测试生成
  - [x] 沙箱执行（subprocess 隔离 + timeout）

### 5.5 自动注册
- [x] `knowledge/auto_register.py`
  - [x] 验证通过后自动注册到工具系统
  - [x] 从技能目录批量注册
  - [x] 吸收工具集管理（absorbed toolset）

### 5.6 吸收流程（端到端）
```
输入：本地路径
  │
  ▼
代码解析 → AST + 项目结构 + 入口点
  │
  ▼
能力提取 → 启发式/LLM → 工具定义 + 可执行 handler
  │
  ▼
技能生成 → SKILL.md + handler.py + meta.json
  │
  ▼
安全验证 → 模式检测 + 语法检查 + 沙箱执行
  │
  ▼
自动注册 → 注册到 toolset="absorbed" → 可用
```

### 5.7 测试
- [x] tests/test_knowledge.py — 53 个测试
  - [x] 多语言解析测试（Python/JS/TS/Go/Rust）
  - [x] 项目扫描 + 摘要生成
  - [x] 能力提取 + 去重
  - [x] 技能生成 + 版本冲突
  - [x] 安全扫描 + 语法验证 + 沙箱执行
  - [x] 自动注册 + 工具调用
  - [x] 端到端吸收测试

---

## Phase 6：自我进化 + 审批委员会

**状态：✅ 已完成** `2026-04-16`
**来源：原创**

### 6.1 自我评估
- [x] `knowledge/self_analyzer.py`
  - [x] 能力盘点（工具/技能/领域覆盖）
  - [x] LLM 驱动的能力缺口分析（不是找 bug，是找"不能做什么"）
  - [x] 支持失败历史、用户模式、对标差距 3 种数据源
  - [x] CapabilityGap 数据结构（domain/priority/evidence/solution）

### 6.2 进化审批委员会
- [x] `knowledge/review_board.py`
  - [x] 5 个独立评审员（能力/安全/架构/质量/用户价值）
  - [x] 每个评审员有独立 system prompt 和上下文
  - [x] 独立 LLM 调用，互不干扰
  - [x] 加权投票（信心高的评审员权重更大）
  - [x] 三档裁决：approve / reject / revise
  - [x] 可配置 quorum 和 approval_threshold

### 6.3 进化循环
- [x] `knowledge/self_improver.py`
  - [x] SelfEvolver — 核心循环：评估→吸收→审批→注册
  - [x] 自动匹配知识源（按领域/关键词）
  - [x] 调用 Phase 5 知识吸收系统
  - [x] 审批通过后注册为 evolved_* 工具集
  - [x] 进化历史记录（JSONL）

### 6.4 测试
- [x] tests/test_self_improve.py — 25 个测试

---

## Phase 7：插件 SDK

**状态：🔲 未开始**
**参考来源：OpenClaw `plugin-sdk/` + `extensions/`**

### 7.1 插件基类
- [ ] `plugins/base.py`
  - [ ] Plugin 基类（init / activate / deactivate）
  - [ ] 插件 Manifest（YAML 声明）
  - [ ] 能力声明（tools / channels / providers / skills）
  - [ ] 依赖管理

### 7.2 插件发现 & 加载
- [ ] `plugins/loader.py`
  - [ ] 目录扫描
  - [ ] Manifest 验证
  - [ ] 动态导入
  - [ ] 依赖解析
  - [ ] 冲突检测

### 7.3 内置插件示例
- [ ] `plugins/examples/`
  - [ ] 示例工具插件
  - [ ] 示例渠道插件
  - [ ] 示例 Provider 插件

### 7.4 插件管理 CLI
- [ ] `maxbot plugins list`
- [ ] `maxbot plugins install <name>`
- [ ] `maxbot plugins enable/disable <name>`

---

## Phase 8：生产就绪

**状态：🔲 未开始**

### 8.1 安全加固
- [ ] 工具执行沙箱（Docker / gVisor）
- [ ] 敏感操作审批（写文件/执行命令需确认）
- [ ] API Key 安全存储（keyring）
- [ ] 日志脱敏

### 8.2 性能优化
- [ ] 异步 I/O（aiohttp / httpx）
- [ ] 工具结果缓存
- [ ] 连接池
- [ ] Token 预算管理

### 8.3 可观测性
- [ ] 结构化日志
- [ ] 指标收集（调用次数、延迟、错误率）
- [ ] 追踪（可选 OpenTelemetry）

### 8.4 文档
- [ ] API 文档（自动生成）
- [ ] 使用指南
- [ ] 贡献指南
- [ ] 插件开发指南

### 8.5 打包 & 发布
- [ ] PyPI 发布
- [ ] Docker 镜像
- [ ] 一键安装脚本
- [ ] CI/CD（GitHub Actions）

---

## 技术债务 & 已知问题

| 问题 | 严重程度 | 说明 |
|------|----------|------|
| JS/TS/Go/Rust 用正则解析而非 tree-sitter | 中 | 够用，但边界 case 会漏 |
| 沙箱验证用 subprocess 而非 Docker | 中 | 无资源隔离，仅超时控制 |
| LLM 分析路径需手动传 llm_client | 低 | 默认走启发式，LLM 是 opt-in |
| 无异步支持（全同步） | 中 | Phase 8 考虑 |

---

## 依赖关系图

```
Phase 0 ✅ ──→ Phase 1 ✅ ──→ Phase 2（代码编辑）✅
                    │
                    ├──→ Phase 3（多 Agent）✅──→ Phase 5（知识吸收）✅
                    │                                    │
                    ├──→ Phase 4（Gateway）✅            ├──→ Phase 6（自我进化）✅
                    │                                    │
                    └──→ Phase 7（插件 SDK）←────────────┘
                                         │
                                         └──→ Phase 8（生产就绪）
```

---

## 当前进度

```
[████████████████████░] Phase 0-6 完成 | 190 tests
当前阶段：Phase 7 — 插件 SDK
下一步：Plugin 基类 + 插件发现加载 + 管理 CLI
```

---

*最后更新：2026-04-16*
*项目路径：/root/maxbot/*
