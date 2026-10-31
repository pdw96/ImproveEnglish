"""조각 8(review-quiz): AI 새 문제 — 퀴즈 전용 지시문 · 스키마로 Gemini 를 한 번 부르고 응답을 검증한다(설계 ③ · Q1 · Q9).

첨삭 앵커볼트(`src/gemini.py` 의 SYSTEM_INSTRUCTION · RESPONSE_SCHEMA · build_gemini_payload)는 건드리지 않는다.
키 읽기 · 모델 후보 · 전송만 빌려 쓴다. AI 새 문제 요청은 이 모듈의 `generate_ai_questions` 한 자리에서만 부른다(설계 ④).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import random
from typing import Any, Callable
import uuid

import src.gemini as gemini_module
from src.feedback_types import FeedbackRecord, ValidationError
from src.quiz_service import PoolEntry
from src.quiz_types import AI_MAX_COUNT, BLANK_MARK, CHOICE_COUNT, QuizQuestion, normalize_text

AI_POOL_LIMIT = 10
AI_RECENT_CORRECTED_LIMIT = 3
QUIZ_AI_TEMPERATURE = 0.7

AI_NOTICE_NO_KEY = "AI 키가 없거나 잠겨 있어 AI 새 문제 없이 내 기록으로만 냈습니다."
AI_NOTICE_FAILED = "AI 새 문제를 만들지 못해 내 기록으로만 냈습니다."
AI_NOTICE_PARTIAL = "AI 새 문제를 {n}개만 만들어 나머지는 내 기록으로 채웠습니다."

QUIZ_SYSTEM_INSTRUCTION = (
    "당신은 한국인 영어 학습자를 위한 퀴즈 출제자입니다. "
    "사용자가 이미 배운 영어 표현 목록과 최근 교정받은 문장을 받습니다. "
    "반드시 지정된 JSON 스키마에 맞춰 4지선다 빈칸 문제 3개를 만드세요.\n"
    "1. 각 문제는 목록의 서로 다른 표현 하나를 대상으로 합니다. 사용자가 본 적 없는 새 영어 문장 하나를 쓰고, "
    "대상 표현이 들어갈 자리를 ____ (밑줄 4개)로 비워 question 에 넣습니다.\n"
    "2. 문장 수준(단어 난이도 · 길이)은 사용자의 교정 문장과 비슷하게 맞추고, 20단어를 넘기지 않습니다.\n"
    "3. choices 는 영어 표현 4개입니다. 정답은 대상 표현 그대로 쓰고, 오답 3개는 비슷한 길이 · 같은 품사로 "
    "그럴듯하지만 그 문장에는 맞지 않는 표현입니다. 네 보기는 서로 달라야 합니다.\n"
    "4. answerIndex 는 정답 보기의 번호(0~3)입니다.\n"
    "5. explanation 은 왜 정답인지, 오답이 왜 어색한지 한국어로 2문장 이내로 씁니다.\n"
    "6. expression 은 대상 표현, meaning 은 그 한국어 뜻, example 은 빈칸을 정답으로 채운 완성 문장입니다."
)

QUIZ_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "required": ["questions"],
    "properties": {
        "questions": {
            "type": "ARRAY",
            "maxItems": AI_MAX_COUNT,
            "items": {
                "type": "OBJECT",
                "required": [
                    "question",
                    "choices",
                    "answerIndex",
                    "explanation",
                    "expression",
                    "meaning",
                    "example",
                ],
                "properties": {
                    "question": {"type": "STRING", "description": "대상 표현 자리를 ____ 로 비운 새 영어 문장"},
                    "choices": {
                        "type": "ARRAY",
                        "minItems": CHOICE_COUNT,
                        "maxItems": CHOICE_COUNT,
                        "items": {"type": "STRING"},
                        "description": "영어 표현 보기 4개(정답 1 · 오답 3)",
                    },
                    "answerIndex": {"type": "INTEGER", "description": "정답 보기 번호(0~3)"},
                    "explanation": {"type": "STRING", "description": "정답 · 오답 이유를 설명하는 한국어 해설"},
                    "expression": {"type": "STRING", "description": "대상 영어 표현"},
                    "meaning": {"type": "STRING", "description": "대상 표현의 한국어 뜻"},
                    "example": {"type": "STRING", "description": "빈칸을 정답으로 채운 완성 문장"},
                },
            },
        }
    },
}


@dataclass(frozen=True)
class AiQuestionsResult:
    """AI 새 문제 결과 — 검증을 지난 문제(최대 3개)와 상태(ok · no_key · failed)."""

    questions: list[QuizQuestion]
    status: str

    def notice(self) -> str | None:
        """세트를 새로 만들 때 화면에 보일 안내(Q9). 3개를 다 받았으면 None."""
        count = len(self.questions)
        if count >= AI_MAX_COUNT:
            return None
        if count == 0:
            return AI_NOTICE_NO_KEY if self.status == "no_key" else AI_NOTICE_FAILED
        return AI_NOTICE_PARTIAL.format(n=count)


def build_quiz_ai_payload(pool: list[PoolEntry], records: list[FeedbackRecord]) -> dict[str, Any]:
    """배운 표현(최대 10개)과 최근 교정 문장(최대 3개)으로 퀴즈 전용 요청 본문을 만든다."""
    lines = ["[배운 표현]"]
    lines += [f"- {e.expression} — {e.meaning}" for e in pool[:AI_POOL_LIMIT]]
    corrected = [r.feedback.corrected.strip() for r in records if r.feedback.corrected.strip()]
    lines.append("[최근 교정 문장]")
    lines += [f"- {c}" for c in corrected[:AI_RECENT_CORRECTED_LIMIT]] or ["- (없음)"]
    return {
        "systemInstruction": {"parts": [{"text": QUIZ_SYSTEM_INSTRUCTION}]},
        "contents": [{"role": "user", "parts": [{"text": "\n".join(lines)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": QUIZ_RESPONSE_SCHEMA,
            "temperature": QUIZ_AI_TEMPERATURE,
        },
    }


def parse_ai_questions(raw_response: Any, rng: random.Random | None = None) -> list[QuizQuestion]:
    """Gemini 응답에서 문제를 꺼내 ③ 의 모양으로 검증한다. 틀린 문제는 그 문제만 버리고, 앞의 3개만 쓴다."""
    generator = rng or random.Random()
    try:
        text = raw_response["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return []
    items = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []

    questions: list[QuizQuestion] = []
    seen_targets: set[str] = set()
    for item in items:
        if len(questions) >= AI_MAX_COUNT:
            break
        if not isinstance(item, dict):
            continue
        try:
            checked = QuizQuestion.from_dict(
                {
                    "id": f"qa-{uuid.uuid4().hex[:12]}",
                    "kind": "ai",
                    "source": "ai",
                    "question": item.get("question"),
                    "choices": item.get("choices"),
                    "answerIndex": item.get("answerIndex"),
                    "explanation": item.get("explanation"),
                    "expression": item.get("expression"),
                    "meaning": item.get("meaning"),
                    "example": item.get("example"),
                }
            )
        except ValidationError:
            continue
        target = normalize_text(checked.expression)
        if BLANK_MARK not in checked.question:
            continue
        if normalize_text(checked.choices[checked.answer_index]) != target:
            continue
        if target in seen_targets:
            continue
        seen_targets.add(target)
        correct = checked.choices[checked.answer_index]
        choices = list(checked.choices)
        generator.shuffle(choices)
        questions.append(
            QuizQuestion(
                id=checked.id,
                kind="ai",
                source="ai",
                question=checked.question,
                choices=tuple(choices),
                answer_index=choices.index(correct),
                explanation=checked.explanation,
                expression=checked.expression,
                meaning=checked.meaning,
                example=checked.example,
            )
        )
    return questions


def generate_ai_questions(
    pool: list[PoolEntry],
    records: list[FeedbackRecord],
    transport: Callable[[str, dict[str, str], bytes], dict[str, Any]] | None = None,
    rng: random.Random | None = None,
) -> AiQuestionsResult:
    """AI 새 문제 요청 — 키는 헤더(x-goog-api-key)로만 보내고, 실패하면 빈 목록과 상태를 돌려준다(Q9)."""
    if len(pool) < CHOICE_COUNT:
        return AiQuestionsResult([], "failed")
    try:
        api_key = gemini_module.get_api_key()
    except gemini_module.GeminiServiceError:
        return AiQuestionsResult([], "no_key")
    body = json.dumps(build_quiz_ai_payload(pool, records), ensure_ascii=False).encode("utf-8")
    try:
        if transport is not None:
            headers = {"Content-Type": "application/json; charset=utf-8", "x-goog-api-key": api_key}
            raw = transport(gemini_module.GEMINI_ENDPOINT, headers, body)
        else:
            raw = gemini_module._send_with_auto_auth(api_key, body)
    except Exception:  # 연결 · 한도 · 응답 오류 — 퀴즈는 내 기록으로 이어간다
        return AiQuestionsResult([], "failed")
    questions = parse_ai_questions(raw, rng=rng)
    return AiQuestionsResult(questions, "ok" if questions else "failed")
