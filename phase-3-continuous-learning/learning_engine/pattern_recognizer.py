"""
模式识别器

负责从用户交互中识别重复的模式和成功策略。
"""

import re
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import logging

logger = logging.getLogger(__name__)


@dataclass
class Pattern:
    """模式定义"""
    id: str
    name: str
    pattern_type: str  # code_pattern, behavior_pattern, error_pattern, etc.
    description: str
    trigger_conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    success_criteria: Dict[str, Any]
    statistics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'pattern_type': self.pattern_type,
            'description': self.description,
            'trigger_conditions': self.trigger_conditions,
            'actions': self.actions,
            'success_criteria': self.success_criteria,
            'statistics': self.statistics
        }


@dataclass
class Observation:
    """观察记录"""
    timestamp: str
    user_id: str
    session_id: str
    action: str
    parameters: Dict[str, Any]
    result: Dict[str, Any]
    error: Optional[str]
    context: Dict[str, Any]


class PatternRecognizer:
    """模式识别器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.patterns: List[Pattern] = []
        self.observations: List[Observation] = []
        self.min_occurrences = self.config.get('min_occurrences', 3)
        self.success_rate_threshold = self.config.get('success_rate_threshold', 0.7)
        self.context_similarity_threshold = self.config.get('context_similarity_threshold', 0.8)

    def add_observation(self, observation: Observation):
        """添加观察记录"""
        self.observations.append(observation)
        logger.debug(f"Added observation: {observation.action}")

    def recognize_patterns(self) -> List[Pattern]:
        """识别模式"""
        logger.info(f"Recognizing patterns from {len(self.observations)} observations")

        # 1. 提取操作序列
        action_sequences = self._extract_action_sequences()

        # 2. 统计高频序列
        high_frequency_sequences = self._find_high_frequency_sequences(action_sequences)

        # 3. 分析序列中的模式
        patterns = self._analyze_sequences_for_patterns(high_frequency_sequences)

        # 4. 过滤和排序模式
        filtered_patterns = self._filter_and_rank_patterns(patterns)

        logger.info(f"Recognized {len(filtered_patterns)} patterns")
        return filtered_patterns

    def _extract_action_sequences(self) -> List[List[str]]:
        """提取操作序列"""
        sequences = []
        current_sequence = []

        for obs in self.observations:
            action = obs.action
            current_sequence.append(action)

            # 检测序列结束条件
            if self._is_sequence_end(obs):
                if len(current_sequence) >= 2:
                    sequences.append(current_sequence[:])
                current_sequence = []

        if current_sequence:
            sequences.append(current_sequence)

        return sequences

    def _is_sequence_end(self, obs: Observation) -> bool:
        """判断是否序列结束"""
        # 如果有错误，序列结束
        if obs.error:
            return True

        # 如果结果是成功的，可能是序列结束
        if obs.result.get('success'):
            return True

        return False

    def _find_high_frequency_sequences(self, sequences: List[List[str]]) -> List[tuple]:
        """查找高频序列"""
        sequence_counter = Counter()

        for seq in sequences:
            # 将序列转换为元组以便计数
            seq_tuple = tuple(seq)
            sequence_counter[seq_tuple] += 1

        # 找出高频序列
        high_frequency = [
            (list(seq), count)
            for seq, count in sequence_counter.items()
            if count >= self.min_occurrences
        ]

        # 按频率排序
        high_frequency.sort(key=lambda x: x[1], reverse=True)

        return high_frequency

    def _analyze_sequences_for_patterns(self, sequences: List[tuple]) -> List[Pattern]:
        """分析序列中的模式"""
        patterns = []

        for seq, frequency in sequences:
            # 分析序列特征
            pattern = self._analyze_sequence(seq, frequency)
            if pattern:
                patterns.append(pattern)

        return patterns

    def _analyze_sequence(self, sequence: List[str], frequency: int) -> Optional[Pattern]:
        """分析单个序列"""
        if len(sequence) < 2:
            return None

        # 识别模式类型
        pattern_type = self._identify_pattern_type(sequence)

        # 提取模式特征
        pattern_id = f"{pattern_type}_{hash('.'.join(sequence))[:8]}"
        pattern_name = self._generate_pattern_name(sequence, pattern_type)

        # 提取触发条件
        trigger_conditions = self._extract_trigger_conditions(sequence)

        # 提取动作
        actions = self._extract_actions(sequence)

        # 提取成功标准
        success_criteria = {
            'occurrence_count': frequency,
            'min_occurrences': self.min_occurrences
        }

        return Pattern(
            id=pattern_id,
            name=pattern_name,
            pattern_type=pattern_type,
            description=f"Auto-generated {pattern_type} pattern",
            trigger_conditions=trigger_conditions,
            actions=actions,
            success_criteria=success_criteria,
            statistics={'occurrence_count': frequency}
        )

    def _identify_pattern_type(self, sequence: List[str]) -> str:
        """识别模式类型"""
        # 根据序列内容识别类型
        if 'test' in sequence and 'write' in sequence:
            return 'tdd_workflow'
        elif 'analyze' in sequence:
            return 'code_analysis'
        elif 'generate' in sequence:
            return 'code_generation'
        elif 'error' in [s.lower() for s in sequence]:
            return 'error_resolution'
        elif 'security' in [s.lower() for s in sequence]:
            return 'security_review'
        else:
            return 'general_workflow'

    def _generate_pattern_name(self, sequence: List[str], pattern_type: str) -> str:
        """生成模式名称"""
        # 使用序列的前几个动作作为名称
        first_actions = '_'.join(sequence[:3])
        return f"{pattern_type}_{first_actions}"

    def _extract_trigger_conditions(self, sequence: List[str]) -> Dict[str, Any]:
        """提取触发条件"""
        conditions = {
            'action_sequence': sequence
        }

        # 查找特定的触发条件
        if 'test' in sequence:
            conditions['has_test_action'] = True
        if 'error' in [s.lower() for s in sequence]:
            conditions['has_error'] = True
        if 'analyze' in sequence:
            conditions['has_analyze_action'] = True

        return conditions

    def _extract_actions(self, sequence: List[str]]) -> List[Dict[str, Any]]:
        """提取动作"""
        actions = []

        for action in sequence:
            actions.append({
                'type': 'execute_action',
                'action': action,
                'description': f"Execute {action}"
            })

        return actions

    def _filter_and_rank_patterns(self, patterns: List[Pattern]) -> List[Pattern]:
        """过滤和排序模式"""
        filtered = []

        for pattern in patterns:
            # 检查是否满足最低出现次数
            occ_count = pattern.statistics.get('occurrence_count', 0)
            if occ_count >= self.min_occurrences:
                filtered.append(pattern)

        # 按出现次数排序
        filtered.sort(key=lambda p: p.statistics.get('occurrence_count', 0), reverse=True)

        return filtered

    def match_pattern(self, pattern: Pattern, context: Dict[str, Any]) -> bool:
        """检查模式是否匹配"""
        # 检查触发条件
        trigger_conditions = pattern.trigger_conditions

        # 检查操作序列
        if 'action_sequence' in trigger_conditions:
            # 这里需要实现序列匹配逻辑
            return True  # 简化实现

        # 检查其他条件
        if 'has_test_action' in trigger_conditions:
            if 'test' not in str(context).lower():
                return False

        return True

    def load_patterns_from_file(self, file_path: str) -> List[Pattern]:
        """从文件加载模式"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            patterns = []
            for pattern_data in data.get('patterns', []):
                pattern = Pattern(**pattern_data)
                patterns.append(pattern)

            self.patterns = patterns
            logger.info(f"Loaded {len(patterns)} patterns from {file_path}")
            return patterns

        except Exception as e:
            logger.error(f"Failed to load patterns from {file_path}: {e}")
            return []

    def save_patterns_to_file(self, file_path: str) -> bool:
        """保存模式到文件"""
        try:
            data = {
                'version': '1.0.0',
                'patterns': [p.to_dict() for p in self.patterns]
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(self.patterns)} patterns to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save patterns to {file_path}: {e}")
            return False

    def get_pattern_statistics(self) -> Dict[str, Any]:
        """获取模式统计信息"""
        return {
            'total_patterns': len(self.patterns),
            'total_observations': len(self.observations),
            'patterns_by_type': self._count_patterns_by_type(),
            'high_frequency_patterns': self._get_high_frequency_patterns(5)
        }

    def _count_patterns_by_type(self) -> Dict[str, int]:
        """按类型统计模式"""
        type_counter = Counter()
        for pattern in self.patterns:
            type_counter[pattern.pattern_type] += 1
        return dict(type_counter)

    def _get_high_frequency_patterns(self, n: int) -> List[Dict[str, Any]]:
        """获取高频模式"""
        sorted_patterns = sorted(
            self.patterns,
            key=lambda p: p.statistics.get('occurrence_count', 0),
            reverse=True
        )
        return [
            {
                'id': p.id,
                'name': p.name,
                'type': p.pattern_type,
                'occurrences': p.statistics.get('occurrence_count', 0)
            }
            for p in sorted_patterns[:n]
        ]
