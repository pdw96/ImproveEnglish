"""조각 8(review-quiz): 오늘의 퀴즈 문제 · 세트 · 답안 · 날짜별 점수 데이터 구조와 채점."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
import uuid

from src.feedback_types import ValidationError

QUIZ_SIZE = 10
MINE_DEFAULT_COUNT = 7
AI_MAX_COUNT = 3
MIN_QUIZ_SIZE = 5
CHOICE_COUNT = 4
BLANK_MARK = "____"

VALID_KINDS = ("meaning", "expression", "blank", "ai")
VALID_SOURCES = ("mine", "ai")

MAX_QUESTION_LENGTH = 300
MAX_CHOICE_LENGTH = 200
MAX_EXPLANATION_LENGTH = 500
MAX_EXPRESSION_LENGTH = 200
MAX_MEANING_LENGTH = 300
MAX_EXAMPLE_LENGTH = 500

NOT_ENOUGH_MESSAGE = "단어장 · 첨삭 기록에 표현이 5개 이상 쌓이면 퀴즈가 열립니다."
DATE_CHANGED_MESSAGE = "날짜가 바뀌어 새 퀴즈가 열렸습니다. 이 답안은 점수에 남지 않습니다."
QUIZ_CHANGED_MESSAGE = "풀던 퀴즈가 바뀌어 이 답안은 점수에 남지 않습니다. 퀴즈를 다시 시작해 주세요."
MAX_QUIZ_ID_LENGTH = 100
SAVE_FAILED_MESSAGE = "퀴즈 기록을 저장하지 못했습니다. 저장 공간을 확인한 뒤 다시 시도해 주세요."


def normalize_text(value: str) -> str:
    """보기 · 대상 표현이 같은지 가르려고 앞뒤 공백을 지우고 소문자로 맞춘다."""
    return " ".join(value.split()).lower()


def _require_text(data: dict[str, Any], key: str, max_len: int, min_len: int = 1) -> str:
    raw = data.get(key, "" if min_len == 0 else None)
    if not isinstance(raw, str):
        raise ValidationError(f"퀴즈 문제의 {key} 칸이 글자가 아닙니다.")
    cleaned = raw.strip()
    if len(cleaned) < min_len or len(cleaned) > max_len:
        raise ValidationError(f"퀴즈 문제의 {key} 칸 길이가 {min_len} ~ {max_len}자가 아닙니다.")
    return cleaned


def _require_date(raw: Any, label: str) -> str:
    if not isinstance(raw, str):
        raise ValidationError(f"{label}은 YYYY-MM-DD 형식이어야 합니다.")
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError(f"{label}은 YYYY-MM-DD 형식이어야 합니다.") from exc
    if parsed.isoformat() != raw:
        raise ValidationError(f"{label}은 YYYY-MM-DD 형식이어야 합니다.")
    return raw


def _require_quiz_id(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip() or len(raw.strip()) > MAX_QUIZ_ID_LENGTH:
        raise ValidationError("퀴즈 세트 id(quizId)가 올바르지 않습니다.")
    return raw.strip()


def _is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class QuizQuestion:
    """4지선다 문제 하나([Q3] 보장 — 보기 4개 · 서로 다름 · 정답 하나)."""

    id: str
    kind: str
    source: str
    question: str
    choices: tuple[str, ...]
    answer_index: int
    explanation: str
    expression: str
    meaning: str
    example: str = ""

    @classmethod
    def from_dict(cls, data: Any) -> "QuizQuestion":
        if not isinstance(data, dict):
            raise ValidationError("퀴즈 문제가 객체 형식이 아닙니다.")
        qid = data.get("id")
        if not isinstance(qid, str) or not qid.strip():
            raise ValidationError("퀴즈 문제 ID가 올바르지 않습니다.")
        kind = data.get("kind")
        if kind not in VALID_KINDS:
            raise ValidationError("퀴즈 문제 종류(kind)가 올바르지 않습니다.")
        source = data.get("source")
        if source not in VALID_SOURCES:
            raise ValidationError("퀴즈 문제 출처(source)가 올바르지 않습니다.")
        if (kind == "ai") != (source == "ai"):
            raise ValidationError("퀴즈 문제 종류와 출처가 맞지 않습니다.")

        question = _require_text(data, "question", MAX_QUESTION_LENGTH)
        raw_choices = data.get("choices")
        if not isinstance(raw_choices, list) or len(raw_choices) != CHOICE_COUNT:
            raise ValidationError("퀴즈 보기는 정확히 4개여야 합니다.")
        choices: list[str] = []
        seen: set[str] = set()
        for raw in raw_choices:
            if not isinstance(raw, str):
                raise ValidationError("퀴즈 보기가 글자가 아닙니다.")
            cleaned = raw.strip()
            if not cleaned or len(cleaned) > MAX_CHOICE_LENGTH:
                raise ValidationError(f"퀴즈 보기 길이가 1 ~ {MAX_CHOICE_LENGTH}자가 아닙니다.")
            key = normalize_text(cleaned)
            if key in seen:
                raise ValidationError("퀴즈 보기가 서로 겹칩니다.")
            seen.add(key)
            choices.append(cleaned)

        answer_index = data.get("answerIndex")
        if not _is_plain_int(answer_index) or not (0 <= answer_index < CHOICE_COUNT):
            raise ValidationError("정답 번호(answerIndex)는 0 ~ 3 의 정수여야 합니다.")

        return cls(
            id=qid.strip(),
            kind=kind,
            source=source,
            question=question,
            choices=tuple(choices),
            answer_index=answer_index,
            explanation=_require_text(data, "explanation", MAX_EXPLANATION_LENGTH),
            expression=_require_text(data, "expression", MAX_EXPRESSION_LENGTH),
            meaning=_require_text(data, "meaning", MAX_MEANING_LENGTH),
            example=_require_text(data, "example", MAX_EXAMPLE_LENGTH, min_len=0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": self.source,
            "question": self.question,
            "choices": list(self.choices),
            "answerIndex": self.answer_index,
            "explanation": self.explanation,
            "expression": self.expression,
            "meaning": self.meaning,
            "example": self.example,
        }


@dataclass(frozen=True)
class DailyQuiz:
    """오늘의 퀴즈 세트 — 저장되는 세트는 늘 하나다([Q4] 보장). id 는 답안이 화면에 보인 그 세트에만 채점되게 가르는 이름표다."""

    id: str
    date: str
    created_at: str
    questions: tuple[QuizQuestion, ...]

    @classmethod
    def create(cls, quiz_date: date, questions: list[QuizQuestion]) -> "DailyQuiz":
        return cls(
            id=f"quiz-{uuid.uuid4().hex}",
            date=quiz_date.isoformat(),
            created_at=datetime.now(timezone.utc).isoformat(),
            questions=tuple(questions),
        )

    @classmethod
    def from_dict(cls, data: Any) -> "DailyQuiz":
        if not isinstance(data, dict):
            raise ValidationError("퀴즈 세트가 객체 형식이 아닙니다.")
        quiz_id = _require_quiz_id(data.get("id"))
        quiz_date = _require_date(data.get("date"), "퀴즈 날짜(date)")
        created_at = data.get("createdAt")
        if not isinstance(created_at, str) or not created_at.strip():
            raise ValidationError("퀴즈 생성 시각(createdAt)이 올바르지 않습니다.")
        raw_questions = data.get("questions")
        if not isinstance(raw_questions, list) or not (
            MIN_QUIZ_SIZE <= len(raw_questions) <= QUIZ_SIZE
        ):
            raise ValidationError("퀴즈 세트의 문제 수는 5 ~ 10 이어야 합니다.")
        questions = tuple(QuizQuestion.from_dict(q) for q in raw_questions)
        return cls(id=quiz_id, date=quiz_date, created_at=created_at.strip(), questions=questions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date,
            "createdAt": self.created_at,
            "questions": [q.to_dict() for q in self.questions],
        }


@dataclass(frozen=True)
class QuizAttemptRequest:
    """답안 — 세트 날짜 · 세트 id 와 문제마다 고른 번호(0 ~ 3)의 목록([Q5] 보장)."""

    date: str
    quiz_id: str
    answers: tuple[int, ...]

    @classmethod
    def from_dict(cls, payload: Any) -> "QuizAttemptRequest":
        if not isinstance(payload, dict):
            raise ValidationError("요청 본문은 JSON 객체여야 합니다.")
        quiz_date = _require_date(payload.get("date"), "퀴즈 날짜(date)")
        quiz_id = _require_quiz_id(payload.get("quizId"))
        raw_answers = payload.get("answers")
        if not isinstance(raw_answers, list) or not raw_answers:
            raise ValidationError("답안(answers)은 고른 번호의 목록이어야 합니다.")
        if len(raw_answers) > QUIZ_SIZE:
            raise ValidationError("답안 개수가 문제 수와 맞지 않습니다.")
        for value in raw_answers:
            if not _is_plain_int(value) or not (0 <= value < CHOICE_COUNT):
                raise ValidationError("고른 번호는 0 ~ 3 의 정수여야 합니다.")
        return cls(date=quiz_date, quiz_id=quiz_id, answers=tuple(raw_answers))


@dataclass(frozen=True)
class QuizScore:
    """날짜별 점수 줄 — 첫 점수는 다시 풀어도 바뀌지 않는다([Q6] 보장)."""

    date: str
    first_score: int
    best_score: int
    attempt_count: int
    total: int

    @classmethod
    def from_dict(cls, data: Any) -> "QuizScore":
        if not isinstance(data, dict):
            raise ValidationError("퀴즈 점수 줄이 객체 형식이 아닙니다.")
        score_date = _require_date(data.get("date"), "점수 날짜(date)")
        first = data.get("firstScore")
        best = data.get("bestScore")
        count = data.get("attemptCount")
        total = data.get("total")
        for value in (first, best):
            if not _is_plain_int(value) or not (0 <= value <= 100):
                raise ValidationError("점수는 0 ~ 100 의 정수여야 합니다.")
        if best < first:
            raise ValidationError("최고 점수가 첫 점수보다 낮습니다.")
        if not _is_plain_int(count) or count < 1:
            raise ValidationError("푼 횟수는 1 이상의 정수여야 합니다.")
        if not _is_plain_int(total) or not (MIN_QUIZ_SIZE <= total <= QUIZ_SIZE):
            raise ValidationError("문제 수는 5 ~ 10 이어야 합니다.")
        return cls(score_date, first, best, count, total)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "firstScore": self.first_score,
            "bestScore": self.best_score,
            "attemptCount": self.attempt_count,
            "total": self.total,
        }

    def with_attempt(self, score: int) -> "QuizScore":
        return QuizScore(
            date=self.date,
            first_score=self.first_score,
            best_score=max(self.best_score, score),
            attempt_count=self.attempt_count + 1,
            total=self.total,
        )


SCORE_TABLE_DAYS = 14
SCORE_AVERAGE_DAYS = 7


def build_score_summary(scores: list["QuizScore"], today: date) -> dict[str, Any]:
    """학습 기록 탭의 「퀴즈 점수」 — 최근 14일(오늘이 맨 앞) 날짜별 점수 줄과 최근 7일 평균([Q6]).

    7일 평균 = 오늘을 포함한 최근 7일 가운데 퀴즈를 푼 날들의 첫 점수 평균(0.5 는 올림). 푼 날이 없으면 None.
    퀴즈 기록만 읽는다 — 연속 학습일 · 하루 목표와는 무관하다.
    """
    by_date = {s.date: s for s in scores}
    days: list[dict[str, Any]] = []
    for offset in range(SCORE_TABLE_DAYS):
        day = (today - timedelta(days=offset)).isoformat()
        line = by_date.get(day)
        days.append(
            {
                "date": day,
                "firstScore": line.first_score if line else None,
                "bestScore": line.best_score if line else None,
                "attemptCount": line.attempt_count if line else 0,
                "total": line.total if line else None,
            }
        )
    recent = [d["firstScore"] for d in days[:SCORE_AVERAGE_DAYS] if d["firstScore"] is not None]
    average = int((sum(recent) * 2 + len(recent)) // (len(recent) * 2)) if recent else None
    return {
        "today": today.isoformat(),
        "days": days,
        "recentAverage": average,
        "recentDays": len(recent),
    }


def calculate_score(correct_count: int, total: int) -> int:
    """점수 = round(맞힌 수 / 문제 수 × 100) — 0.5 는 올린다."""
    if total <= 0:
        return 0
    return int((correct_count * 100 * 2 + total) // (total * 2))


def grade_attempt(quiz: DailyQuiz, answers: tuple[int, ...]) -> dict[str, Any]:
    """답안을 채점해 점수와 문제마다 맞음 · 정답 · 해설을 돌려준다([Q5] 보장)."""
    if len(answers) != len(quiz.questions):
        raise ValidationError("답안 개수가 문제 수와 맞지 않습니다.")
    results: list[dict[str, Any]] = []
    correct_count = 0
    for idx, (question, chosen) in enumerate(zip(quiz.questions, answers)):
        correct = chosen == question.answer_index
        if correct:
            correct_count += 1
        results.append(
            {
                "index": idx,
                "questionId": question.id,
                "chosenIndex": chosen,
                "answerIndex": question.answer_index,
                "correct": correct,
                "answer": question.choices[question.answer_index],
                "explanation": question.explanation,
            }
        )
    total = len(quiz.questions)
    return {
        "date": quiz.date,
        "score": calculate_score(correct_count, total),
        "correctCount": correct_count,
        "total": total,
        "results": results,
    }
