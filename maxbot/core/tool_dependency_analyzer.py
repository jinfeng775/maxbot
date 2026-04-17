"""
工具依赖分析器

功能：
- 分析工具参数依赖关系
- 检测工具间的数据流
- 判断工具是否可以并行执行
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Set, Dict, List

from maxbot.utils.logger import get_logger

logger = get_logger("tool_deps")


@dataclass
class ToolDependency:
    """工具依赖关系"""
    tool_name: str
    depends_on: Set[str] = field(default_factory=set)  # 依赖的工具名称
    output_keys: Set[str] = field(default_factory=set)  # 输出的键可能被其他工具使用
    input_keys: Set[str] = field(default_factory=set)  # 输入的键


class ToolDependencyAnalyzer:
    """
    工具依赖分析器
    
    功能：
    - 分析工具调用之间的依赖关系
    - 判断哪些工具可以并行执行
    - 生成执行拓扑顺序
    """

    def __init__(self):
        self._common_output_patterns = [
            # 常见的输出键模式
            r"file_path",
            r"content",
            r"result",
            r"data",
            r"output",
        ]

    def analyze_dependencies(
        self,
        tool_calls: List[Dict[str, Any]],
    ) -> List[ToolDependency]:
        """
        分析工具调用依赖关系
        
        Args:
            tool_calls: 工具调用列表
            
        Returns:
            工具依赖关系列表
        """
        dependencies = []
        
        # 第一步：提取每个工具的输入/输出键
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call.get("function", {}).get("name", "")
            tool_args = tool_call.get("function", {}).get("arguments", {})
            
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except (json.JSONDecodeError, ValueError):
                    tool_args = {}
            
            # 提取输入键
            input_keys = self._extract_input_keys(tool_args)
            
            # 预测输出键
            output_keys = self._predict_output_keys(tool_name, tool_args)
            
            dep = ToolDependencyDependency(
                tool_name=tool_name,
                input_keys=input_keys,
                output_keys=output_keys,
            )
            dependencies.append(dep)
        
        # 第二步：分析工具间的依赖关系
        for i, dep_i in enumerate(dependencies):
            for j, dep_j in enumerate(dependencies):
                if i >= j:  # 只分析 j < i 的情况
                    continue
                
                # 如果 dep_j 的输出被 dep_i 使用，则 dep_i 依赖 dep_j
                if dep_i.input_keys & dep_j.output_keys:
                    dep_i.depends_on.add(dep_j.tool_name)
        
        logger.debug(f"依赖分析完成: {len(dependencies)} 个工具")
        for dep in dependencies:
            if dep.depends_on:
                logger.debug(f"  {dep.tool_name} 依赖: {dep.depends_on}")
        
        return dependencies

    def _extract_input_keys(self, args: Dict[str, Any]) -> Set[str]:
        """
        从参数中提取可能的输入键
        
        Args:
            args: 工具参数
            
        Returns:
            输入键集合
        """
        keys = set()
        
        for key, value in args.items():
            # 添加参数名
            keys.add(key)
            
            # 如果值看起来像引用（如 ${result}），提取引用的键
            if isinstance(value, str):
                refs = re.findall(r'\$\{([^}]+)\}', value)
                keys.update(refs)
            
            # 如果值是字典，递归提取
            elif isinstance(value, dict):
                keys.update(self._extract_input_keys(value))
        
        return keys

    def _predict_output_keys(self, tool_name: str, args: Dict[str, Any]) -> Set[str]:
        """
        预测工具的输出键
        
        Args:
            tool_name: 工具名称
            args: 工具参数
            
        Returns:
            输出键集合
        """
        keys = set()
        
        # 根据工具名称和参数预测输出
        if "read" in tool_name.lower():
            keys.add("content")
            if "file" in tool_name.lower():
                keys.add("file_content")
        
        elif "write" in tool_name.lower():
            keys.add("success")
        
        elif "search" in tool_name.lower():
            keys.add("results")
            keys.add("matches")
        
        elif "shell" in tool_name.lower() or "exec" in tool_name.lower():
            keys.add("stdout")
            keys.add("stderr")
            keys.add("exit_code")
        
        elif "git" in tool_name.lower():
            keys.add("status")
            keys.add("diff")
        
        elif "web" in tool_name.lower() or "fetch" in tool_name.lower():
            keys.add("html")
            keys.add("content")
        
        # 通用输出键
        keys.add("result")
        keys.add("data")
        keys.add("output")
        
        return keys

    def get_parallel_groups(
        self,
        dependencies: List[ToolDependency],
    ) -> List[List[int]]:
        """
        获取可以并行执行的工具组
        
        Args:
            dependencies: 工具依赖关系列表
            
        Returns:
            工具索引组列表，每组内的工具可以并行执行
        """
        groups = []
        executed = set()
        
        while len(executed) < len(dependencies):
            # 找出所有依赖都已满足的工具
            current_group = []
            for i, dep in enumerate(dependencies):
                if i in executed:
                    continue
                
                # 检查所有依赖是否已执行
                deps_satisfied = all(
                    any(d.tool_name == dep_name for d in dependencies[:i])
                    for dep_name in dep.depends_on
                )
                
                if deps_satisfied:
                    current_group.append(i)
            
            if not current_group:
                # 检测到循环依赖，将剩余工具全部加入
                logger.warning("检测到可能的循环依赖，将剩余工具串行执行")
                current_group = [
                    i for i in range(len(dependencies))
                    if i not in executed
                ]
            
            groups.append(current_group)
            executed.update(current_group)
        
        logger.debug(f"并行分组: {[len(g) for g in groups]} 组")
        return groups


# 兼容性别名
ToolDependencyDependency = ToolDependency
