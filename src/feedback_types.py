"""앵커볼트: AI 첨삭 요청·응답·기록 데이터 구조 및 입력/출력 검증 모듈."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import uuid

MAX_TEXT_LENGTH = 1000
VALID_INPUT_MODES = ("text", "voice")


class ValidationError(ValueError):
    """요청 또는 응답 데이터가 규약을 어겼을 때 발생하는 예외."""


@dataclass(frozen=True)
class FeedbackRequest:
    """사용자가 보낸 첨삭 요청 데이터 구조."""

    text: str
    input_mode: str = "text"

    @classmethod
    def from_dict(cls, payload: Any) -> "FeedbackRequest":
        """입력 JSON 딕셔너리를 검증하여 FeedbackRequest로 변환한다([G1] 보장)."""
        if not isinstance(payload, dict):
            raise ValidationError("요청 본문은 JSON 객체여야 합니다.")

        raw_text = payload.get("text")
        if not isinstance(raw_text, str):
            raise ValidationError("문장(text)을 글자로 입력해 주세요.")

        cleaned_text = raw_text.strip()
        if not cleaned_text:
            raise ValidationError("첨삭받을 영어 문장을 입력해 주세요.")

        if len(cleaned_text) > MAX_TEXT_LENGTH:
            raise ValidationError(
                f"문장은 최대 {MAX_TEXT_LENGTH}자까지 입력할 수 있습니다(현재 {len(cleaned_text)}자)."
            )

        raw_mode = payload.get("inputMode", "text")
        if raw_mode is None:
            raw_mode = "text"
        if not isinstance(raw_mode, str) or raw_mode not in VALID_INPUT_MODES:
            raise ValidationError("입력 방식(inputMode)은 'text' 또는 'voice'만 허용됩니다.")

        return cls(text=cleaned_text, input_mode=raw_mode)

    def to_dict(self) -> dict[str, Any]:
        """직렬화 가능한 딕셔너리로 변환한다."""
        return {
            "text": self.text,
            "inputMode": self.input_mode,
        }


@dataclass(frozen=True)
class AlternativeExpression:
    """원어민이 자주 쓰는 자연스러운 추천 표현 항목."""

    expression: str
    nuance: str

    @classmethod
    def from_dict(cls, data: Any) -> "AlternativeExpression":
        if not isinstance(data, dict):
            raise ValidationError("추천 표현 항목이 객체 형식이 아닙니다.")
        expression = data.get("expression")
        nuance = data.get("nuance")
        if not isinstance(expression, str) or not expression.strip():
            raise ValidationError("추천 표현(expression)이 비어 있습니다.")
        if not isinstance(nuance, str) or not nuance.strip():
            raise ValidationError("추천 표현의 뉘앙스 설명(nuance)이 비어 있습니다.")
        return cls(expression=expression.strip(), nuance=nuance.strip())

    def to_dict(self) -> dict[str, str]:
        return {
            "expression": self.expression,
            "nuance": self.nuance,
        }


@dataclass(frozen=True)
class KeyExpression:
    """외워두면 좋은 핵심 단어·표현 요약 항목."""

    expression: str
    meaning: str
    example: str

    @classmethod
    def from_dict(cls, data: Any) -> "KeyExpression":
        if not isinstance(data, dict):
            raise ValidationError("핵심 표현 항목이 객체 형식이 아닙니다.")
        expression = data.get("expression")
        meaning = data.get("meaning")
        example = data.get("example")
        if not isinstance(expression, str) or not expression.strip():
            raise ValidationError("핵심 표현(expression)이 비어 있습니다.")
        if not isinstance(meaning, str) or not meaning.strip():
            raise ValidationError("핵심 표현 뜻(meaning)이 비어 있습니다.")
        if not isinstance(example, str) or not example.strip():
            raise ValidationError("핵심 표현 예문(example)이 비어 있습니다.")
        return cls(
            expression=expression.strip(),
            meaning=meaning.strip(),
            example=example.strip(),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "expression": self.expression,
            "meaning": self.meaning,
            "example": self.example,
        }


@dataclass(frozen=True)
class FeedbackResponse:
    """AI 첨삭 3단 결과 데이터 구조([G2] 보장)."""

    corrected: str
    explanation: str
    alternatives: list[AlternativeExpression]
    key_expressions: list[KeyExpression]

    @classmethod
    def from_dict(cls, data: Any) -> "FeedbackResponse":
        """AI가 반환한 딕셔너리가 3단 첨삭 규약을 만족하는지 검증한다."""
        if not isinstance(data, dict):
            raise ValidationError("AI 첨삭 응답이 객체 형식이 아닙니다.")

        corrected = data.get("corrected")
        explanation = data.get("explanation")
        raw_alternatives = data.get("alternatives")
        raw_keys = data.get("keyExpressions")

        if not isinstance(corrected, str) or not corrected.strip():
            raise ValidationError("교정된 문장(corrected)이 비어 있습니다.")
        if not isinstance(explanation, str) or not explanation.strip():
            raise ValidationError("교정 이유 설명(explanation)이 비어 있습니다.")
        if not isinstance(raw_alternatives, list) or not (2 <= len(raw_alternatives) <= 3):
            raise ValidationError("자연스러운 추천 표현(alternatives)은 2~3개여야 합니다.")
        if not isinstance(raw_keys, list) or len(raw_keys) < 1:
            raise ValidationError("핵심 단어·표현 요약(keyExpressions)은 최소 1개 이상이어야 합니다.")

        alternatives = [AlternativeExpression.from_dict(item) for item in raw_alternatives]
        key_expressions = [KeyExpression.from_dict(item) for item in raw_keys]

        return cls(
            corrected=corrected.strip(),
            explanation=explanation.strip(),
            alternatives=alternatives,
            key_expressions=key_expressions,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "corrected": self.corrected,
            "explanation": self.explanation,
            "alternatives": [item.to_dict() for item in self.alternatives],
            "keyExpressions": [item.to_dict() for item in self.key_expressions],
        }


@dataclass(frozen=True)
class FeedbackRecord:
    """내 PC에 자동 보관되는 첨삭 학습 기록 항목([G3] 보장)."""

    id: str
    created_at: str
    text: str
    input_mode: str
    feedback: FeedbackResponse

    @classmethod
    def create(cls, req: FeedbackRequest, feedback: FeedbackResponse) -> "FeedbackRecord":
        """요청과 첨삭 결과로부터 새 학습 기록을 생성한다."""
        now_iso = datetime.now(timezone.utc).isoformat()
        return cls(
            id=str(uuid.uuid4()),
            created_at=now_iso,
            text=req.text,
            input_mode=req.input_mode,
            feedback=feedback,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "FeedbackRecord":
        if not isinstance(data, dict):
            raise ValidationError("기록 항목이 객체 형식이 아닙니다.")
        record_id = data.get("id")
        created_at = data.get("createdAt")
        text = data.get("text")
        input_mode = data.get("inputMode", "text")
        feedback_data = data.get("feedback")

        if not isinstance(record_id, str) or not record_id.strip():
            raise ValidationError("기록 ID가 올바르지 않습니다.")
        if not isinstance(created_at, str) or not created_at.strip():
            raise ValidationError("기록 생성 시각(createdAt)이 올바르지 않습니다.")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("기록 원문(text)이 올바르지 않습니다.")
        if input_mode not in VALID_INPUT_MODES:
            input_mode = "text"

        return cls(
            id=record_id,
            created_at=created_at,
            text=text,
            input_mode=input_mode,
            feedback=FeedbackResponse.from_dict(feedback_data),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "createdAt": self.created_at,
            "text": self.text,
            "inputMode": self.input_mode,
            "feedback": self.feedback.to_dict(),
        }
