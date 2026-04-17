"""
性能监控器 - 监控和统计性能指标

功能:
1. 记录关键操作耗时
2. 统计优化效果
3. 生成性能报告
"""

from dataclasses import dataclass, field
from typing import Any
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricStats:
    """指标统计"""
    count: int = 0  # 调用次数
    total_time: float = 0  # 总耗时
    min_time: float = float('inf')  # 最小耗时
    max_time: float = 0  # 最大耗时
    last_time: float = 0  # 上次耗时
    
    def update(self, duration: float) -> None:
        """更新统计"""
        self.count += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.last_time = duration
    
    @property
    def avg_time(self) -> float:
        """平均耗时"""
        return self.total_time / self.count if self.count > 0 else 0


class PerformanceMonitor:
    """
    性能监控器
    
    功能:
    - 记录关键操作耗时
    - 统计优化效果
    - 生成性能报告
    """
    
    def __init__(self):
        self._metrics: dict[str, MetricStats] = {}
        self._start_time = time.time()
        self._enabled = True
    
    def enable(self):
        """启用监控"""
        self._enabled = True
        logger.debug("性能监控已启用")
    
    def disable(self):
        """禁用监控"""
        self._enabled = False
        logger.debug("性能监控已禁用")
    
    def record(self, metric_name: str, duration: float) -> None:
        """
        记录指标
        
        Args:
            metric_name: 指标名称
            duration: 耗时（秒）
        """
        if not self._enabled:
            return
        
        if metric_name not in self._metrics:
            self._metrics[metric_name] = MetricStats()
        
        self._metrics[metric_name].update(duration)
    
    def start_timer(self, metric_name: str) -> "Timer":
        """
        启动计时器
        
        Args:
            metric_name: 指标名称
        
        Returns:
            Timer: 计时器对象
        """
        return Timer(self, metric_name)
    
    def get_stats(self, metric_name: str | None = None) -> dict[str, Any]:
        """
        获取统计信息
        
        Args:
            metric_name: 指标名称（None = 获取所有指标）
        
        Returns:
            dict: 统计信息
        """
        if metric_name:
            if metric_name not in self._metrics:
                return {}
            stats = self._metrics[metric_name]
            return {
                "count": stats.count,
                "total_time": stats.total_time,
                "avg_time": stats.avg_time,
                "min_time": stats.min_time if stats.count > 0 else 0,
                "max_time": stats.max_time,
                "last_time": stats.last_time,
            }
        
        # 获取所有指标
        return {
            name: {
                "count": stats.count,
                "total_time": stats.total_time,
                "avg_time": stats.avg_time,
                "min_time": stats.min_time if stats.count > 0 else 0,
                "max_time": stats.max_time,
                "last_time": stats.last_time,
            }
            for name, stats in self._metrics.items()
        }
    
    def get_total_time(self) -> float:
        """
        获取总运行时间
        
        Returns:
            float: 总运行时间（秒）
        """
        return time.time() - self._start_time
    
    def print_report(self, detailed: bool = False) -> str:
        """
        打印性能报告
        
        Args:
            detailed: 是否显示详细信息
        
        Returns:
            str: 格式化的性能报告
        """
        total_time = self.get_total_time()
        lines = [
            "📊 性能监控报告",
            "=" * 70,
            f"总运行时间: {total_time:.2f}s",
            f"监控指标数: {len(self._metrics)}",
            ""
        ]
        
        if not self._metrics:
            lines.append("暂无性能数据")
            return "\n".join(lines)
        
        # 按总耗时排序
        sorted_metrics = sorted(
            self._metrics.items(),
            key=lambda x: x[1].total_time,
            reverse=True
        )
        
        for name, stats in sorted_metrics:
            lines.append(f"🔹 {name}")
            lines.append(f"  调用次数: {stats.count}")
            lines.append(f"  平均耗时: {stats.avg_time:.4f}s")
            lines.append(f"  最小耗时: {stats.min_time:.4f}s")
            lines.append(f"  最大耗时: {stats.max_time:.4f}s")
            lines.append(f"  总耗时: {stats.total_time:.4f}s")
            lines.append(f"  占比: {stats.total_time / total_time * 100:.1f}%")
            
            if detailed:
                lines.append(f"  上次耗时: {stats.last_time:.4f}s")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def print_summary(self) -> str:
        """
        打印性能摘要
        
        Returns:
            str: 格式化的性能摘要
        """
        total_time = self.get_total_time()
        lines = [
            "📊 性能摘要",
            "=" * 70,
            f"总运行时间: {total_time:.2f}s",
            f"监控指标数: {len(self._metrics)}",
            ""
        ]
        
        if not self._metrics:
            lines.append("暂无性能数据")
            return "\n".join(lines)
        
        # 计算总调用次数
        total_calls = sum(stats.count for stats in self._metrics.values())
        
        # 找出最慢的操作
        slowest = max(self._metrics.items(), key=lambda x: x[1].avg_time)
        # 找出调用最多的操作
        most_called = max(self._metrics.items(), key=lambda x: x[1].count)
        # 找出总耗时最多的操作
        most_time = max(self._metrics.items(), key=lambda x: x[1].total_time)
        
        lines.append(f"总调用次数: {total_calls}")
        lines.append(f"平均每次调用耗时: {total_time / total_calls:.4f}s" if total_calls > 0 else "平均每次调用耗时: 0s")
        lines.append("")
        lines.append(f"最慢的操作: {slowest[0]} (平均 {slowest[1].avg_time:.4f}s)")
        lines.append(f"调用最多的操作: {most_called[0]} ({most_called[1].count} 次)")
        lines.append(f"总耗时最多的操作: {most_time[0]} ({most_time[1].total_time:.4f}s)")
        lines.append("")
        
        return "\n".join(lines)
    
    def reset(self):
        """重置所有统计"""
        self._metrics.clear()
        self._start_time = time.time()
        logger.debug("性能监控统计已重置")
    
    def export_metrics(self) -> dict[str, Any]:
        """
        导出指标数据
        
        Returns:
            dict: 指标数据
        """
        return {
            "total_time": self.get_total_time(),
            "metrics": self.get_stats(),
            "start_time": self._start_time,
        }


class Timer:
    """
    计时器
    
    用法:
        with monitor.start_timer("operation_name"):
            # 执行操作
            pass
    """
    
    def __init__(self, monitor: PerformanceMonitor, metric_name: str):
        self._monitor = monitor
        self._metric_name = metric_name
        self._start_time = None
    
    def __enter__(self):
        self._start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._start_time is not None:
            duration = time.time() - self._start_time
            self._monitor.record(self._metric_name, duration)
    
    def stop(self):
        """手动停止计时"""
        if self._start_time is not None:
            duration = time.time() - self._start_time
            self._monitor.record(self._metric_name, duration)
            self._start_time = None


# 上下文管理器快捷方式
def monitor_performance(monitor: PerformanceMonitor, metric_name: str) -> Timer:
    """
    性能监控快捷方式
    
    Args:
        monitor: 性能监控器
        metric_name: 指标名称
    
    Returns:
        Timer: 计时器对象
    """
    return monitor.start_timer(metric_name)
