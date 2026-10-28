"""조각 3(study-routine): 일일 학습 목표·날짜별 학습 활동·연속 학습일(스트릭) 데이터 구조 및 계산 모듈."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from src.feedback_types import ValidationError
from src.vocab_types import VALID_RATINGS

MIN_FEEDBACK_GOAL = 1
MAX_FEEDBACK_GOAL = 20
MIN_REVIEW_GOAL = 1
MAX_REVIEW_GOAL = 50
DEFAULT_FEEDBACK_GOAL = 1
DEFAULT_REVIEW_GOAL = 3
RECENT_CALENDAR_DAYS = 14


def _resolve_today(today: date | None = None) -> date:
    """기준 날짜가 주어지지 않으면 내 PC의 오늘 날짜(YYYY-MM-DD)를 반환한다."""
    return today if today is not None else date.today()


def iso_to_local_date_str(iso_str: str, fallback_today: date | None = None) -> str:
    """ISO-8601 시각 문자열에서 날짜(YYYY-MM-DD)를 추출한다."""
    if not isinstance(iso_str, str) or not iso_str.strip():
        return _resolve_today(fallback_today).isoformat()
    cleaned = iso_str.strip()
    # 이미 YYYY-MM-DD 형태인 경우
    if len(cleaned) >= 10:
        candidate = cleaned[:10]
        try:
            date.fromisoformat(candidate)
            return candidate
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except ValueError:
        return _resolve_today(fallback_today).isoformat()


@dataclass(frozen=True)
class DailyGoal:
    """사용자가 설정한 하루 영어 학습 목표치([R1] 보장)."""

    daily_feedback_goal: int = DEFAULT_FEEDBACK_GOAL
    daily_review_goal: int = DEFAULT_REVIEW_GOAL

    @classmethod
    def from_dict(cls, payload: Any) -> "DailyGoal":
        """입력 JSON 딕셔너리를 검증하여 DailyGoal로 변환한다([R1] 보장)."""
        if not isinstance(payload, dict):
            raise ValidationError("요청 본문은 JSON 객체여야 합니다.")

        fb_goal = payload.get("dailyFeedbackGoal")
        rev_goal = payload.get("dailyReviewGoal")

        if (
            not isinstance(fb_goal, int)
            or isinstance(fb_goal, bool)
            or not (MIN_FEEDBACK_GOAL <= fb_goal <= MAX_FEEDBACK_GOAL)
        ):
            raise ValidationError(
                f"일일 첨삭 목표(dailyFeedbackGoal)는 {MIN_FEEDBACK_GOAL}~{MAX_FEEDBACK_GOAL} 사이의 정수여야 합니다."
            )

        if (
            not isinstance(rev_goal, int)
            or isinstance(rev_goal, bool)
            or not (MIN_REVIEW_GOAL <= rev_goal <= MAX_REVIEW_GOAL)
        ):
            raise ValidationError(
                f"일일 복습 목표(dailyReviewGoal)는 {MIN_REVIEW_GOAL}~{MAX_REVIEW_GOAL} 사이의 정수여야 합니다."
            )

        return cls(
            daily_feedback_goal=fb_goal,
            daily_review_goal=rev_goal,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "dailyFeedbackGoal": self.daily_feedback_goal,
            "dailyReviewGoal": self.daily_review_goal,
        }


@dataclass(frozen=True)
class ReviewLogEntry:
    """일자별 단어장 복습 활동 기록 항목."""

    date: str
    vocab_id: str
    expression: str
    meaning: str
    rating: str
    reviewed_at: str

    @classmethod
    def from_dict(cls, data: Any) -> "ReviewLogEntry":
        if not isinstance(data, dict):
            raise ValidationError("복습 기록 항목이 객체 형식이 아닙니다.")

        raw_date = data.get("date")
        if not isinstance(raw_date, str):
            raise ValidationError("복습 날짜(date)가 올바르지 않습니다.")
        try:
            date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValidationError("복습 날짜(date)는 YYYY-MM-DD 형식이어야 합니다.") from exc

        vocab_id = data.get("vocabId")
        expression = data.get("expression")
        meaning = data.get("meaning")
        rating = data.get("rating")
        reviewed_at = data.get("reviewedAt")

        if not isinstance(vocab_id, str) or not vocab_id.strip():
            raise ValidationError("단어 ID(vocabId)가 비어 있습니다.")
        if not isinstance(expression, str) or not expression.strip():
            raise ValidationError("영어 표현(expression)이 비어 있습니다.")
        if not isinstance(meaning, str) or not meaning.strip():
            raise ValidationError("한국어 뜻(meaning)이 비어 있습니다.")
        if not isinstance(rating, str) or rating not in VALID_RATINGS:
            raise ValidationError("복습 난이도(rating)가 올바르지 않습니다.")
        if not isinstance(reviewed_at, str) or not reviewed_at.strip():
            raise ValidationError("복습 시각(reviewedAt)이 비어 있습니다.")

        return cls(
            date=raw_date,
            vocab_id=vocab_id.strip(),
            expression=expression.strip(),
            meaning=meaning.strip(),
            rating=rating,
            reviewed_at=reviewed_at.strip(),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "date": self.date,
            "vocabId": self.vocab_id,
            "expression": self.expression,
            "meaning": self.meaning,
            "rating": self.rating,
            "reviewedAt": self.reviewed_at,
        }


def calculate_streaks(
    studied_dates: set[str],
    today: date | None = None,
) -> tuple[int, int, int]:
    """학습 완료 날짜 집합(YYYY-MM-DD)으로부터 (현재 연속일, 최장 연속일, 총 학습일 수)를 계산한다([R2] 보장).

    - 오늘 이미 학습했으면 오늘부터 과거로 이어진 연속 일수를 센다.
    - 오늘 아직 학습하지 않았더라도 어제 학습했으면 어제까지 이어진 연속 일수를 유지한다.
    - 어제도 학습하지 않았으면 현재 연속일은 0이다.
    """
    base_today = _resolve_today(today)
    valid_dates: set[date] = set()
    for d_str in studied_dates:
        if not isinstance(d_str, str):
            continue
        try:
            parsed = date.fromisoformat(d_str)
        except ValueError:
            continue
        if parsed <= base_today:
            valid_dates.add(parsed)

    if not valid_dates:
        return 0, 0, 0

    sorted_dates = sorted(valid_dates)
    total_days = len(sorted_dates)

    # 최장 연속 학습일 계산
    longest = 1
    current_run = 1
    for idx in range(1, len(sorted_dates)):
        if sorted_dates[idx] - sorted_dates[idx - 1] == timedelta(days=1):
            current_run += 1
            if current_run > longest:
                longest = current_run
        else:
            current_run = 1

    # 현재 연속 학습일 계산
    yesterday = base_today - timedelta(days=1)
    if base_today in valid_dates:
        cursor = base_today
    elif yesterday in valid_dates:
        cursor = yesterday
    else:
        return 0, longest, total_days

    current_streak = 0
    while cursor in valid_dates:
        current_streak += 1
        cursor -= timedelta(days=1)

    return current_streak, longest, total_days
