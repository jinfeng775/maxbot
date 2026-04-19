# MaxBot Full Evolution Gap List

**生成时间：** 2026-04-19  
**来源：** fresh audit（Phase 1 ~ Phase 7）

---

## P0：当前仍应优先处理

### 1. tracked `__pycache__/` / `.pyc` 仍污染仓库状态
- 当前 git 仍跟踪多处字节码缓存文件
- 会放大 `git status` 噪音并干扰后续 fresh audit

### 2. 历史 phase 文档仍保留较多旧时代正文
本轮已完成：
- 主计划 / 进度 / ECC 对齐文档第一轮收口
- `docs/phase7-hook-audit.md` 重写
- Phase 1 缺件回补

但仍有一些文档正文保留：
- 旧阶段状态
- 旧技能名称（如 `code-generation`）
- 旧“下一步计划”语境

这些内容虽已通过“历史文档说明”降低误导风险，后续仍可继续精修或归档。

### 3. Phase 6 legacy 兼容层仍待进一步压缩
- 当前已不影响“完成”口径
- 但 runtime 主链与 legacy 层并存，仍属后续可维护性收敛项

---

## P1：建议后续继续推进

### 4. Phase 2 仍缺更完整 acceptance suite
当前已有：
- `tests/test_phase2.py`
- `tests/test_phase2_skill_runtime.py`

但后续仍可继续补：
- 技能发现与匹配排序
- repo skills / user skills 冲突覆盖
- 注入预算与回退路径
- 热加载 / 安装 / 失效恢复

### 5. Phase 4 双层记忆边界说明仍可继续细化
当前代码已具备：
- 内置分层 Memory 主线
- MemPalace `mine / search / wake-up` PoC

但仍可继续明确：
- 何时走内置 Memory
- 何时走外接 MemPalace
- 二者在 prompt 注入 / 治理 / 检索上的职责边界

### 6. 历史文档归档策略尚未建立
当前已有多份“历史快照文档”，后续可考虑：
- 集中归档到 `archive/`
- 或统一 frontmatter 标注 `historical_snapshot: true`
- 或增加 doc-lint 规则避免历史文档被误当当前状态

---

## P2：中长期可维护性

### 7. 建议单独做一次仓库卫生清理
适合单独提交：
- tracked `.pyc` / `__pycache__` 清理
- 其他历史缓存噪音删除

建议命令：
```bash
git rm --cached -r maxbot/__pycache__ maxbot/core/__pycache__ maxbot/tools/__pycache__ tests/__pycache__
find . -type f \( -name '*.pyc' -o -path '*/__pycache__/*' \) -delete
```

### 8. 建议建立 doc consistency 机制
例如：
- 定期检查 `MAXBOT_EVOLUTION_PLAN.md` / `EVOLUTION_PROGRESS.md` / `ECC_LEARNING_PLAN.md`
- 对“当前状态”“下一步”“阶段统计”建立简单一致性校验

---

## 建议执行顺序

1. 提交本轮 Phase 1~7 fresh audit 收口
2. 单独提交 tracked `.pyc` / `__pycache__` 清理
3. 再继续推进 Phase 8 后续实施
