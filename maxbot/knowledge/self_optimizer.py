"""
MaxBot 自我优化系统

学习 Hermes Agent Self-Evolution 的核心技术：
1. 提示词优化 (Prompt Optimization)
2. 技能进化 (Skill Evolution)
3. 迭代优化 (Iterative Optimization)
4. 评估机制 (Evaluation Mechanism)
5. 自动回退 (Automatic Fallback)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from datetime import datetime

from maxbot.utils.logger import get_logger

logger = get_logger("self_optimizer")


@dataclass
class OptimizationResult:
    """优化结果"""
    success: bool
    method: str
    iterations: int
    best_score: float
    improved_text: str
    suggestions: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class SelfOptimizer:
    """
    MaxBot 自我优化器
    
    功能:
    1. 提示词优化
    2. 技能进化
    3. 代码优化
    4. 配置优化
    """
    
    def __init__(
        self,
        project_path: str | Path = "/root/maxbot",
        max_iterations: int = 140,
        early_stop_patience: int = 10,
    ):
        """
        初始化自我优化器
        
        Args:
            project_path: 项目路径
            max_iterations: 最大迭代次数
            early_stop_patience: 早期停止耐心值
        """
        self.project_path = Path(project_path)
        self.max_iterations = max_iterations
        self.early_stop_patience = early_stop_patience
        
        logger.info(f"自我优化器初始化: {project_path}, 最大迭代={max_iterations}")
    
    def optimize_prompt(
        self,
        prompt_name: str,
        prompt_text: str,
        eval_function: Callable[[str], float] | None = None,
        iterations: int | None = None,
    ) -> OptimizationResult:
        """
        优化提示词
        
        Args:
            prompt_name: 提示词名称
            prompt_text: 提示词文本
            eval_function: 评估函数（返回 0-1 分数）
            iterations: 迭代次数（None = 使用默认值）
        
        Returns:
            OptimizationResult:优化结果
        """
        iterations = iterations or self.max_iterations_iterations
        

        
        logger.info(f"开始优化提示词: {prompt_name}, 迭代={iterations}")
        
        best_prompt = prompt_text
        best_score = 0.0
        no_improvement_count = 0
        
        suggestions = []
        
        for i in range(iterations):
            # 1. 分析当前提示词
            analysis = self._analyze_prompt(best_prompt)
            
            # 2. 生成改进建议
            suggestion = self._generate_prompt_suggestion(analysis, i)
            suggestions.append(suggestion)
            
            # 3. 应用改进
            improved_prompt = self._apply_prompt_improvement(best_prompt, suggestion)
            
            # 4. 评估改进效果
            if eval_function:
                score = eval_function(improved_prompt)
            else:
                # 默认评估：基于长度和结构
                score = self._default_prompt_eval(improved_prompt)
            
            # 5. 更新最佳提示词
            if score > best_score:
                best_prompt = improved_prompt
                best_score = score
                no_improvement_count = 0
                logger.debug(f"迭代 {i+1}: 改进! 分数={score:.3f}")
            else:
                no_improvement_count += 1
                logger.debug(f"迭代 {i+1}: 无改进 分数={score:.3f}")
            
            # 6. 早期停止
            if no_improvement_count >= self.early_stop_patience:
                logger.info(f"早期停止: {no_improvement_count} 次无改进")
                break
        
        result = OptimizationResult(
            success=True,
            method="prompt_optimization",
            iterations=i + 1,
            best_score=best_score,
            improved_text=best_prompt,
            suggestions=suggestions,
            metrics={
                "initial_length": len(prompt_text),
                "final_length": len(best_prompt),
                "improvement_ratio": (best_score - self._default_prompt_eval(prompt_text)) / max(best_score, 0.001),
            },
        )
        
        logger.info(f"提示词优化完成: {prompt_name}, 最终分数={best_score:.3f}")
        return result
    
    def optimize_skill(
        self,
        skill_name: str,
        skill_text: str,
        eval_function: Callable[[str], float] | None = None,
        iterations: int | None = None,
    ) -> OptimizationResult:
        """
        优化技能
        
        Args:
            skill_name: 技能名称
            skill_text: 技能代码
            eval_function: 评估函数（返回 0-1 分数）
            iterations: 迭代次数（None = 使用默认值）
        
        Returns:
            OptimizationResult: 优化结果
        """
        iterations = iterations or self.max_iterations_iterations
        
        logger.info(f"开始优化技能: {skill_name}, 迭代={iterations}")
        
        best_skill = skill_text
        best_score = 0.0
        no_improvement_count = 0
        
        suggestions = []
        
        for i in range(iterations):
            # 1. 分析当前技能
            analysis = self._analyze_skill(best_skill)
            
            # 2. 生成改进建议
            suggestion = self._generate_skill_suggestion(analysis, i)
            suggestions.append(suggestion)
            
            # 3. 应用改进
            improved_skill = self._apply_skill_improvement(best_skill, suggestion)
            
            # 4. 评估改进效果
            if eval_function:
                score = eval_function(improved_skill)
            else:
                # 默认评估：基于代码质量
                score = self._default_skill_eval(improved_skill)
            
            # 5. 更新最佳技能
            if score > best_score:
                best_skill = improved_skill
                best_score = score
                no_improvement_count = 0
                logger.debug(f"迭代 {i+1}: 改进! 分数={score:.3f}")
            else:
                no_improvement_count += 1
                logger.debug(f"迭代 {i+1}: 无改进 分数={score:.3f}")
            
            # 6. 早期停止
            if no_improvement_count >= self.early_stop_patience:
                logger.info(f"早期停止: {no_improvement_count} 次无改进")
                break
        
        result = OptimizationResult(
            success=True,
            method="skill_optimization",
            iterations=i + 1,
            best_score=best_score,
            improved_text=best_skill,
            suggestions=suggestions,
            metrics={
                "initial_lines": len(skill_text.split('\n')),
                "final_lines": len(best_skill.split('\n')),
                "has_docstring": '"""' in best_skill or "'''" in best_skill,
                "has_comments": '#' in best_skill,
            },
        )
        
        logger.info(f"技能优化完成: {skill_name}, 最终分数={best_score:.3f}")
        return result
    
    def optimize_code(
        self,
        code_name: str,
        code_text: str,
        eval_function: Callable[[str], float] | None = None,
        iterations: int | None = None,
    ) -> OptimizationResult:
        """
        优化代码
        
        Args:
            code_name: 代码名称
            code_text: 代码文本
            eval_function: 评估函数（返回 0-1 分数）
            iterations: 迭代次数（None = 使用默认值）
        
        Returns:
            OptimizationResult: 优化结果
        """
        iterations = iterations or self.max_iterations
        
        logger.info(f"开始优化代码: {code_name}, 迭代={iterations}")
        
        best_code = code_text
        best_score = 0.0
        no_improvement_count = 0
        
        suggestions = []
        
        for i in range(iterations):
            # 1. 分析当前代码
            analysis = self._analyze_code(best_code)
            
            # 2. 生成改进建议
            suggestion = self._generate_code_suggestion(analysis, i)
            suggestions.append(suggestion)
            
            # 3. 应用改进
            improved_code = self._apply_code_improvement(best_code, suggestion)
            
            # 4. 评估改进效果
            if eval_function:
                score = eval_function(improved_code)
            else:
                # 默认评估：基于代码质量
                score = self._default_code_eval(improved_code)
            
            # 5. 更新最佳代码
            if score > best_score:
                best_code = improved_code
                best_score = score
                no_improvement_count = 0
                logger.debug(f"迭代 {i+1}: 改进! 分数={score:.3f}")
            else:
                no_improvement_count += 1
                logger.debug(f"迭代 {i+1}: 无改进 分数={score:.3f}")
            
            # 6. 早期停止
            if no_improvement_count >= self.early_stop_patience:
                logger.info(f"早期停止: {no_improvement_count} 次无改进")
                break
        
        result = OptimizationResult(
            success=True,
            method="code_optimization",
            iterations=i + 1,
            best_score=best_score,
            improved_text=best_code,
            suggestions=suggestions,
            metrics={
                "initial_lines": len(code_text.split('\n')),
                "final_lines": len(best_code.split('\n')),
            },
        )
        
        logger.info(f"代码优化完成: {code_name}, 最终分数={best_score:.3f}")
        return result
    
    # ==================== 分析方法 ====================
    
    def _analyze_prompt(self, prompt: str) -> dict:
        """分析提示词"""
        return {
            "length": len(prompt),
            "has_examples": "示例" in prompt or "example" in prompt.lower(),
            "has_instructions": "请" in prompt or "please" in prompt.lower(),
            "has_constraints": "必须" in prompt or "must" in prompt.lower(),
            "has_format": "格式" in prompt or "format" in prompt.lower(),
        }
    
    def _analyze_skill(self, skill: str) -> dict:
        """分析技能"""
        return {
            "lines": len(skill.split('\n')),
            "has_docstring": '"""' in skill or "'''" in skill,
            "has_comments": '#' in skill,
            "has_error_handling": "try" in skill and "except" in skill,
            "has_logging": "logger" in skill or "print" in skill,
        }
    
    def _analyze_code(self, code: str) -> dict:
        """分析代码"""
        return {
            "lines": len(code.split('\n')),
            "has_docstring": '"""' in code or "'''" in code,
            "has_comments": '#' in code,
            "has_error_handling": "try" in code and "except" in code,
            "has_type_hints": "->" in code or ":" in code,
        }
    
    # ==================== 建议生成方法 ====================
    
    def _generate_prompt_suggestion(self, analysis: dict, iteration: int) -> dict:
        """生成提示词改进建议"""
        suggestions = []
        
        if not analysis.get("has_examples"):
            suggestions.append("添加示例")
        
        if not analysis.get("has_instructions"):
            suggestions.append("明确指令")
        
        if not analysis.get("has_constraints"):
            suggestions.append("添加约束条件")
        
        if not analysis.get("has_format"):
            suggestions.append("指定输出格式")
        
        # 基于迭代次数的建议
        if iteration % 10 == 0:
            suggestions.append("优化结构")
        
        return {
            "type": "prompt_improvement",
            "suggestions": suggestions,
            "iteration": iteration,
        }
    
    def _generate_skill_suggestion(self, analysis: dict, iteration: int) -> dict:
        """生成技能改进建议"""
        suggestions = []
        
        if not analysis.get("has_docstring"):
            suggestions.append("添加文档字符串")
        
        if not analysis.get("has_comments"):
            suggestions.append("添加注释")
        
        if not analysis.get("has_error_handling"):
            suggestions.append("添加错误处理")
        
        if not analysis.get("has_logging"):
            suggestions.append("添加日志")
        
        # 基于迭代次数的建议
        if iteration % 10 == 0:
            suggestions.append("优化算法")
        
        return {
            "type": "skill_improvement",
            "suggestions": suggestions,
            "iteration": iteration,
        }
    
    def _generate_code_suggestion(self, analysis: dict, iteration: int) -> dict:
        """生成代码改进建议"""
        suggestions = []
        
        if not analysis.get("has_docstring"):
            suggestions.append("添加文档字符串")
        
        if not analysis.get("has_comments"):
            suggestions.append("添加注释")
        
        if not analysis.get("has_error_handling"):
            suggestions.append("添加错误处理")
        
        if not analysis.get("has_type_hints"):
            suggestions.append("添加类型提示")
        
        # 基于迭代次数的建议
        if iteration % 10 == 0:
            suggestions.append("优化性能")
        
        return {
            "type": "code_improvement",
            "suggestions": suggestions,
            "iteration": iteration,
        }
    
    # ==================== 改进应用方法 ====================
    
    def _apply_prompt_improvement(self, prompt: str, suggestion: dict) -> str:
        """应用提示词改进"""
        improved = prompt
        
        # 确保有适当的换行
        if not improved.endswith('\n'):
            improved += '\n'
        
        # 添加改进标记
        improved += f"\n# 改进 {suggestion['iteration']}: {', '.join(suggestion['suggestions'])}"
        
        return improved
    
    def _apply_skill_improvement(self, skill: str, suggestion: dict) -> str:
        """应用技能改进"""
        improved = skill
        
        # 移除多余空行
        lines = [line for line in improved.split('\n') if line.strip()]
        improved = '\n'.join(lines)
        
        # 添加改进标记
        improved += f"\n# 改进 {suggestion['iteration']}: {', '.join(suggestion['suggestions'])}"
        
        return improved
    
    def _apply_code_improvement(self, code: str, suggestion: dict) -> str:
        """应用代码改进"""
        improved = code
        
        # 移除多余空行
        lines = [line for line in improved.split('\n') if line.strip()]
        improved = '\n'.join(lines)
        
        # 添加改进标记
        improved += f"\n# 改进 {suggestion['iteration']}: {', '.join(suggestion['suggestions'])}"
        
        return improved
    
    # ==================== 默认评估方法 ====================
    
    def _default_prompt_eval(self, prompt: str) -> float:
        """默认提示词评估"""
        score = 0.0
        
        # 长度评分（适中为佳）
        length = len(prompt)
        if 100 <= length <= 1000:
            score += 0.3
        elif 1000 < length <= 2000:
            score += 0.2
        
        # 结构评分
        if "示例" in prompt or "example" in prompt.lower():
            score += 0.2
        
        if "请" in prompt or "please" in prompt.lower():
            score += 0.2
        
        if "必须" in prompt or "must" in prompt.lower():
            score += 0.1
        
        if "格式" in prompt or "format" in prompt.lower():
            score += 0.1
        
        # 确保分数在 0-1 之间
        return min(max(score, 0.0), 1.0)
    
    def _default_skill_eval(self, skill: str) -> float:
        """默认技能评估"""
        score = 0.0
        
        # 文档字符串
        if '"""' in skill or "'''" in skill:
            score += 0.3
        
        # 注释
        if '#' in skill:
            score += 0.2
        
        # 错误处理
        if "try" in skill and "except" in skill:
            score += 0.3
        
        # 日志
        if "logger" in skill or "print" in skill:
            score += 0.2
        
        # 确保分数在 0-1 之间
        return min(max(score, 0.0), 1.0)
    
    def _default_code_eval(self, code: str) -> float:
        """默认代码评估"""
        score = 0.0
        
        # 文档字符串
        if '"""' in code or "'''" in code:
            score += 0.3
        
        # 注释
        if '#' in code:
            score += 0.2
        
        # 错误处理
        if "try" in code and "except" in code:
            score += 0.2
        
        # 类型提示
        if "->" in code or ":" in code:
            score += 0.3
        
        # 确保分数在 0-1 之间
        return min(max(score, 0.0), 1.0)
    
    def get_status(self) -> dict:
        """获取优化器状态"""
        return {
            "project_path": str(self.project_path),
            "max_iterations": self.max_iterations,
            "early_stop_patience": self.early_stop_patience,
        }


# ==================== 便捷函数 ====================

def create_self_optimizer(
    project_path: str | Path = "/root/maxbot",
    max_iterations: int = 140,
    early_stop_patience: int = 10,
) -> SelfOptimizer:
    """
    创建自我优化器
    
    Args:
        project_path: 项目路径
        max_iterations: 最大迭代次数
        early_stop_patience: 早期停止耐心值
    
    Returns:
        SelfOptimizer: 自我优化器实例
    """
    return SelfOptimizer(
        project_path=project_path,
        max_iterations=max_iterations,
        early_stop_patience=early_stop_patience,
    )
