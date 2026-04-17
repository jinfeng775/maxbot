"""
MaxBot 工具注册表导出

这是工具注册表的统一入口点。

所有工具都应该从这里导入 registry：

    from maxbot.tools._registry import registry

    @registry.tool(name="my_tool", description="...")
    def my_tool(arg: str) -> str:
        ...

实际的实现位于 maxbot.core.tool_registry
"""

from maxbot.core.tool_registry import ToolRegistry, ToolDef

# 全局工具注册表实例
registry = ToolRegistry()

# 导出主要类
__all__ = ["registry", "ToolRegistry", "ToolDef"]
