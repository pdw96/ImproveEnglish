"""조각 2(vocab-review): 단어장 항목·추가 요청·복습 평가 데이터 구조 및 간격 반복(SRS) 계산 모듈."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
import uuid

from src.feedback_types import ValidationError

MAX_EXPRESSION_LENGTH = 200
MAX_MEANING_LENGTH = 300
MAX_EXAMPLE_LENGTH = 500
VALID_RATINGS = ("again", "hard", "easy")
EASY_INTERVAL_BY_BOX = {
    1: 7,
    2: 14,
    3: 30,
}


def normalize_expression(expression: str) -> str:
    """중복 검사를 위해 앞뒤 공백을 제거하고 소문자로 정규화한다([V1] 보장)."""
    return expression.strip().lower()


def _resolve_today(today: date | None = None) -> date:
    """기준 날짜가 주어지지 않으면 내 PC의 오늘 날짜(YYYY-MM-DD)를 반환한다."""
    return today if today is not None else date.today()


@dataclass(frozen=True)
class VocabCreateRequest:
    """단어장 항목 추가 요청 데이터 구조([V1] 보장)."""

    expression: str
    meaning: str
    example: str = ""

    @classmethod
    def from_dict(cls, payload: Any) -> "VocabCreateRequest":
        """입력 JSON 딕셔너리를 검증하여 VocabCreateRequest로 변환한다."""
        if not isinstance(payload, dict):
            raise ValidationError("요청 본문은 JSON 객체여야 합니다.")

        raw_expr = payload.get("expression")
        if not isinstance(raw_expr, str):
            raise ValidationError("영어 표현(expression)을 글자로 입력해 주세요.")
        cleaned_expr = raw_expr.strip()
        if not cleaned_expr:
            raise ValidationError("단어장에 추가할 영어 표현을 입력해 주세요.")
        if len(cleaned_expr) > MAX_EXPRESSION_LENGTH:
            raise ValidationError(
                f"영어 표현은 최대 {MAX_EXPRESSION_LENGTH}자까지 입력할 수 있습니다(현재 {len(cleaned_expr)}자)."
            )

        raw_meaning = payload.get("meaning")
        if not isinstance(raw_meaning, str):
            raise ValidationError("한국어 뜻(meaning)을 글자로 입력해 주세요.")
        cleaned_meaning = raw_meaning.strip()
        if not cleaned_meaning:
            raise ValidationError("영어 표현의 한국어 뜻 또는 뉘앙스 설명을 입력해 주세요.")
        if len(cleaned_meaning) > MAX_MEANING_LENGTH:
            raise ValidationError(
                f"한국어 뜻은 최대 {MAX_MEANING_LENGTH}자까지 입력할 수 있습니다(현재 {len(cleaned_meaning)}자)."
            )

        raw_example = payload.get("example", "")
        if raw_example is None:
            raw_example = ""
        if not isinstance(raw_example, str):
            raise ValidationError("예문(example)은 글자로 입력해 주세요.")
        cleaned_example = raw_example.strip()
        if len(cleaned_example) > MAX_EXAMPLE_LENGTH:
            raise ValidationError(
                f"예문은 최대 {MAX_EXAMPLE_LENGTH}자까지 입력할 수 있습니다(현재 {len(cleaned_example)}자)."
            )

        return cls(
            expression=cleaned_expr,
            meaning=cleaned_meaning,
            example=cleaned_example,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "expression": self.expression,
            "meaning": self.meaning,
            "example": self.example,
        }


@dataclass(frozen=True)
class VocabReviewRequest:
    """단어장 복습 평가 요청 데이터 구조([V2] 보장)."""

    id: str
    rating: str

    @classmethod
    def from_dict(cls, payload: Any) -> "VocabReviewRequest":
        """입력 JSON 딕셔너리를 검증하여 VocabReviewRequest로 변환한다."""
        if not isinstance(payload, dict):
            raise ValidationError("요청 본문은 JSON 객체여야 합니다.")

        raw_id = payload.get("id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ValidationError("복습할 단어장 항목 ID(id)를 입력해 주세요.")

        raw_rating = payload.get("rating")
        if not isinstance(raw_rating, str) or raw_rating not in VALID_RATINGS:
            raise ValidationError(
                "복습 난이도(rating)는 'again', 'hard', 'easy' 중 하나여야 합니다."
            )

        return cls(id=raw_id.strip(), rating=raw_rating)

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "rating": self.rating,
        }


def calculate_next_review(
    current_box: int,
    rating: str,
    today: date | None = None,
) -> tuple[int, str]:
    """난이도 3단계(again / hard / easy)에 따라 다음 box 단계와 복습 예정일(YYYY-MM-DD)을 계산한다([V2] 보장).

    - again (몰랐음): box = 0, 1일 뒤 복습
    - hard (헷갈림): box = max(1, 현재 box), 3일 뒤 복습
    - easy (쉬웠음): box를 1단계 올려(최대 3) 1단계면 7일 뒤, 2단계면 14일 뒤, 3단계 이상이면 30일 뒤 복습
    """
    if rating not in VALID_RATINGS:
        raise ValidationError(
            "복습 난이도(rating)는 'again', 'hard', 'easy' 중 하나여야 합니다."
        )

    base_date = _resolve_today(today)
    safe_box = max(0, min(3, current_box))

    if rating == "again":
        next_box = 0
        days = 1
    elif rating == "hard":
        next_box = max(1, safe_box)
        days = 3
    else:  # rating == "easy"
        next_box = min(3, safe_box + 1)
        days = EASY_INTERVAL_BY_BOX[next_box]

    next_date_str = (base_date + timedelta(days=days)).isoformat()
    return next_box, next_date_str


@dataclass(frozen=True)
class VocabItem:
    """내 단어장에 저장되는 개별 단어·표현 항목 데이터 구조."""

    id: str
    expression: str
    meaning: str
    example: str
    box: int
    review_count: int
    next_review_date: str
    created_at: str
    last_reviewed_at: str | None = None

    @classmethod
    def create(
        cls,
        req: VocabCreateRequest,
        today: date | None = None,
    ) -> "VocabItem":
        """새 단어장 항목을 생성한다. 신규 등록 시 오늘 바로 복습 가능하도록 nextReviewDate를 오늘로 설정한다."""
        base_date = _resolve_today(today)
        now_iso = datetime.now(timezone.utc).isoformat()
        return cls(
            id=str(uuid.uuid4()),
            expression=req.expression,
            meaning=req.meaning,
            example=req.example,
            box=0,
            review_count=0,
            next_review_date=base_date.isoformat(),
            created_at=now_iso,
            last_reviewed_at=None,
        )

    def apply_review(
        self,
        rating: str,
        today: date | None = None,
    ) -> "VocabItem":
        """복습 평가 결과를 반영하여 다음 복습 예정일, box 단계, 복습 횟수가 갱신된 새 VocabItem을 반환한다."""
        next_box, next_date_str = calculate_next_review(
            current_box=self.box,
            rating=rating,
            today=today,
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        return VocabItem(
            id=self.id,
            expression=self.expression,
            meaning=self.meaning,
            example=self.example,
            box=next_box,
            review_count=self.review_count + 1,
            next_review_date=next_date_str,
            created_at=self.created_at,
            last_reviewed_at=now_iso,
        )

    def is_due(self, today: date | None = None) -> bool:
        """오늘 복습 대상(nextReviewDate <= 오늘)인지 판별한다."""
        base_date_str = _resolve_today(today).isoformat()
        return self.next_review_date <= base_date_str

    @classmethod
    def from_dict(cls, data: Any) -> "VocabItem":
        """저장된 JSON 딕셔너리를 검증하여 VocabItem으로 복원한다."""
        if not isinstance(data, dict):
            raise ValidationError("단어장 항목이 객체 형식이 아닙니다.")

        item_id = data.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValidationError("단어장 항목 ID가 올바르지 않습니다.")

        req = VocabCreateRequest.from_dict(
            {
                "expression": data.get("expression"),
                "meaning": data.get("meaning"),
                "example": data.get("example", ""),
            }
        )

        box = data.get("box", 0)
        if not isinstance(box, int) or isinstance(box, bool) or not (0 <= box <= 3):
            raise ValidationError("복습 단계(box)는 0~3 사이의 정수여야 합니다.")

        review_count = data.get("reviewCount", 0)
        if (
            not isinstance(review_count, int)
            or isinstance(review_count, bool)
            or review_count < 0
        ):
            raise ValidationError("복습 횟수(reviewCount)는 0 이상의 정수여야 합니다.")

        next_review_date = data.get("nextReviewDate")
        if not isinstance(next_review_date, str):
            raise ValidationError("다음 복습 예정일(nextReviewDate)이 올바르지 않습니다.")
        try:
            date.fromisoformat(next_review_date)
        except ValueError as exc:
            raise ValidationError(
                "다음 복습 예정일(nextReviewDate)은 YYYY-MM-DD 형식이어야 합니다."
            ) from exc

        created_at = data.get("createdAt")
        if not isinstance(created_at, str) or not created_at.strip():
            raise ValidationError("생성 시각(createdAt)이 올바르지 않습니다.")

        last_reviewed_at = data.get("lastReviewedAt")
        if last_reviewed_at is not None and (
            not isinstance(last_reviewed_at, str) or not last_reviewed_at.strip()
        ):
            last_reviewed_at = None

        return cls(
            id=item_id.strip(),
            expression=req.expression,
            meaning=req.meaning,
            example=req.example,
            box=box,
            review_count=review_count,
            next_review_date=next_review_date,
            created_at=created_at.strip(),
            last_reviewed_at=last_reviewed_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화용 딕셔너리로 변환한다."""
        return {
            "id": self.id,
            "expression": self.expression,
            "meaning": self.meaning,
            "example": self.example,
            "box": self.box,
            "reviewCount": self.review_count,
            "nextReviewDate": self.next_review_date,
            "createdAt": self.created_at,
            "lastReviewedAt": self.last_reviewed_at,
        }
