# MaxBot 开发计划

> 自我学习、自我构建的超级智能体
> 
> 技术来源：Hermes + Claude Code + OpenClaw
> 
> 语言：Python 统一

---

## 总览

| 阶段 | 内容 | 状态 | 预计周期 |
|------|------|------|----------|
| Phase 0 | 项目骨架 & 核心引擎 | ✅ 已完成 | — |
| Phase 1 | 工具系统完善 | ✅ 已完成 | — |
| Phase 2 | 代码编辑引擎 | ✅ 已完成 | — |
| Phase 3 | 多 Agent 编排 | ✅ 已完成 | — |
| Phase 4 | Gateway 多平台 | ✅ 已完成 | — |
| Phase 5 | 知识吸收系统 | 🔲 未开始 | 3-4 周 |
| Phase 6 | 自我改进 | 🔲 未开始 | 2-3 周 |
| Phase 7 | 插件 SDK | 🔲 未开始 | 2 周 |
| Phase 8 | 生产就绪 | 🔲 未开始 | 2 周 |

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
  - [x] read_file — 读取文件（行号、分页）
  - [x] write_file — 写入文件
  - [x] search_files — 正则搜索
  - [x] patch_file — 查找替换
  - [x] list_files — 列出目录
- [x] `tools/shell_tools.py` — 2 个工具
  - [x] shell — 执行 shell 命令
  - [x] exec_python — 执行 Python 代码
- [x] `tools/git_tools.py` — 5 个工具
  - [x] git_status / git_diff / git_log / git_commit / git_branch
- [x] `tools/web_tools.py` — 2 个工具
  - [x] web_search — Brave API + DuckDuckGo 回退
  - [x] web_fetch — 网页抓取 + HTML 清理

**共 14 个工具，全部自动注册。**

### 1.6 CLI 交互界面 ✅
- [x] `cli/__init__.py` — 交互式 REPL
  - [x] 参数解析（model/provider/base-url/api-key）
  - [x] 工具调用实时显示
  - [x] 内置命令（/tools /reset /quit）
- [x] `cli/main.py` — 入口点

### 1.7 会话管理 ✅
- [x] `sessions/__init__.py`
  - [x] SessionStore（SQLite）
  - [x] CRUD + 消息持久化

### 1.8 测试 ✅
- [x] `tests/test_core.py` — 16 个测试
  - [x] ToolRegistry — 6 个测试
  - [x] Memory — 5 个测试
  - [x] ContextManager — 4 个测试
  - [x] 全部通过 ✅

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
  - [x] 引号标准化测试
  - [x] 编辑逻辑测试（单次/批量/冲突检测）
  - [x] diff 生成测试
  - [x] snippet 测试
  - [x] 工具注册测试
  - [x] 端到端工具调用测试
  - [x] 代码分析测试

---

## Phase 3：多 Agent 编排 ✅

**状态：已完成** `2026-04-15`
**参考来源：Claude Code `AgentTool/` + `coordinator/` + `runAgent.ts`**

### 3.1 子 Agent 委派 ✅
- [x] `multi_agent/__init__.py` — AgentDelegate
  - [x] 从主 Agent 派生子 Agent（隔离上下文）
  - [x] 工具子集控制（allowed_tools 白名单）
  - [x] system prompt 继承 + 扩展
  - [x] 同步执行 `run()`
  - [x] 异步后台执行 `run_background()`（threading）

### 3.2 Coordinator 模式 ✅
- [x] Coordinator — 任务编排器
  - [x] 子任务定义（SubTask dataclass，含 depends_on）
  - [x] 按依赖关系排序执行
  - [x] 并行执行无依赖任务（max_parallel 控制）
  - [x] 依赖结果注入
  - [x] 最终结果汇总
  - [x] 自动拆分 `orchestrate_auto()`（LLM 驱动）

### 3.3 Worker Pool ✅
- [x] WorkerPool — 管理多个并行 Worker
  - [x] Worker 注册 & 任务提交
  - [x] 后台执行 + 状态跟踪
  - [x] wait / wait_all 等待
  - [x] 任务摘要生成

### 3.4 工具 Schema ✅
- [x] `multi_agent/tools.py`
  - [x] spawn_agent — 派生单个子 Agent
  - [x] spawn_agents_parallel — 并行派生多个
  - [x] agent_status — 查看状态

### 3.5 测试 ✅
- [x] tests/test_phase3.py — 16 个测试
  - [x] AgentTask 状态流转
  - [x] AgentDelegate 创建 & 工具过滤
  - [x] Coordinator 依赖注入
  - [x] WorkerPool 创建
  - [x] 工具 schema 验证
  - [x] 依赖图测试（顺序/并行/钻石）

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
  - [x] CORS 中间件
  - [x] 健康检查 /health

### 4.2 渠道适配器 ✅
- [x] `gateway/channels/base.py` — ChannelAdapter 基类
  - [x] 统一接口（connect/send/receive/disconnect）
  - [x] InboundMessage / OutboundMessage 数据类
  - [x] ChannelRegistry 注册表
  - [x] 广播支持
- [x] `gateway/channels/http_channel.py` — HTTP 渠道
- [x] `gateway/channels/telegram.py` — Telegram Bot 渠道
  - [x] Bot API 长轮询
  - [x] 消息解析（文本/图片/语音/文件）
  - [x] 发送消息

### 4.3 测试 ✅
- [x] tests/test_phase4.py — 15 个测试
  - [x] Gateway API 测试（health/tools/sessions/auth）
  - [x] 渠道注册表测试
  - [x] HTTP 渠道测试
  - [x] 数据模型测试

---

## Phase 5：知识吸收系统 ⭐ 核心创新

**状态：🔲 未开始**
**预计周期：3-4 周**
**来源：原创（三家都没有）**

### 5.1 代码解析引擎
- [ ] `knowledge/code_parser.py`
  - [ ] tree-sitter 多语言 AST 解析
    - [ ] Python
    - [ ] JavaScript / TypeScript
    - [ ] Go
    - [ ] Rust
  - [ ] 项目结构扫描（目录树、依赖图）
  - [ ] 入口点识别（main 函数、CLI 入口、API 端点）
  - [ ] 函数签名提取
  - [ ] 类型信息收集

### 5.2 能力抽象器
- [ ] `knowledge/capability_extractor.py`
  - [ ] LLM 驱动的代码分析
    - [ ] Prompt：这段代码能做什么？
    - [ ] Prompt：输入输出是什么？
    - [ ] Prompt：如何调用它？
  - [ ] 自动生成工具定义
    - [ ] name / description / parameters
    - [ ] handler 代码生成
  - [ ] 批量处理（整个项目一次分析）
  - [ ] 依赖关系映射

### 5.3 技能工厂
- [ ] `knowledge/skill_factory.py`
  - [ ] 自动生成 SKILL.md
  - [ ] 自动生成 handler 脚本
  - [ ] 版本管理（技能更新时保留旧版）
  - [ ] 冲突检测（同名技能）

### 5.4 沙箱验证
- [ ] `knowledge/sandbox.py`
  - [ ] Docker 容器隔离
  - [ ] 资源限制（CPU / 内存 / 网络）
  - [ ] 自动化测试生成 & 执行
  - [ ] 安全扫描（敏感操作检测）

### 5.5 自动注册
- [ ] `knowledge/auto_register.py`
  - [ ] 验证通过后自动注册到工具系统
  - [ ] 技能目录管理
  - [ ] 启用/禁用控制

### 5.6 吸收流程（端到端）
```
输入：GitHub URL 或本地路径
  │
  ▼
代码解析 → AST + 项目结构 + 入口点
  │
  ▼
能力抽象 → LLM 分析 → 工具定义 + handler 代码
  │
  ▼
沙箱验证 → Docker 执行 → 测试通过？
  │
  ├── 通过 → 自动注册 → 可用
  └── 失败 → 报告问题 → 人工干预或自动修复
```

### 5.7 测试
- [ ] tests/test_knowledge.py
  - [ ] 代码解析测试（多语言）
  - [ ] 能力提取测试
  - [ ] 沙箱执行测试
  - [ ] 端到端吸收测试（用真实开源项目）

---

## Phase 6：自我改进

**状态：🔲 未开始**
**预计周期：2-3 周**
**来源：原创（部分参考 Claude Code 的自我修改能力）**

### 6.1 自我代码分析
- [ ] `knowledge/self_analyzer.py`
  - [ ] 读取 MaxBot 自身源码
  - [ ] 识别代码质量问题
  - [ ] 识别性能瓶颈
  - [ ] 识别缺失功能（对比 OpenClaw/CC 的功能清单）

### 6.2 补丁生成
- [ ] `knowledge/patch_generator.py`
  - [ ] LLM 生成代码补丁
  - [ ] Diff 格式输出
  - [ ] 多文件补丁支持
  - [ ] 补丁冲突检测

### 6.3 自动测试 & 应用
- [ ] `knowledge/self_improver.py`
  - [ ] 生成补丁后自动运行测试套件
  - [ ] 测试通过 → 自动应用
  - [ ] 测试失败 → 回滚 + 报告
  - [ ] 改进历史记录（哪些改进生效了）

### 6.4 架构级改进（实验性）
- [ ] 对比学习（分析 OpenClaw/CC 的架构优势）
- [ ] 自动生成改进提案
- [ ] 人工审批流程（重大改动）

### 6.5 测试
- [ ] tests/test_self_improve.py
  - [ ] 自我分析测试
  - [ ] 补丁生成测试
  - [ ] 自动应用测试
  - [ ] 回滚测试

---

## Phase 7：插件 SDK

**状态：🔲 未开始**
**预计周期：2 周**
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
**预计周期：2 周**

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

| 问题 | 严重程度 | 计划修复阶段 |
|------|----------|-------------|
| FTS5 中文搜索依赖 LIKE 回退 | 低 | Phase 5（知识吸收时优化） |
| 无异步支持（全同步） | 中 | Phase 8（性能优化） |
| CLI 功能简单 | 低 | Phase 4（Gateway 完善后改进 CLI） |
| 无 provider 热切换 | 中 | Phase 4 |

---

## 依赖关系图

```
Phase 0 ✅ ──→ Phase 1 ✅ ──→ Phase 2（代码编辑）
                    │
                    ├──→ Phase 3（多 Agent）──→ Phase 5（知识吸收）
                    │                                    │
                    ├──→ Phase 4（Gateway）              ├──→ Phase 6（自我改进）
                    │                                    │
                    └──→ Phase 7（插件 SDK）←────────────┘
                                         │
                                         └──→ Phase 8（生产就绪）
```

---

## 当前进度

```
[████████████████░░░░] Phase 0-4 完成 | 5/8 阶段
当前阶段：Phase 5 — 知识吸收系统（核心创新）
下一步：实现代码解析 + 能力提取 + 工具自动生成
```

---

*最后更新：2026-04-15*
*项目路径：/root/maxbot/*
