"""조각 8(review-quiz): 내 단어장 · 첨삭 기록으로 4지선다 문제를 만들고 오늘의 세트를 구성한다([Q1] ~ [Q3])."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import random
import re
import uuid

from src.feedback_types import FeedbackRecord
from src.quiz_types import (
    AI_MAX_COUNT,
    BLANK_MARK,
    CHOICE_COUNT,
    MAX_CHOICE_LENGTH,
    MAX_EXPLANATION_LENGTH,
    MAX_QUESTION_LENGTH,
    MIN_QUIZ_SIZE,
    QUIZ_SIZE,
    DailyQuiz,
    QuizQuestion,
    normalize_text,
)
from src.vocab_types import VocabItem

MINE_KINDS = ("blank", "meaning", "expression")


@dataclass
class PoolEntry:
    """「표현 모음」의 한 줄(설계 ③)."""

    expression: str
    meaning: str
    example: str
    blank_sources: list[tuple[str, str]] = field(default_factory=list)  # (교정 문장, 해설)


def build_expression_pool(
    vocab_items: list[VocabItem],
    feedback_records: list[FeedbackRecord],
    today: date | None = None,
) -> list[PoolEntry]:
    """단어장과 첨삭 핵심 표현을 합친 표현 모음 — 복습 예정 단어장 → 최근 첨삭 핵심 표현 → 나머지 단어장 순."""
    base_today = today or date.today()
    entries: dict[str, PoolEntry] = {}
    order: list[str] = []

    def add(expression: str, meaning: str, example: str) -> str | None:
        expr = expression.strip()
        mean = meaning.strip()
        if not expr or not mean:
            return None
        key = normalize_text(expr)
        if key not in entries:
            entries[key] = PoolEntry(expr, mean, example.strip())
            order.append(key)
        return key

    due = [item for item in vocab_items if item.is_due(today=base_today)]
    rest = [item for item in vocab_items if not item.is_due(today=base_today)]
    for item in due:
        add(item.expression, item.meaning, item.example)
    for record in feedback_records:
        for key_expr in record.feedback.key_expressions:
            key = add(key_expr.expression, key_expr.meaning, key_expr.example)
            if key is None:
                continue
            corrected = record.feedback.corrected.strip()
            if corrected and key_expr.expression.strip().lower() in corrected.lower():
                entries[key].blank_sources.append(
                    (corrected, record.feedback.explanation.strip())
                )
    for item in rest:
        add(item.expression, item.meaning, item.example)
    return [entries[key] for key in order]


def _pick_distractors(
    correct: str, candidates: list[str], rng: random.Random
) -> list[str] | None:
    """정답과 서로 다른(정리 뒤) 오답 셋을 고른다. 모으지 못하면 None."""
    seen = {normalize_text(correct)}
    unique: list[str] = []
    for cand in candidates:
        cleaned = cand.strip()
        key = normalize_text(cleaned)
        if not cleaned or len(cleaned) > MAX_CHOICE_LENGTH or key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    if len(unique) < CHOICE_COUNT - 1:
        return None
    return rng.sample(unique, CHOICE_COUNT - 1)


def _shuffle_choices(
    correct: str, distractors: list[str], rng: random.Random
) -> tuple[list[str], int]:
    choices = [correct, *distractors]
    rng.shuffle(choices)
    return choices, choices.index(correct)


def _plain_explanation(entry: PoolEntry) -> str:
    text = f"「{entry.expression}」 — {entry.meaning}"
    if entry.example:
        text += f" · 예문: {entry.example}"
    return text[:MAX_EXPLANATION_LENGTH]


def _make_question(
    entry: PoolEntry, kind: str, pool: list[PoolEntry], rng: random.Random
) -> QuizQuestion | None:
    others = [e for e in pool if e is not entry]
    if kind == "meaning":
        correct = entry.meaning
        question = f"「{entry.expression}」의 뜻으로 알맞은 것은?"
        candidates = [e.meaning for e in others]
        explanation = _plain_explanation(entry)
    elif kind == "expression":
        correct = entry.expression
        question = f"「{entry.meaning}」에 알맞은 영어 표현은?"
        candidates = [e.expression for e in others]
        explanation = _plain_explanation(entry)
    else:  # blank
        if not entry.blank_sources:
            return None
        corrected, record_explanation = entry.blank_sources[0]
        blanked = re.sub(
            re.escape(entry.expression), BLANK_MARK, corrected, count=1, flags=re.IGNORECASE
        )
        if BLANK_MARK not in blanked:
            return None
        correct = entry.expression
        question = f"빈칸에 알맞은 표현은?\n{blanked}"
        candidates = [e.expression for e in others]
        explanation = (record_explanation or _plain_explanation(entry))[:MAX_EXPLANATION_LENGTH]

    if len(question) > MAX_QUESTION_LENGTH or len(correct) > MAX_CHOICE_LENGTH:
        return None
    distractors = _pick_distractors(correct, candidates, rng)
    if distractors is None:
        return None
    choices, answer_index = _shuffle_choices(correct, distractors, rng)
    return QuizQuestion(
        id=f"q-{uuid.uuid4().hex[:12]}",
        kind=kind,
        source="mine",
        question=question,
        choices=tuple(choices),
        answer_index=answer_index,
        explanation=explanation,
        expression=entry.expression[:200],
        meaning=entry.meaning[:300],
        example=entry.example[:500],
    )


def make_mine_questions(
    pool: list[PoolEntry],
    limit: int,
    rng: random.Random,
    exclude_keys: set[str] | None = None,
) -> list[QuizQuestion]:
    """표현 모음 앞에서부터 대상 표현 하나에 문제 하나씩, 최대 limit 개를 만든다(③ 의 세 종류)."""
    excluded = exclude_keys or set()
    questions: list[QuizQuestion] = []
    if len(pool) < CHOICE_COUNT:
        return questions
    for idx, entry in enumerate(pool):
        if len(questions) >= limit:
            break
        if normalize_text(entry.expression) in excluded:
            continue
        start = idx % len(MINE_KINDS)
        kinds = MINE_KINDS[start:] + MINE_KINDS[:start]
        for kind in kinds:
            made = _make_question(entry, kind, pool, rng)
            if made is not None:
                questions.append(made)
                break
    return questions


def build_daily_quiz(
    vocab_items: list[VocabItem],
    feedback_records: list[FeedbackRecord],
    today: date | None = None,
    ai_questions: list[QuizQuestion] | None = None,
    rng: random.Random | None = None,
) -> DailyQuiz | None:
    """오늘의 세트 — 기본 배분 내 기록 7 · AI 3, AI 가 모자란 만큼 내 기록으로 최대 10문제. 5문제 미만이면 None([Q1] · [Q2])."""
    base_today = today or date.today()
    generator = rng or random.Random()
    ai = list(ai_questions or [])[:AI_MAX_COUNT]
    ai_keys = {normalize_text(q.expression) for q in ai}
    pool = build_expression_pool(vocab_items, feedback_records, today=base_today)
    mine = make_mine_questions(pool, QUIZ_SIZE - len(ai), generator, exclude_keys=ai_keys)
    questions = [*mine, *ai]
    if len(questions) < MIN_QUIZ_SIZE:
        return None
    generator.shuffle(questions)
    return DailyQuiz.create(base_today, questions)
