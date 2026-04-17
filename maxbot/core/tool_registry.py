"""
工具注册表 — MaxBot 工具系统核心

参考来源:
- Hermes: tools/registry.py — 装饰器注册 + 自动发现 + schema 收集
- Claude Code: tools.ts — 工具分类 + 模块化组织
- OpenClaw: plugin-sdk — 类型化合约
"""

from __future__ import annotations

import importlib
import inspect
import json
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from maxbot.utils.logger import get_logger

# 获取工具日志器
logger = get_logger("tools")


@dataclass
class ToolDef:
    """工具定义"""
    name: str
    description: str
    parameters: dict[str, Any]          # JSON: Schema properties
    handler: Callable[..., str]
    toolset: str = "builtin"
    requires_env: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    required_params: list[str] = field(default_factory=list)

    def to_schema(self) -> dict:
        """转换成 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required_params or list(self.parameters.keys()),
                },
            },
        }


class ToolRegistry:
    """
    工具注册表

    支持:
    - 装饰器注册
    - 目录自动扫描
    - 动态注册/卸载
    - 沙箱执行（待实现）
    """

    def __init__(self):
        self._tools: dict[str, ToolDef] = {}
        logger.info("工具注册表初始化完成")

    # ─── 注册 ─────────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., str],
        toolset: str = "builtin",
        requires_env: list[str] | None = None,
        tags: list[str] | None = None,
        required_params: list[str] | None = None,
    ) -> ToolDef:
        """注册一个工具"""
        tool = ToolDef(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            toolset=toolset,
            requires_env=requires_env or [],
            tags=tags or [],
            required_params=required_params or [],
        )
        self._tools[name] = tool
        logger.debug(f"工具注册成功: {name} (toolset={toolset})")
        return tool

    def register_def(self, tool: ToolDef):
        """直接注册 ToolDef 对象"""
        self._tools[tool.name] = tool
        logger.debug(f"工具定义注册成功: {tool.name}")

    def unregister(self, name: str):
        """卸载工具"""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"工具卸载成功: {name}")
        else:
            logger.warning(f"尝试卸载不存在的工具: {name}")

    # ─── 装饰器 ─────────────────────────────────────────────────────────────

    def tool(
        self,
        name: str | None = None,
        description: str | None = None,
        toolset: str = "builtin",
        tags: list[str] | None = None,
    ):
        """
        装饰器注册工具

        @registry.tool(name="read_file", description="读取文件")
        def read_file(path: str) -> str:
            ...
        """
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            tool_desc = description or inspect.getdoc(func) or f"Tool: {tool_name}"
            params, required = _extract_params(func)
            self.register(
                name=tool_name,
                description=tool_desc,
                parameters=params,
                handler=func,
                toolset=toolset,
                tags=tags,
                required_params=required,
            )
            return func
        return decorator

    # ─── 查询 & 调用 ─────────────────────────────────────────────────────────

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_tools(self, toolset: str | None = None) -> list[ToolDef]:
        tools = list(self._tools.values())
        if toolset:
            tools = [t for t in tools if t.toolset == toolset]
        return tools

    def get_schemas(self) -> list[dict]:
        """获取所有工具的 OpenAI schema"""
        return [t.to_schema() for t in self._tools.values()]

    def call(self, name: str, args: dict[str, Any]) -> str:
        """调用工具"""
        tool = self._tools.get(name)
        if not tool:
            logger.error(f"工具未找到: {name}")
            return json.dumps({"error": f"未知工具: {name}"})

        logger.debug(f"调用工具: {name}, 参数: {args}")

        try:
            result = tool.handler(**args)
            # 确保返回字符串
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
            logger.debug(f"工具调用成功: {name}")
            return result
        except Exception as e:
            logger.error(f"工具调用失败: {name}, 错误: {e}")
            return json.dumps({"error": str(e), "tool": name}, ensure_ascii=False)

    # ─── 自动发现 ─────────────────────────────────────────────────────────────

    def load_builtins(self):
        """加载 maxbot.tools 包下的所有工具"""
        logger.info("开始加载内置工具")
        import maxbot.tools as tools_pkg
        self._discover_package(tools_pkg)
        logger.info(f"内置工具加载完成，共 {len(self._tools)} 个工具")

    def load_directory(self, dir_path: str | Path):
        """从指定目录加载 .py 工具文件"""
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            logger.warning(f"工具目录不存在: {dir_path}")
            return

        logger.info(f"开始扫描工具目录: {dir_path}")
        loaded_count = 0

        for py_file in dir_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(py_file.stem, str(py_file))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    loaded_count += 1
                    logger.debug(f"加载工具文件: {py_file.name}")
            except Exception as e:
                logger.error(f"加载工具文件失败: {py_file} — {e}")

        logger.info(f"工具目录扫描完成，加载 {loaded_count} 个文件")

    def _discover_package(self, pkg):
        """扫描包内所有模块，触发注册"""
        for _importer, modname, _ispkg in pkgutil.walk_packages(
            pkg.__path__, prefix=pkg.__name__ + "."
        ):
            try:
                importlib.import_module(modname)
                logger.debug(f"加载模块: {modname}")
            except Exception as e:
                logger.error(f"加载模块失败: {modname} — {e}")

    # ─── 热加载 ─────────────────────────────────────────────────────────────

    def hot_reload(self, name: str) -> bool:
        """热重载指定工具（重新导入模块）"""
        tool = self._tools.get(name)
        if not tool:
            logger.warning(f"热重载失败: 工具不存在 {name}")
            return False

        handler_mod = inspect.getmodule(tool.handler)
        if handler_mod is None:
            logger.warning(f"热重载失败: 无法获取模块 {name}")
            return False

        try:
            importlib.reload(handler_mod)
            logger.info(f"热重载成功: {name}")
            return True
        except Exception as e:
            logger.error(f"热重载失败: {name} — {e}")
            return False

    def __len__(self):
        return len(self._tools)

    def __repr__(self):
        return f"ToolRegistry({len(self._tools)} tools: {list(self._tools.keys())})"


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def _extract_params(func: Callable) -> dict[str, Any]:
    """从函数签名提取 JSON Schema 参数"""
    sig = inspect.signature(func)
    params: dict[str, Any] = {}
    required: list[str] = []
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    for name, param in sig.parameters.items():
        if name in ("self", "cls", "task_id"):
            continue
        ptype = type_map.get(param.annotation, "string")
        p: dict[str, Any] = {"type": ptype}
        if param.default is not inspect.Parameter.empty:
            p["default"] = param.default
        else:
            required.append(name)
        params[name] = p
    return params, required
