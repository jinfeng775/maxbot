"""
自动注册 — 将验证通过的能力注册到工具系统

流程:
1. 接收 ValidationResult 列表
2. 过滤出通过验证的
3. 为每个生成可注册的 ToolDef
4. 注册到 ToolRegistry
"""

from __future__ import annotations

import json
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from maxbot.knowledge.capability_extractor import ExtractedCapability
from maxbot.knowledge.sandbox_validator import ValidationResult


@dataclass
class RegistrationResult:
    """注册结果"""
    tool_name: str
    success: bool
    error: str = ""
    toolset: str = "absorbed"


class AutoRegister:
    """
    自动注册管理器

    用法:
        register = AutoRegister(registry)
        results = register.register_validated(validation_results)
    """

    def __init__(self, tool_registry: Any = None):
        self._registry = tool_registry

    def register_validated(
        self,
        results: list[ValidationResult],
        toolset: str = "absorbed",
    ) -> list[RegistrationResult]:
        """
        注册通过验证的能力

        Args:
            results: 验证结果列表
            toolset: 注册到的工具集名称
        """
        registrations = []
        for result in results:
            if not result.is_valid:
                registrations.append(RegistrationResult(
                    tool_name=result.capability.name,
                    success=False,
                    error=f"Validation failed: security={result.security.is_safe}, "
                          f"syntax={result.syntax_valid}, test={result.test_passed}",
                ))
                continue

            reg = self._register_single(result.capability, toolset)
            registrations.append(reg)

        return registrations

    def _register_single(
        self,
        cap: ExtractedCapability,
        toolset: str,
    ) -> RegistrationResult:
        """注册单个能力"""
        if self._registry is None:
            return RegistrationResult(
                tool_name=cap.name,
                success=False,
                error="No tool registry provided",
            )

        try:
            # Build a handler function from the capability
            handler = _create_handler(cap)

            # Register
            self._registry.register(
                name=cap.name,
                description=cap.description,
                parameters=cap.parameters,
                handler=handler,
                toolset=toolset,
                required_params=cap.required_params,
                tags=cap.tags,
            )

            return RegistrationResult(
                tool_name=cap.name,
                success=True,
                toolset=toolset,
            )

        except Exception as e:
            return RegistrationResult(
                tool_name=cap.name,
                success=False,
                error=str(e),
            )

    def register_from_skill_dir(
        self,
        skill_dir: str | Path,
        toolset: str = "absorbed",
    ) -> list[RegistrationResult]:
        """从技能目录注册所有 handler"""
        skill_dir = Path(skill_dir)
        if not skill_dir.exists():
            return []

        registrations = []
        for sub in skill_dir.iterdir():
            if not sub.is_dir():
                continue
            handler_path = sub / "handler.py"
            meta_path = sub / "meta.json"
            if not handler_path.exists():
                continue

            try:
                # Load handler module dynamically
                spec = importlib.util.spec_from_file_location(
                    f"absorbed_{sub.name}",
                    str(handler_path),
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    # Find the handler function (first non-private function)
                    handler_fn = None
                    for name in dir(mod):
                        if not name.startswith("_") and callable(getattr(mod, name)):
                            handler_fn = getattr(mod, name)
                            break

                    if handler_fn and self._registry is not None:
                        # Load metadata
                        description = f"Absorbed tool: {sub.name}"
                        if meta_path.exists():
                            meta = json.loads(meta_path.read_text())
                            description = meta.get("description", description)

                        self._registry.register(
                            name=sub.name,
                            description=description,
                            parameters={},  # Will be inferred from function signature
                            handler=handler_fn,
                            toolset=toolset,
                            tags=["absorbed", "from-skill"],
                        )
                        registrations.append(RegistrationResult(
                            tool_name=sub.name,
                            success=True,
                            toolset=toolset,
                        ))

            except Exception as e:
                registrations.append(RegistrationResult(
                    tool_name=sub.name,
                    success=False,
                    error=str(e),
                ))

        return registrations

    def unregister_absorbed(self) -> int:
        """卸载所有 absorbed 工具集的工具"""
        if self._registry is None:
            return 0
        count = 0
        tools = self._registry.list_tools(toolset="absorbed")
        for tool in tools:
            self._registry.unregister(tool.name)
            count += 1
        return count


def _create_handler(cap: ExtractedCapability) -> Callable[..., str]:
    """从 capability 创建 handler 函数"""
    def handler(**kwargs) -> str:
        # The handler code is a string — compile and execute it
        local_ns: dict[str, Any] = {}
        try:
            exec(cap.handler_code, {}, local_ns)
            # Find the function (first callable)
            for name, obj in local_ns.items():
                if callable(obj) and not name.startswith("_"):
                    return obj(**kwargs)
            return json.dumps({"error": "No handler function found in generated code"})
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    handler.__name__ = cap.name
    handler.__doc__ = cap.description
    return handler
