"""MaxBot 内置工具包 — 导入即注册"""

from maxbot.tools._registry import registry

# 导入所有工具模块，触发 @registry.tool() 装饰器
from maxbot.tools import file_tools   # noqa: F401
from maxbot.tools import shell_tools  # noqa: F401
from maxbot.tools import git_tools    # noqa: F401
from maxbot.tools import web_tools    # noqa: F401
from maxbot.tools import code_editor  # noqa: F401
from maxbot.tools import notebook_tools  # noqa: F401
from maxbot.tools import code_analysis   # noqa: F401
from maxbot.tools import multi_agent_tools  # noqa: F401

__all__ = ["registry"]
