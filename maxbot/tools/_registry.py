"""
MaxBot 内置工具

工具文件用法：
    from maxbot.tools._registry import registry

    @registry.tool(name="my_tool", description="...")
    def my_tool(arg: str) -> str:
        ...
"""

from maxbot.core.tool_registry import ToolRegistry

# 全局工具注册表实例
registry = ToolRegistry()
