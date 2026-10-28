"""내 PC의 로컬 JSON 파일(data/routine-settings.json)에 하루 학습 목표와 복습 활동 로그를 저장하고 연속 학습 루틴을 집계하는 모듈."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import pathlib
import threading
from typing import Any
import uuid

from src.feedback_types import FeedbackRecord, ValidationError
from src.routine_types import (
    RECENT_CALENDAR_DAYS,
    DailyGoal,
    ReviewLogEntry,
    calculate_streaks,
    iso_to_local_date_str,
)
from src.vocab_types import VocabItem

DEFAULT_ROUTINE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "data" / "routine-settings.json"
)


class RoutineStore:
    """하루 학습 목표와 일자별 복습 로그를 원자적으로 보관하고 전체 학습 루틴·스트릭을 집계한다([R1]~[R3] 보장)."""

    def __init__(self, file_path: pathlib.Path | None = None) -> None:
        self.file_path = file_path or DEFAULT_ROUTINE_PATH
        self._lock = threading.Lock()

    def get_goal(self) -> DailyGoal:
        """현재 설정된 하루 학습 목표를 반환한다(설정 파일이 없으면 기본값 첨삭 1·복습 3)."""
        with self._lock:
            goal, _ = self._read_state_unlocked()
            return goal

    def save_goal(self, goal: DailyGoal) -> DailyGoal:
        """새로운 하루 학습 목표를 로컬 파일에 즉시 저장하고 반환한다([R1], [R3] 보장)."""
        with self._lock:
            _, logs = self._read_state_unlocked()
            self._write_state_unlocked(goal, logs)
            return goal

    def record_review(
        self,
        item: VocabItem,
        rating: str,
        today: date | None = None,
    ) -> ReviewLogEntry:
        """단어 복습 완료 시 일자별 복습 활동 로그를 추가하고 원자적으로 저장한다([R2], [R3] 보장)."""
        base_today = today if today is not None else date.today()
        now_iso = item.last_reviewed_at or datetime.now(timezone.utc).isoformat()
        entry = ReviewLogEntry(
            date=base_today.isoformat(),
            vocab_id=item.id,
            expression=item.expression,
            meaning=item.meaning,
            rating=rating,
            reviewed_at=now_iso,
        )
        with self._lock:
            goal, logs = self._read_state_unlocked()
            updated_logs = [entry, *logs]
            self._write_state_unlocked(goal, updated_logs)
            return entry

    def build_routine_summary(
        self,
        feedback_records: list[FeedbackRecord],
        vocab_items: list[VocabItem],
        today: date | None = None,
    ) -> dict[str, Any]:
        """첨삭 기록·단어장·복습 로그를 종합하여 연속 학습일, 오늘 목표 진행률, 최근 14일 달력 및 일자별 내역을 반환한다."""
        base_today = today if today is not None else date.today()
        today_str = base_today.isoformat()

        with self._lock:
            goal, review_logs = self._read_state_unlocked()

        # 1) 날짜별 첨삭 내역 집계
        feedbacks_by_date: dict[str, list[dict[str, Any]]] = {}
        for rec in feedback_records:
            d_str = iso_to_local_date_str(rec.created_at, fallback_today=base_today)
            feedbacks_by_date.setdefault(d_str, []).append(
                {
                    "id": rec.id,
                    "text": rec.text,
                    "corrected": rec.feedback.corrected,
                    "inputMode": rec.input_mode,
                    "createdAt": rec.created_at,
                }
            )

        # 2) 날짜별 복습 내역 집계 (명시적 복습 로그 + 기존 VocabItem.lastReviewedAt 하위 호환)
        reviews_by_date: dict[str, list[dict[str, Any]]] = {}
        logged_vocab_dates: set[tuple[str, str]] = set()
        for entry in review_logs:
            reviews_by_date.setdefault(entry.date, []).append(entry.to_dict())
            logged_vocab_dates.add((entry.date, entry.vocab_id))

        for item in vocab_items:
            if item.review_count > 0 and item.last_reviewed_at:
                d_str = iso_to_local_date_str(
                    item.last_reviewed_at, fallback_today=base_today
                )
                if (d_str, item.id) not in logged_vocab_dates:
                    reviews_by_date.setdefault(d_str, []).append(
                        {
                            "date": d_str,
                            "vocabId": item.id,
                            "expression": item.expression,
                            "meaning": item.meaning,
                            "rating": "easy" if item.box >= 1 else "again",
                            "reviewedAt": item.last_reviewed_at,
                        }
                    )

        # 3) 학습이 이루어진 모든 날짜 집합 및 연속 학습일(스트릭) 계산
        all_dates = set(feedbacks_by_date.keys()) | set(reviews_by_date.keys())
        studied_dates = {
            d_str
            for d_str in all_dates
            if len(feedbacks_by_date.get(d_str, [])) >= 1
            or len(reviews_by_date.get(d_str, [])) >= 1
        }
        current_streak, longest_streak, total_study_days = calculate_streaks(
            studied_dates, today=base_today
        )

        def make_day_summary(target_date_str: str) -> dict[str, Any]:
            fb_list = feedbacks_by_date.get(target_date_str, [])
            rv_list = reviews_by_date.get(target_date_str, [])
            fb_count = len(fb_list)
            rv_count = len(rv_list)
            studied = fb_count >= 1 or rv_count >= 1
            goal_met = (
                fb_count >= goal.daily_feedback_goal
                and rv_count >= goal.daily_review_goal
            )
            fb_ratio = min(1.0, fb_count / max(1, goal.daily_feedback_goal))
            rv_ratio = min(1.0, rv_count / max(1, goal.daily_review_goal))
            progress_pct = int(round((fb_ratio * 0.5 + rv_ratio * 0.5) * 100))
            return {
                "date": target_date_str,
                "feedbackCount": fb_count,
                "reviewCount": rv_count,
                "studied": studied,
                "goalMet": goal_met,
                "progressPercent": progress_pct,
                "feedbacks": fb_list,
                "reviews": rv_list,
            }

        # 4) 최근 14일 달력 (과거 -> 오늘 순)
        recent_days: list[dict[str, Any]] = []
        for offset in range(RECENT_CALENDAR_DAYS - 1, -1, -1):
            d_str = (base_today - timedelta(days=offset)).isoformat()
            recent_days.append(make_day_summary(d_str))

        # 5) 학습 기록이 있는 날짜 전체 목록 (최신순)
        sorted_history_dates = sorted(
            (d for d in studied_dates if d <= today_str),
            reverse=True,
        )
        history_days = [make_day_summary(d_str) for d_str in sorted_history_dates]

        today_summary = make_day_summary(today_str)

        return {
            "today": today_str,
            "goal": goal.to_dict(),
            "currentStreak": current_streak,
            "longestStreak": longest_streak,
            "totalStudyDays": total_study_days,
            "todaySummary": today_summary,
            "recentDays": recent_days,
            "historyDays": history_days,
        }

    def _read_state_unlocked(self) -> tuple[DailyGoal, list[ReviewLogEntry]]:
        default_goal = DailyGoal()
        if not self.file_path.is_file():
            return default_goal, []
        try:
            raw_text = self.file_path.read_text(encoding="utf-8")
            if not raw_text.strip():
                return default_goal, []
            raw_obj = json.loads(raw_text)
        except (OSError, json.JSONDecodeError):
            return default_goal, []

        if not isinstance(raw_obj, dict):
            return default_goal, []

        raw_goal = raw_obj.get("goal")
        try:
            goal = DailyGoal.from_dict(raw_goal) if isinstance(raw_goal, dict) else default_goal
        except ValidationError:
            goal = default_goal

        raw_logs = raw_obj.get("reviewLogs")
        logs: list[ReviewLogEntry] = []
        if isinstance(raw_logs, list):
            for item in raw_logs:
                try:
                    logs.append(ReviewLogEntry.from_dict(item))
                except ValidationError:
                    continue

        return goal, logs

    def _write_state_unlocked(
        self,
        goal: DailyGoal,
        logs: list[ReviewLogEntry],
    ) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "goal": goal.to_dict(),
            "reviewLogs": [entry.to_dict() for entry in logs],
        }
        temp_path = self.file_path.with_name(
            f"{self.file_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_path.replace(self.file_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
