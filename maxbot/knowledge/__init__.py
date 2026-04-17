"""
知识吸收系统 — MaxBot 核心创新

Phase 5 实现

从代码仓库自动解析、提取能力、生成工具定义并验证注册。

架构:
```
输入: GitHub URL 或本地路径
  │
  ▼
CodeParser: 解析目标代码库结构 (code_parser.py)
  │
  ▼
CapabilityExtractor: 提取可复用功能 (capability_extractor.py)
  │
  ▼
SkillFactory: 生成 SKILL.md + handler (skill_factory.py)
  │
  ▼
SandboxValidator: 安全扫描 + 沙箱执行 (sandbox_validator.py)
  │
  ▼
AutoRegister: 验证通过后注册到工具系统 (auto_register.py)
```

用法:
    from maxbot.knowledge import KnowledgeAbsorber

    absorber = KnowledgeAbsorber()
    result = absorber.absorb("/path/to/repo")
    print(result.summary())
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maxbot.knowledge.code_parser import (
    ModuleInfo,
    ProjectStructure,
    FunctionInfo,
    ClassInfo,
    parse_file,
    scan_project,
    summarize_structure,
)
from maxbot.knowledge.capability_extractor import (
    ExtractedCapability,
    extract_capabilities_heuristic,
    extract_from_repo,
)
from maxbot.knowledge.skill_factory import (
    GeneratedSkill,
    SkillFactory,
)
from maxbot.knowledge.sandbox_validator import (
    SecurityReport,
    ValidationResult,
    scan_security,
    validate_syntax,
    run_sandboxed,
    batch_validate,
)
from maxbot.knowledge.auto_register import (
    AutoRegister,
    RegistrationResult,
)
from maxbot.knowledge.self_analyzer import (
    CapabilityGap,
    CapabilityInventory,
    SelfAssessment,
    assess,
)
from maxbot.knowledge.review_board import (
    Verdict,
    ReviewOpinion,
    ReviewBoardResult,
    ReviewBoard,
)
from maxbot.knowledge.self_improver import (
    EvolutionAttempt,
    EvolutionResult,
    SelfEvolver,
)
from maxbot.knowledge.harness_optimizer import (
    HarnessCandidate,
    OptimizationIteration,
    OptimizationResult,
    HarnessOptimizer,
)


@dataclass
class AbsorptionResult:
    """吸收结果"""
    repo_path: str
    structure: ProjectStructure | None = None
    capabilities: list[ExtractedCapability] = field(default_factory=list)
    generated_skills: list[GeneratedSkill] = field(default_factory=list)
    validations: list[ValidationResult] = field(default_factory=list)
    registrations: list[RegistrationResult] = field(default_factory=list)
    elapsed: float = 0.0

    @property
    def total_extracted(self) -> int:
        return len(self.capabilities)

    @property
    def total_validated(self) -> int:
        return sum(1 for v in self.validations if v.is_valid)

    @property
    def total_registered(self) -> int:
        return sum(1 for r in self.registrations if r.success)

    def summary(self) -> str:
        lines = [
            f"## 知识吸收报告: {self.repo_path}",
            f"- 扫描文件: {len(self.structure.modules) if self.structure else 0}",
            f"- 提取能力: {self.total_extracted}",
            f"- 验证通过: {self.total_validated}",
            f"- 注册工具: {self.total_registered}",
            f"- 耗时: {self.elapsed:.2f}s",
        ]
        if self.registrations:
            lines.append("\n### 注册详情")
            for r in self.registrations:
                status = "✅" if r.success else "❌"
                lines.append(f"- {status} {r.tool_name}" + (f" — {r.error}" if r.error else ""))
        return "\n".join(lines)


class KnowledgeAbsorber:
    """
    知识吸收器 — 核心入口

    用法:
        absorber = KnowledgeAbsorber()

        # 完整吸收流程
        result = absorber.absorb("/path/to/repo")

        # 或分步操作
        structure = absorber.scan("/path/to/repo")
        caps = absorber.extract(structure)
        absorber.validate_and_register(caps)
    """

    def __init__(
        self,
        sandbox_dir: str | None = None,
        tool_registry: Any = None,
        skills_dir: str | Path | None = None,
    ):
        self.sandbox_dir = Path(sandbox_dir) if sandbox_dir else Path.home() / ".maxbot" / "sandbox"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Use a dedicated absorbed-skills directory to avoid conflicts with user skills
        default_skills = Path.home() / ".maxbot" / "absorbed_skills"
        output_dir = Path(skills_dir) if skills_dir else default_skills
        self._skill_factory = SkillFactory(output_dir=output_dir)
        self._auto_register = AutoRegister(tool_registry=tool_registry)

    def absorb(
        self,
        repo_path: str | Path,
        languages: list[str] | None = None,
        min_docstring_len: int = 20,
        validate: bool = True,
        register: bool = True,
        llm_client: Any = None,
    ) -> AbsorptionResult:
        """
        完整吸收流程

        Args:
            repo_path: 代码仓库路径
            languages: 限制语言
            min_docstring_len: 最小 docstring 长度
            validate: 是否进行安全验证
            register: 是否注册到工具系统
            llm_client: 可选 LLM 客户端（用于深度分析）
        """
        start = time.time()
        result = AbsorptionResult(repo_path=str(repo_path))

        # 1. Scan
        result.structure = scan_project(repo_path)

        # 2. Extract
        if llm_client:
            result.capabilities = extract_from_repo(
                repo_path, languages, use_llm=True, llm_client=llm_client
            )
        else:
            for module in result.structure.modules:
                if languages and module.language not in languages:
                    continue
                caps = extract_capabilities_heuristic(module, min_docstring_len)
                result.capabilities.extend(caps)

        if not result.capabilities:
            result.elapsed = time.time() - start
            return result

        # 3. Generate skills
        result.generated_skills = self._skill_factory.generate(result.capabilities)

        # 4. Validate
        if validate:
            result.validations = batch_validate(result.capabilities)

            # 5. Register
            if register:
                result.registrations = self._auto_register.register_validated(result.validations)

        result.elapsed = time.time() - start
        return result

    def scan(self, repo_path: str | Path) -> ProjectStructure:
        """扫描项目结构"""
        return scan_project(repo_path)

    def extract(
        self,
        structure: ProjectStructure,
        min_docstring_len: int = 20,
    ) -> list[ExtractedCapability]:
        """从项目结构提取能力"""
        caps = []
        for module in structure.modules:
            caps.extend(extract_capabilities_heuristic(module, min_docstring_len))
        return caps

    def validate_and_register(
        self,
        capabilities: list[ExtractedCapability],
        toolset: str = "absorbed",
    ) -> list[RegistrationResult]:
        """验证并注册"""
        validations = batch_validate(capabilities)
        return self._auto_register.register_validated(validations, toolset)

    def unregister_all(self) -> int:
        """卸载所有 absorbed 工具"""
        return self._auto_register.unregister_absorbed()


# Re-export key types
__all__ = [
    "KnowledgeAbsorber",
    "AbsorptionResult",
    "ExtractedCapability",
    "ModuleInfo",
    "ProjectStructure",
    "FunctionInfo",
    "ClassInfo",
    "GeneratedSkill",
    "SecurityReport",
    "ValidationResult",
    "RegistrationResult",
    # Standalone functions
    "parse_file",
    "scan_project",
    "summarize_structure",
    "extract_from_repo",
    "extract_capabilities_heuristic",
    "scan_security",
    "validate_syntax",
    "run_sandboxed",
    "batch_validate",
    # Self-improvement (Phase 6)
    "CapabilityGap",
    "CapabilityInventory",
    "SelfAssessment",
    "assess",
    "Verdict",
    "ReviewOpinion",
    "ReviewBoardResult",
    "ReviewBoard",
    "EvolutionAttempt",
    "EvolutionResult",
    "SelfEvolver",
    # Meta-Harness style optimization
    "HarnessCandidate",
    "OptimizationIteration",
    "OptimizationResult",
    "HarnessOptimizer",
]
