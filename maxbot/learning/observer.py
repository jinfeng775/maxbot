"""
观察模块 - 监控用户交互和工具调用

功能：
- 记录用户消息
- 记录工具调用
- 记录工具结果
- 记录会话上下文
- 提供查询接口
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import os
from pathlib import Path


@dataclass
class ToolCall:
    """工具调用记录"""
    tool_name: str
    arguments: Dict[str, Any]
    timestamp: datetime
    call_id: Optional[str] = None

    @staticmethod
    def _sanitize_for_json(obj):
        """清理对象使其可 JSON 序列化"""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [ToolCall._sanitize_for_json(item) for item in obj]
        elif isinstance(obj, dict):
            return {str(k): ToolCall._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, set):
            return [ToolCall._sanitize_for_json(item) for item in obj]
        else:
            return str(obj)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tool_name": self.tool_name,
            "arguments": self._sanitize_for_json(self.arguments),
            "timestamp": self.timestamp.isoformat(),
            "call_id": self.call_id
        }


@dataclass
class ToolResult:
    """工具结果记录"""
    tool_name: str
    success: bool
    duration: float
    error: Optional[str]
    result_data: Optional[Dict[str, Any]]
    timestamp: datetime
    call_id: Optional[str] = None

    @staticmethod
    def _sanitize_for_json(obj):
        """清理对象使其可 JSON 序列化"""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [ToolResult._sanitize_for_json(item) for item in obj]
        elif isinstance(obj, dict):
            return {str(k): ToolResult._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, set):
            return [ToolResult._sanitize_for_json(item) for item in obj]
        else:
            return str(obj)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "duration": self.duration,
            "error": self.error,
            "result_data": self._sanitize_for_json(self.result_data),
            "timestamp": self.timestamp.isoformat(),
            "call_id": self.call_id
        }


@dataclass
class Observation:
    """单次交互观察记录"""
    session_id: str
    timestamp: datetime
    user_message: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    success: bool = True
    context: Dict[str, Any] = field(default_factory=dict)
    observation_id: Optional[str] = None

    def _sanitize_for_json(self, obj):
        """清理对象使其可 JSON 序列化

        Args:
            obj: 要清理的对象

        Returns:
            清理后的对象
        """
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [self._sanitize_for_json(item) for item in obj]
        elif isinstance(obj, dict):
            return {str(k): self._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, set):
            return [self._sanitize_for_json(item) for item in obj]
        else:
            # 其他类型转换为字符串
            return str(obj)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "user_message": self.user_message,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "tool_results": [tr.to_dict() for tr in self.tool_results],
            "success": self.success,
            "context": self._sanitize_for_json(self.context),
            "observation_id": self.observation_id
        }


class Observer:
    """观察器 - 监控用户交互和工具调用"""

    def __init__(self, store_path: str = "~/.maxbot/observations"):
        """初始化观察器

        Args:
            store_path: 观察记录存储路径
        """
        self.store_path = Path(store_path).expanduser()
        self.store_path.mkdir(parents=True, exist_ok=True)

        # 内存中的观察记录
        self._observations: Dict[str, List[Observation]] = {}
        self._current_observation: Optional[Observation] = None

        # 工具调用计时
        self._call_timings: Dict[str, datetime] = {}

    def _sanitize_message(self, message: str) -> str:
        """清理消息中的敏感信息

        Args:
            message: 原始消息

        Returns:
            清理后的消息
        """
        # 过滤常见的敏感信息关键词
        sensitive_keywords = [
            "password", "token", "api_key", "secret", "key",
            "authorization", "bearer", "credentials"
        ]

        # 简单的敏感信息过滤（实际应用中需要更复杂的逻辑）
        sanitized = message
        for keyword in sensitive_keywords:
            # 只是为了演示，实际需要更智能的过滤
            if keyword.lower() in sanitized.lower():
                sanitized = sanitized.replace(sanitized, "[SANITIZED]")

        return sanitized

    def start_observation(
        self,
        session_id: str,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Observation:
        """开始一个新的观察

        Args:
            session_id: 会话 ID
            user_message: 用户消息
            context: 额外的上下文信息

        Returns:
            创建的观察对象
        """
        # 清理敏感信息
        sanitized_message = self._sanitize_message(user_message)

        # 创建观察对象
        observation = Observation(
            session_id=session_id,
            timestamp=datetime.now(),
            user_message=sanitized_message,
            context=context or {}
        )

        # 保存当前观察
        self._current_observation = observation

        # 添加到会话观察列表
        if session_id not in self._observations:
            self._observations[session_id] = []
        self._observations[session_id].append(observation)

        return observation

    def record_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        call_id: Optional[str] = None
    ) -> ToolCall:
        """记录工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            call_id: 调用 ID（可选）

        Returns:
            创建的工具调用对象
        """
        if self._current_observation is None:
            raise RuntimeError("No active observation to record tool call")

        # 创建工具调用记录
        tool_call = ToolCall(
            tool_name=tool_name,
            arguments=arguments,
            timestamp=datetime.now(),
            call_id=call_id
        )

        # 添加到当前观察
        self._current_observation.tool_calls.append(tool_call)

        # 记录调用开始时间
        if call_id:
            self._call_timings[call_id] = tool_call.timestamp

        return tool_call

    def record_tool_result(
        self,
        tool_name: str,
        success: bool,
        result_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        call_id: Optional[str] = None
    ) -> ToolResult:
        """记录工具结果

        Args:
            tool_name: 工具名称
            success: 是否成功
            result_data: 结果数据
            error: 错误信息
            call_id: 调用 ID（可选）

        Returns:
            创建的工具结果对象
        """
        if self._current_observation is None:
            raise RuntimeError("No active observation to record tool result")

        # 计算调用时长
        duration = 0.0
        if call_id and call_id in self._call_timings:
            start_time = self._call_timings[call_id]
            duration = (datetime.now() - start_time).total_seconds()
            del self._call_timings[call_id]

        # 创建工具结果记录
        tool_result = ToolResult(
            tool_name=tool_name,
            success=success,
            duration=duration,
            error=error,
            result_data=result_data,
            timestamp=datetime.now(),
            call_id=call_id
        )

        # 添加到当前观察
        self._current_observation.tool_results.append(tool_result)

        # 如果工具调用失败，标记观察为失败
        if not success:
            self._current_observation.success = False

        return tool_result

    def end_observation(self, success: Optional[bool] = None) -> Observation:
        """结束当前观察

        Args:
            success: 是否成功（可选，覆盖自动判断）

        Returns:
            结束的观察对象
        """
        if self._current_observation is None:
            raise RuntimeError("No active observation to end")

        # 设置成功状态
        if success is not None:
            self._current_observation.success = success

        # 保存到文件
        self._save_observation(self._current_observation)

        # 返回并清除当前观察
        observation = self._current_observation
        self._current_observation = None

        return observation

    def get_session_observations(
        self,
        session_id: str,
        include_failed: bool = False
    ) -> List[Observation]:
        """获取会话的所有观察

        Args:
            session_id: 会话 ID
            include_failed: 是否包含失败的观察

        Returns:
            观察列表
        """
        observations = self._observations.get(session_id, [])

        if not include_failed:
            observations = [obs for obs in observations if obs.success]

        return observations

    def get_all_observations(self, include_failed: bool = False) -> List[Observation]:
        """获取所有观察

        Args:
            include_failed: 是否包含失败的观察

        Returns:
            观察列表
        """
        all_obs = []
        for observations in self._observations.values():
            all_obs.extend(observations)

        if not include_failed:
            all_obs = [obs for obs in all_obs if obs.success]

        return all_obs

    def _save_observation(self, observation: Observation):
        """保存观察到文件

        Args:
            observation: 要保存的观察
        """
        # 创建会话目录
        session_dir = self.store_path / observation.session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        timestamp = observation.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"obs_{timestamp}.json"
        filepath = session_dir / filename

        # 保存到文件
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(observation.to_dict(), f, indent=2, ensure_ascii=False)

    def load_observations(
        self,
        session_id: Optional[str] = None,
        include_failed: bool = False
    ) -> List[Observation]:
        """从文件加载观察记录

        Args:
            session_id: 会话 ID（None 表示加载所有会话）
            include_failed: 是否包含失败的观察

        Returns:
            观察列表
        """
        observations = []

        # 确定要加载的目录
        if session_id:
            session_dirs = [self.store_path / session_id]
        else:
            session_dirs = [
                d for d in self.store_path.iterdir()
                if d.is_dir()
            ]

        # 加载每个会话的观察
        for session_dir in session_dirs:
            if not session_dir.exists():
                continue

            for filepath in session_dir.glob("obs_*.json"):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # 转换为 Observation 对象
                    observation = self._dict_to_observation(data)

                    # 过滤失败的观察
                    if not include_failed and not observation.success:
                        continue

                    observations.append(observation)

                except Exception as e:
                    print(f"⚠️  Failed to load observation {filepath}: {e}")

        return observations

    def _dict_to_observation(self, data: Dict[str, Any]) -> Observation:
        """从字典转换为 Observation 对象

        Args:
            data: 字典数据

        Returns:
            Observation 对象
        """
        # 转换工具调用
        tool_calls = [
            ToolCall(
                tool_name=tc["tool_name"],
                arguments=tc["arguments"],
                timestamp=datetime.fromisoformat(tc["timestamp"]),
                call_id=tc.get("call_id")
            )
            for tc in data.get("tool_calls", [])
        ]

        # 转换工具结果
        tool_results = [
            ToolResult(
                tool_name=tr["tool_name"],
                success=tr["success"],
                duration=tr["duration"],
                error=tr.get("error"),
                result_data=tr.get("result_data"),
                timestamp=datetime.fromisoformat(tr["timestamp"]),
                call_id=tr.get("call_id")
            )
            for tr in data.get("tool_results", [])
        ]

        # 创建 Observation 对象
        return Observation(
            session_id=data["session_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            user_message=data["user_message"],
            tool_calls=tool_calls,
            tool_results=tool_results,
            success=data["success"],
            context=data.get("context", {}),
            observation_id=data.get("observation_id")
        )

    def clear_observations(self, session_id: Optional[str] = None):
        """清除观察记录

        Args:
            session_id: 会话 ID（None 表示清除所有会话）
        """
        if session_id:
            if session_id in self._observations:
                del self._observations[session_id]
        else:
            self._observations.clear()

        self._current_observation = None
