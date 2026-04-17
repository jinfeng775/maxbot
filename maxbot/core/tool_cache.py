"""
工具缓存 - 优化工具调用

优化点:
1. 工具列表缓存
2. 工具优先级
3. 工具使用统计
"""

from dataclasses import dataclass, field
from typing import Any, Callable
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolUsageStats:
    """工具使用统计"""
    call_count: int = 0  # 调用次数
    last_call_time: float = 0  # 上次调用时间
    total_time: float = 0  # 总耗时
    avg_time: float = 0  # 平均耗时


class ToolCache:
    """
    工具缓存
    
    功能:
    - 缓存工具列表
    - 工具使用统计
    - 缓存失效管理
    """
    
    def __init__(self, cache_ttl: float = 300):
        """
        初始化工具缓存
        
        Args:
            cache_ttl: 缓存有效期（秒），默认 5 分钟
        """
        self._cached_tools: list[dict] | None = None
        self._last_update: float = 0
        self._cache_ttl: float = cache_ttl
        self._usage_stats: dict[str, ToolUsageStats] = {}
    
    def get_tools(
        self,
        get_tools_fn: Callable[[], list[dict]],
        force_refresh: bool = False
    ) -> list[dict]:
        """
        获取工具列表（带缓存）
        
        Args:
            get_tools_fn: 获取工具列表的函数
            force_refresh: 强制刷新缓存
        
        Returns:
            list[dict]: 工具列表
        """
        # 检查是否需要刷新缓存
        if force_refresh or self._is_cache_expired():
            logger.debug("工具缓存已过期，重新获取工具列表")
            self._refresh_cache(get_tools_fn)
        
        return self._cached_tools.copy() if self._cached_tools else []
    
    def _is_cache_expired(self) -> bool:
        """
        检查缓存是否过期
        
        Returns:
            bool: 是否过期
        """
        if self._cached_tools is None:
            return True
        
        return time.time() - self._last_update > self._cache_ttl
    
    def _refresh_cache(self, get_tools_fn: Callable[[], list[dict]]) -> None:
        """
        刷新缓存
        
        Args:
            get_tools_fn: 获取工具列表的函数
        """
        start_time = time.time()
        self._cached_tools = get_tools_fn()
        self._last_update = time.time()
        logger.debug(
            f"工具缓存已更新: {len(self._cached_tools)} 个工具, "
            f"耗时 {self._last_update - start_time:.4f}s"
        )
    
    def invalidate(self):
        """使缓存失效"""
        self._cached_tools = None
        self._last_update = 0
        logger.debug("工具缓存已失效")
    
    def record_usage(self, tool_name: str, duration: float) -> None:
        """
        记录工具使用情况
        
        Args:
            tool_name: 工具名称
            duration: 调用耗时（秒）
        """
        if tool_name not in self._usage_stats:
            self._usage_stats[tool_name] = ToolUsageStats()
        
        stats = self._usage_stats[tool_name]
        stats.call_count += 1
        stats.last_call_time = time.time()
        stats.total_time += duration
        stats.avg_time = stats.total_time / stats.call_count
    
    def get_usage_stats(self) -> dict[str, dict]:
        """
        获取工具使用统计
        
        Returns:
            dict: 工具使用统计
        """
        return {
            name: {
                "call_count": stats.call_count,
                "last_call_time": stats.last_call_time,
                "total_time": stats.total_time,
                "avg_time": stats.avg_time,
            }
            for name, stats in self._usage_stats.items()
        }
    
    def print_usage_stats(self) -> str:
        """
        打印工具使用统计
        
        Returns:
            str: 格式化的统计信息
        """
        if not self._usage_stats:
            return "暂无工具使用统计"
        
        lines = ["📊 工具使用统计:\n"]
        
        # 按调用次数排序
        sorted_tools = sorted(
            self._usage_stats.items(),
            key=lambda x: x[1].call_count,
            reverse=True
        )
        
        for tool_name, stats in sorted_tools:
            lines.append(f"  {tool_name}:")
            lines.append(f"    调用次数: {stats.call_count}")
            lines.append(f"    平均耗时: {stats.avg_time:.4f}s")
            lines.append(f"    总耗时: {stats.total_time:.4f}s")
            lines.append("")
        
        return "\n".join(lines)


class ToolPrioritizer:
    """
    工具优先级管理器
    
    功能:
    - 工具优先级排序
    - 工具分类
    """
    
    # 工具优先级（数字越小优先级越高）
    TOOL_PRIORITIES = {
        # 核心工具（最高优先级）
        "memory": 1,
        
        # 文件操作（高优先级）
        "read_file": 2,
        "write_file": 3,
        "code_edit": 4,
        "code_edit_multi": 5,
        "code_create": 6,
        "patch_file": 7,
        
        # 代码分析（中高优先级）
        "analyze_python": 8,
        "analyze_code": 9,
        "analyze_project": 10,
        "get_function": 11,
        
        # 系统操作（中优先级）
        "shell": 12,
        "exec_python": 13,
        "execute_code": 14,
        
        # 搜索操作（中低优先级）
        "search_files": 15,
        "list_files": 16,
        
        # 网络操作（低优先级）
        "web_search": 17,
        "web_fetch": 18,
        
        # Git 操作（低优先级）
        "git_status": 19,
        "git_diff": 20,
        "git_log": 21,
        "git_commit": 22,
        "git_branch": 23,
        
        # Notebook 操作（低优先级）
        "notebook_read": 24,
        "notebook_edit_cell": 25,
        "notebook_insert_cell": 26,
        "notebook_delete_cell": 27,
        
        # Agent 操作（最低优先级）
        "spawn_agent": 28,
        "spawn_agents_parallel": 29,
        
        # 记忆操作（低优先级）
        "memory": 30,
    }
    
    @classmethod
    def sort_tools(cls, tools: list[dict]) -> list[dict]:
        """
        按优先级排序工具
        
        Args:
            tools: 工具列表
        
        Returns:
            list[dict]: 排序后的工具列表
        """
        def get_priority(tool):
            name = tool.get("function", {}).get("name", "")
            return cls.TOOL_PRIORITIES.get(name, 100)
        
        return sorted(tools, key=get_priority)
    
    @classmethod
    def get_priority(cls, tool_name: str) -> int:
        """
        获取工具优先级
        
        Args:
            tool_name: 工具名称
        
        Returns:
            int: 优先级（数字越小优先级越高）
        """
        return cls.TOOL_PRIORITIES.get(tool_name, 100)
    
    @classmethod
    def categorize_tools(cls, tools: list[dict]) -> dict[str, list[dict]]:
        """
        按类别分类工具
        
        Args:
            tools: 工具列表
        
        Returns:
            dict: 分类后的工具字典
        """
        categories = {
            "core": [],           # 核心工具
            "file": [],           # 文件操作
            "code": [],           # 代码分析
            "system": [],         # 系统操作
            "search": [],         # 搜索操作
            "network": [],        # 网络操作
            "git": [],            # Git操作
            "notebook": [],       # Notebook 操作
            "agent": [],          # Agent 操作
            "other": [],          # 其他工具
        }
        
        for tool in tools:
            name = tool.get("function", {}).get("name", "")
            priority = cls.get_priority(name)
            
            if priority <= 1:
                categories["core"].append(tool)
            elif priority <= 7:
                categories["file"].append(tool)
            elif priority <= 11:
                categories["code"].append(tool)
            elif priority <= 14:
                categories["system"].append(tool)
            elif priority <= 16:
                categories["search"].append(tool)
            elif priority <= 18:
                categories["network"].append(tool)
            elif priority <= 23:
                categories["git"].append(tool)
            elif priority <= 27:
                categories["notebook"].append(tool)
            elif priority <= 29:
                categories["agent"].append(tool)
            else:
                categories["other"].append(tool)
        
        return categories
    
    @classmethod
    def print_tool_categories(cls, tools: list[dict]) -> str:
        """
        打印工具分类信息
        
        Args:
            tools: 工具列表
        
        Returns:
            str: 格式化的分类信息
        """
        categories = cls.categorize_tools(tools)
        
        lines = ["📊 工具分类:\n"]
        
        for category, tools_list in categories.items():
            if tools_list:
                lines.append(f"  {category.upper()} ({len(tools_list)} 个):")
                for tool in tools_list:
                    name = tool.get("function", {}).get("name", "")
                    lines.append(f"    • {name}")
                lines.append("")
        
        return "\n".join(lines)
