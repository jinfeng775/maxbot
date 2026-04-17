"""
工具缓存 - 优化工具调用（增强版）

优化项：
1. 工具列表缓存
2. 工具优先级
3. 工具使用统计
4. 工具结果缓存（新增）
5. 缓存命中率统计
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import time
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class ToolUsageStats:
    """工具使用统计"""
    call_count: int = 0  # 调用次数
    last_call_time: float = 0  # 上次调用时间
    total_time: float = 0  # 总耗时
    avg_time: float = 0  # 平均耗时
    cache_hits: int = 0  # 缓存命中次数
    cache_misses: int = 0  # 缓存未命中次数
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class ToolCache:
    """
    工具缓存（增强版）
    
    功能：
    - 缓存工具列表
    - 工具使用统计
    - 缓存失效管理
    - 工具结果缓存（新增）
    - 缓存命中率统计
    """
    
    def __init__(
        self,
        cache_ttl: float = 300,
        result_cache_ttl: float = 60,
        max_result_cache_size: int = 1000,
    ):
        """
        初始化工具缓存
        
        Args:
            cache_ttl: 缓存有效期（秒），默认 5 分钟
            result_cache_ttl: 结果缓存有效期（秒），默认 1 分钟
            max_result_cache_size: 最大结果缓存条目数
        """
        self._cached_tools: list[dict] | None = None
        self._last_update: float = 0
        self._cache_ttl: float = cache_ttl
        self._usage_stats: dict[str, ToolUsageStats] = {}
        self._result_cache: dict[str, tuple[float, str]] = {}  # {hash: (timestamp, result)}
        self._result_cache_ttl: float = result_cache_ttl
        self._max_result_cache_size: int = max_result_cache_size
        self._result_cache_hits: int = 0
        self._result_cache_misses: int = 0
    
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
    
    def get_cached_result(
        self,
        tool_name: str,
        args: dict,
    ) -> Optional[str]:
        """
        获取缓存的结果
        
        Args:
            tool_name: 工具名称
            args: 工具参数
            
        Returns:
            缓存的结果，如果不存在返回 None
        """
        cache_key = self._make_cache_key(tool_name, args)
        
        if cache_key in self._result_cache:
            timestamp, result = self._result_cache[cache_key]
            
            # 检查是否过期
            if time.time() - timestamp < self._result_cache_ttl:
                self._result_cache_hits += 1
                
                # 更新统计
                if tool_name not in self._usage_stats:
                    self._usage_stats[tool_name] = ToolUsageStats()
                self._usage_stats[tool_name].cache_hits += 1
                
                logger.debug(f"工具结果缓存命中: {tool_name}")
                return result
            else:
                # 过期，删除
                del self._result_cache[cache_key]
        
        self._result_cache_misses += 1
        
        # 更新统计
        if tool_name not in self._usage_stats:
            self._usage_stats[tool_name] = ToolUsageStats()
        self._usage_stats[tool_name].cache_misses += 1
        
        return None
    
    def cache_result(
        self,
        tool_name: str,
        args: dict,
        result: str,
    ):
        """
        缓存工具结果
        
        Args:
            tool_name: 工具名称
            args: 工具参数
            result: 工具结果
        """
        # 检查缓存大小
        if len(self._result_cache) >= self._max_result_cache_size:
            # 删除最旧的缓存
            oldest_key = min(
                self._result_cache.keys(),
                key=lambda k: self._result_cache[k][0]
            )
            del self._result_cache[oldest_key]
            logger.debug(f"工具结果缓存已满，删除最旧的条目")
        
        cache_key = self._make_cache_key(tool_name, args)
        self._result_cache[cache_key] = (time.time(), result)
        logger.debug(f"缓存工具结果: {tool_name}")
    
    def _make_cache_key(self, tool_name: str, args: dict) -> str:
        """
        生成缓存键
        
        Args:
            tool_name: 工具名称
            args: 工具参数
            
        Returns:
            缓存键
        """
        # 规范化参数
        normalized_args = self._normalize_args(args)
        
        # 生成哈希
        key_str = f"{tool_name}:{json.dumps(normalized_args, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _normalize_args(self, args: Any) -> Any:
        """
        规范化参数用于缓存键生成
        
        Args:
            args: 原始参数
            
        Returns:
            规范化后的参数
        """
        if isinstance(args, dict):
            return {k: self._normalize_args(v) for k, v in sorted(args.items())}
        elif isinstance(args, (list, tuple)):
            return [self._normalize_args(v) for v in args]
        elif isinstance(args, (str, int, float, bool)) or args is None:
            return args
        else:
            # 其他类型转为字符串
            return str(args)
    
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
    
    def invalidate_result_cache(self):
        """使结果缓存失效"""
        self._result_cache.clear()
        logger.debug("工具结果缓存已失效")
    
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
                "call_count: stats.call_count,
                "last_call_time": stats.last_call_time,
                "total_time": stats.total_time,
                "avg_time": stats.avg_time,
                "cache_hits": stats.cache_hits,
                "cache_misses": stats.cache_misses,
                "cache_hit_rate": stats.cache_hit_rate,
            }
            for name, stats in self._usage_stats.items()
        }
    
    def get_cache_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            dict: 缓存统计信息
        """
        total_requests = self._result_cache_hits + self._result_cache_misses
        
        return {
            "result_cache_size": len(self._result_cache),
            "result_cache_max_size": self._max_result_cache_size,
            "result_cache_ttl": self._result_cache_ttl,
            "result_cache_hits": self._result_cache_hits,
            "result_cache_misses": self._result_cache_misses,
            "result_cache_hit_rate": (
                self._result_cache_hits / total_requests
                if total_requests > 0
                else 0.0
            ),
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
            lines.append(f"    调用次数: {{stats.call_count}")
            lines.append(f"    平均耗时: {stats.avg_time:.4f}s")
            lines.append(f"    总耗时: {stats.total_time:.4f}s")
            lines.append(f"    缓存命中: {stats.cache_hits}")
            lines.append(f"    缓存未命中: {stats.cache_misses}")
            lines.append(f"    缓存命中率: {stats.cache_hit_rate:.2%}")
            lines.append("")
        
        return "\n".join(lines)
    
    def print_cache_stats(self) -> str:
        """
        打印缓存统计信息
        
        Returns:
            str: 格式化的统计信息
        """
        cache_stats = self.get_cache_stats()
        
        lines = ["📊 缓存统计:\n"]
        lines.append(f"  结果缓存大小: {cache_stats['result_cache_size']}/{cache_stats['result_cache_max_size']}")
        lines.append(f"  结果缓存 TTL: {cache_stats['result_cache_ttl']}s")
        lines.append(f"  缓存命中: {cache_stats['result_cache_hits']}")
        lines.append(f"  缓存未命中: {cache_stats['result_cache_misses']}")
        lines.append(f"  缓存命中率: {cache_stats['result_cache_hit_rate']:.2%}")
        
        return "\n".join(lines)


class ToolPrioritizer:
    """
    工具优先级管理器
    
    功能：
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
