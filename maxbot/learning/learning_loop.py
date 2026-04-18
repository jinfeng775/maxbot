"""
学习循环协调器 - 协调所有学习模块

功能：
- 观察用户交互
- 提取模式
- 验证模式
- 存储本能
- 应用本能
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional
import hashlib
import json
import queue
import threading
import time


@dataclass
class LearningStats:
    """学习统计"""
    total_observations: int = 0
    total_patterns_extracted: int = 0
    total_instincts_learned: int = 0
    total_instincts_applied: int = 0
    total_instincts_successful: int = 0
    last_learning_time: Optional[datetime] = None
    learning_loop_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_observations": self.total_observations,
            "total_patterns_extracted": self.total_patterns_extracted,
            "total_instincts_learned": self.total_instincts_learned,
            "total_instincts_applied": self.total_instincts_applied,
            "total_instincts_successful": self.total_instincts_successful,
            "last_learning_time": self.last_learning_time.isoformat() if self.last_learning_time else None,
            "learning_loop_count": self.learning_loop_count,
        }


class LearningLoop:
    """持续学习循环协调器"""

    def __init__(self, config=None):
        from maxbot.learning.config import LearningConfig
        from maxbot.learning.observer import Observer
        from maxbot.learning.pattern_extractor import PatternExtractor
        from maxbot.learning.pattern_validator import PatternValidator
        from maxbot.learning.instinct_store import InstinctStore
        from maxbot.learning.instinct_applier import InstinctApplier

        self.config = config or LearningConfig()
        self.observer = Observer(store_path=self.config.store_path)
        self.extractor = PatternExtractor(
            min_occurrence_count=self.config.min_occurrence_count,
            pattern_threshold=self.config.pattern_threshold,
        )
        self.validator = PatternValidator(
            validation_threshold=self.config.validation_threshold,
            min_reproducibility=self.config.min_reproducibility,
            min_value_score=self.config.min_value_score,
            min_safety=self.config.min_safety,
            min_best_practice=self.config.min_best_practice,
        )
        self.store = InstinctStore(db_path=self.config.instincts_db_path)
        self.applier = InstinctApplier(
            auto_apply_threshold=self.config.auto_apply_threshold,
            require_user_confirmation=self.config.require_user_confirmation,
        )
        self.stats = LearningStats()

        self._queue_lock = threading.Lock()
        self._pending_task_fingerprints: set[str] = set()
        self._worker_threads: List[threading.Thread] = []

        if self.config.learning_loop_async:
            self._learning_queue: Optional[queue.Queue] = queue.Queue()
            for index in range(self.config.async_worker_count):
                worker = threading.Thread(
                    target=self._learning_worker,
                    name=f"learning-worker-{index + 1}",
                    daemon=True,
                )
                worker.start()
                self._worker_threads.append(worker)
        else:
            self._learning_queue = None

    def on_user_message(
        self,
        session_id: str,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        full_context = dict(context or {})
        full_context["user_message"] = user_message

        suggestion: Optional[Dict[str, Any]] = None
        if self.config.enable_auto_apply:
            instincts = self.store.get_all_instincts(enabled_only=True)
            if instincts:
                matches = self.applier.find_matching_instincts(full_context, instincts)
                if matches:
                    best_match = matches[0]
                    if best_match.trigger_mode == "auto_apply":
                        instinct = self.store.get_instinct(best_match.instinct_id)
                        if instinct:
                            result = self.applier.apply_instinct(
                                best_match,
                                instinct,
                                require_confirmation=False,
                            )
                            self.store.record_instinct_usage(instinct.id, result.success)
                            self.stats.total_instincts_applied += 1
                            if result.success:
                                self.stats.total_instincts_successful += 1
                            suggestion = {
                                "match": best_match.to_dict(),
                                "application": result.to_dict(),
                            }
                    elif best_match.trigger_mode == "suggest":
                        suggestion = best_match.to_dict()

        if self.config.enable_tool_tracking:
            self.observer.start_observation(
                session_id=session_id,
                user_message=user_message,
                context=full_context,
            )

        return suggestion

    def on_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        call_id: Optional[str] = None,
    ):
        if self.config.enable_tool_tracking:
            self.observer.record_tool_call(tool_name, arguments, call_id)

    def on_tool_result(
        self,
        tool_name: str,
        success: bool,
        result_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        call_id: Optional[str] = None,
    ):
        if self.config.enable_tool_tracking:
            self.observer.record_tool_result(
                tool_name,
                success,
                result_data,
                error,
                call_id,
            )

    def on_session_end(self, session_id: str):
        if self.config.enable_tool_tracking and self.observer._current_observation is not None:
            self.observer.end_observation()

        if self.config.learning_loop_async:
            self._enqueue_task("session", {"session_id": session_id})
            return

        try:
            self._run_learning_loop(session_id)
        except Exception as exc:
            if self.config.enable_logging:
                print(f"⚠️  Learning loop error: {exc}")

    def on_error(self, error: str, context: Optional[Dict[str, Any]] = None):
        if not self.config.enable_error_tracking:
            return

        full_context = dict(context or {})
        full_context["error"] = error

        if self.config.learning_loop_async:
            self._enqueue_task("error", full_context)
            return

        try:
            self._run_error_learning(error, full_context)
        except Exception as exc:
            if self.config.enable_logging:
                print(f"⚠️  Error learning failed: {exc}")

    def apply_instinct(
        self,
        instinct_id: str,
        confirm: Optional[bool] = None,
    ) -> Dict[str, Any]:
        from maxbot.learning.instinct_applier import MatchResult

        instinct = self.store.get_instinct(instinct_id)
        if not instinct:
            return {"success": False, "error": "Instinct not found"}

        match_result = MatchResult(
            instinct_id=instinct.id,
            instinct_name=instinct.name,
            match_score=1.0,
            match_type="manual",
            confidence=1.0,
            confidence_tier="high",
            trigger_mode="auto_apply",
        )
        result = self.applier.apply_instinct(match_result, instinct, confirm)
        self.store.record_instinct_usage(instinct_id, result.success)
        self.stats.total_instincts_applied += 1
        if result.success:
            self.stats.total_instincts_successful += 1
        return result.to_dict()

    def get_learning_stats(self) -> Dict[str, Any]:
        return {
            "learning_stats": self.stats.to_dict(),
            "store_stats": self.store.get_statistics(),
        }

    def cleanup_old_data(self):
        deleted = self.store.cleanup_old_instincts(
            days=self.config.instinct_retention_days,
            max_count=self.config.max_instincts,
        )
        if self.config.enable_logging and deleted > 0:
            print(f"🧹 Cleaned up {deleted} old instinct(s)")

    def shutdown(self):
        if self._learning_queue is not None:
            self._learning_queue.join()
        if self.config.enable_logging:
            print("🔴 Learning loop shutdown complete")

    def _run_learning_loop(self, session_id: str):
        observations = self.observer.get_session_observations(session_id, include_failed=True)
        self.stats.total_observations += len(observations)
        if len(observations) < self.config.min_session_length:
            return

        start_time = time.time()
        patterns = self.extractor.extract_patterns(
            observations,
            enable_tool_sequence=self.config.enable_tool_sequence,
            enable_error_solution=self.config.enable_error_solution,
            enable_user_preference=self.config.enable_user_preference,
        )
        self.stats.total_patterns_extracted += len(patterns)

        learned = 0
        for pattern in patterns:
            if self._validate_and_persist(pattern):
                learned += 1

        self.stats.total_instincts_learned += learned
        self.stats.last_learning_time = datetime.now()
        self.stats.learning_loop_count += 1

        elapsed = time.time() - start_time
        if self.config.enable_logging and elapsed > self.config.max_pattern_extract_time:
            print(f"⚠️  Learning loop took {elapsed:.2f}s (max: {self.config.max_pattern_extract_time}s)")

    def _run_error_learning(self, error: str, context: Dict[str, Any]):
        start_time = time.time()
        pattern = self.extractor.extract_error_pattern(error, context)
        if not pattern:
            return

        self.stats.total_patterns_extracted += 1
        learned = 1 if self._validate_and_persist(pattern) else 0
        self.stats.total_instincts_learned += learned
        self.stats.last_learning_time = datetime.now()
        self.stats.learning_loop_count += 1

        elapsed = time.time() - start_time
        if self.config.enable_logging and elapsed > self.config.max_validation_time:
            print(f"⚠️  Error learning took {elapsed:.2f}s (max: {self.config.max_validation_time}s)")

    def _validate_and_persist(self, pattern) -> bool:
        validation = self.validator.validate(pattern)
        if not validation.approved:
            if self.config.enable_logging:
                print(
                    f"ℹ️  Rejected pattern {pattern.id}: "
                    f"{'; '.join(validation.reasons) or 'validation failed'}"
                )
            return False

        before = self.store.get_statistics()["total_count"]
        validation_payload = validation.score.to_dict()
        validation_payload.update(
            {
                "overall": validation.score.overall,
                "confidence": validation.confidence,
                "approved": validation.approved,
                "rejected": validation.rejected,
                "reasons": validation.reasons,
            }
        )
        self.store.save_instinct(
            pattern_id=pattern.id,
            name=pattern.name,
            pattern_type=pattern.pattern_type,
            pattern_data=pattern.data,
            validation_score=validation_payload,
            tags=pattern.tags,
            description=pattern.description,
        )
        after = self.store.get_statistics()["total_count"]
        return after >= before

    def _enqueue_task(self, task_type: str, task_data: Dict[str, Any]):
        if self._learning_queue is None:
            return

        fingerprint = self._make_task_fingerprint(task_type, task_data)
        with self._queue_lock:
            if fingerprint in self._pending_task_fingerprints:
                return
            self._pending_task_fingerprints.add(fingerprint)

        self._learning_queue.put(
            {
                "task_type": task_type,
                "task_data": task_data,
                "retry_count": 0,
                "fingerprint": fingerprint,
            }
        )

    def _learning_worker(self):
        while True:
            if self._learning_queue is None:
                return
            try:
                task = self._learning_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            fingerprint = task["fingerprint"]
            try:
                if task["task_type"] == "session":
                    self._run_learning_loop(task["task_data"]["session_id"])
                elif task["task_type"] == "error":
                    payload = task["task_data"]
                    self._run_error_learning(payload.get("error", ""), payload)

                with self._queue_lock:
                    self._pending_task_fingerprints.discard(fingerprint)
            except Exception as exc:
                retry_count = task["retry_count"]
                if retry_count < self.config.async_retry_limit:
                    task["retry_count"] += 1
                    time.sleep(self.config.async_retry_backoff * (2 ** retry_count))
                    self._learning_queue.put(task)
                else:
                    with self._queue_lock:
                        self._pending_task_fingerprints.discard(fingerprint)
                    if self.config.enable_logging:
                        print(f"⚠️  Learning worker error: {exc}")
            finally:
                self._learning_queue.task_done()

    def _make_task_fingerprint(self, task_type: str, task_data: Dict[str, Any]) -> str:
        if task_type == "session":
            return f"session:{task_data.get('session_id', 'unknown')}"
        payload = json.dumps(task_data, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.md5(f"{task_type}:{payload}".encode("utf-8")).hexdigest()
        return f"{task_type}:{digest}"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
