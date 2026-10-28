"""조각 4(daily-mission): 날짜·카테고리 기반 상황 미션 선정 및 내 단어장 추천 표현·오늘 미션 완료 상태 연동 서비스."""

from __future__ import annotations

from datetime import date
from typing import Any

from src.feedback_types import FeedbackRecord
from src.mission_types import (
    CATEGORY_LABELS,
    MISSION_BY_ID,
    MISSION_POOL,
    VALID_MISSION_CATEGORIES,
    MissionPrompt,
    VocabSuggestion,
    validate_mission_query,
)
from src.routine_types import iso_to_local_date_str
from src.vocab_types import VocabItem

MAX_VOCAB_SUGGESTIONS = 2


def select_mission_prompt(
    category: str = "all",
    mission_id: str | None = None,
    exclude_id: str | None = None,
    today: date | None = None,
) -> MissionPrompt:
    """날짜·카테고리·선택/제외 ID에 따라 상황별 미션 1개를 선정한다([M1], [M2] 보장)."""
    cleaned_cat, cleaned_mid, cleaned_ex = validate_mission_query(
        category=category,
        mission_id=mission_id,
        exclude_id=exclude_id,
    )
    base_today = today if today is not None else date.today()

    if cleaned_mid is not None:
        return MISSION_BY_ID[cleaned_mid]

    candidates = [
        m
        for m in MISSION_POOL
        if cleaned_cat == "all" or m.category == cleaned_cat
    ]
    if not candidates:
        candidates = list(MISSION_POOL)

    if cleaned_ex is not None and len(candidates) > 1:
        # 현재 보고 있는 미션(excludeId) 다음 순서의 미션을 반환하여 [다른 미션 보기] 클릭 시 즉시 순환되도록 함
        for idx, item in enumerate(candidates):
            if item.id == cleaned_ex:
                return candidates[(idx + 1) % len(candidates)]
        filtered = [m for m in candidates if m.id != cleaned_ex]
        if filtered:
            candidates = filtered

    day_index = base_today.toordinal() % len(candidates)
    return candidates[day_index]


def pick_vocab_suggestions(
    vocab_items: list[VocabItem],
    today: date | None = None,
    limit: int = MAX_VOCAB_SUGGESTIONS,
) -> list[VocabSuggestion]:
    """내 단어장에서 오늘 복습 대상(isDue=True) 표현을 우선으로, 부족하면 최근 표현에서 최대 limit개를 뽑는다([M3] 보장)."""
    base_today = today if today is not None else date.today()
    due_list: list[VocabSuggestion] = []
    other_list: list[VocabSuggestion] = []

    for item in vocab_items:
        is_due = item.is_due(today=base_today)
        suggestion = VocabSuggestion(
            id=item.id,
            expression=item.expression,
            meaning=item.meaning,
            example=item.example,
            is_due=is_due,
        )
        if is_due:
            due_list.append(suggestion)
        else:
            other_list.append(suggestion)

    combined = [*due_list, *other_list]
    return combined[: max(0, limit)]


def build_daily_mission_status(
    feedback_records: list[FeedbackRecord],
    vocab_items: list[VocabItem],
    category: str | None = None,
    mission_id: str | None = None,
    exclude_id: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """오늘의 상황별 미션, 내 단어장 추천 표현(최대 2개), 오늘 미션 완료 여부를 종합해 반환한다([M1]~[M3] 보장)."""
    base_today = today if today is not None else date.today()
    today_str = base_today.isoformat()

    cleaned_cat, cleaned_mid, cleaned_ex = validate_mission_query(
        category=category,
        mission_id=mission_id,
        exclude_id=exclude_id,
    )
    mission = select_mission_prompt(
        category=cleaned_cat,
        mission_id=cleaned_mid,
        exclude_id=cleaned_ex,
        today=base_today,
    )
    vocab_suggestions = pick_vocab_suggestions(
        vocab_items=vocab_items,
        today=base_today,
        limit=MAX_VOCAB_SUGGESTIONS,
    )

    today_feedback_count = sum(
        1
        for rec in feedback_records
        if iso_to_local_date_str(rec.created_at, fallback_today=base_today)
        == today_str
    )
    completed_today = today_feedback_count >= 1

    categories = [
        {"id": cat_id, "label": CATEGORY_LABELS[cat_id]}
        for cat_id in VALID_MISSION_CATEGORIES
    ]

    return {
        "today": today_str,
        "selectedCategory": cleaned_cat,
        "categories": categories,
        "mission": mission.to_dict(),
        "vocabSuggestions": [s.to_dict() for s in vocab_suggestions],
        "completedToday": completed_today,
        "todayFeedbackCount": today_feedback_count,
    }
