"""조각 8(review-quiz): 내 PC 의 로컬 JSON 파일(data/quiz.json)에 오늘의 세트 하나와 날짜별 점수를 저장한다([Q4] ~ [Q6]).

퀴즈 기록은 루틴(data/routine-settings.json)과 다른 자리에 둔다 — 연속 학습일 · 하루 목표 집계가 읽지 않는다.
"""

from __future__ import annotations

from datetime import date
import json
import pathlib
import threading
from typing import Any, Callable
import uuid

from src.feedback_types import ValidationError
from src.quiz_types import (
    DATE_CHANGED_MESSAGE,
    QUIZ_CHANGED_MESSAGE,
    DailyQuiz,
    QuizAttemptRequest,
    QuizScore,
    grade_attempt,
)

DEFAULT_QUIZ_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "quiz.json"


class QuizDateMismatch(ValidationError):
    """답안의 날짜 · 세트 id 가 저장된 세트와 다르다(다음 날 세트가 먼저 만들어졌거나, 다른 저장소의 세트이거나, 세트가 없다)."""


class QuizStore:
    """오늘의 세트(늘 하나)와 날짜별 점수 줄을 원자적으로 보관한다."""

    def __init__(self, file_path: pathlib.Path | None = None) -> None:
        self.file_path = file_path or DEFAULT_QUIZ_PATH
        self._lock = threading.Lock()

    def get_today_state(self, today: date) -> tuple[DailyQuiz | None, QuizScore | None]:
        """오늘 날짜의 세트와 점수 줄. 저장된 세트가 다른 날짜면 세트는 None."""
        with self._lock:
            quiz, scores = self._read_state_unlocked()
        today_str = today.isoformat()
        today_quiz = quiz if quiz is not None and quiz.date == today_str else None
        today_score = next((s for s in scores if s.date == today_str), None)
        return today_quiz, today_score

    def get_or_create(
        self, today: date, factory: Callable[[], DailyQuiz | None]
    ) -> tuple[DailyQuiz | None, bool]:
        """오늘 세트가 있으면 그것을, 없으면 factory 로 만들어 저장한다. (세트, 새로 만들었나)([Q2] · [Q4])."""
        today_str = today.isoformat()
        with self._lock:
            quiz, scores = self._read_state_unlocked()
            if quiz is not None and quiz.date == today_str:
                return quiz, False
            made = factory()
            if made is None:
                return None, False
            self._write_state_unlocked(made, scores)
            return made, True

    def submit_attempt(self, req: QuizAttemptRequest) -> tuple[dict[str, Any], QuizScore]:
        """답안을 채점하고 그 세트 날짜의 점수 줄을 고친다. 조건 밖이면 아무것도 쓰지 않고 거절한다([Q5] · [Q6])."""
        with self._lock:
            quiz, scores = self._read_state_unlocked()
            if quiz is None or quiz.date != req.date:
                raise QuizDateMismatch(DATE_CHANGED_MESSAGE)
            if quiz.id != req.quiz_id:
                raise QuizDateMismatch(QUIZ_CHANGED_MESSAGE)
            result = grade_attempt(quiz, req.answers)
            score = result["score"]
            updated: list[QuizScore] = []
            line: QuizScore | None = None
            for existing in scores:
                if existing.date == quiz.date and line is None:
                    line = existing.with_attempt(score)
                    updated.append(line)
                else:
                    updated.append(existing)
            if line is None:
                line = QuizScore(quiz.date, score, score, 1, len(quiz.questions))
                updated.insert(0, line)
            updated.sort(key=lambda s: s.date, reverse=True)
            self._write_state_unlocked(quiz, updated)
            return result, line

    def list_scores(self) -> list[QuizScore]:
        with self._lock:
            _, scores = self._read_state_unlocked()
            return scores

    def _read_state_unlocked(self) -> tuple[DailyQuiz | None, list[QuizScore]]:
        if not self.file_path.is_file():
            return None, []
        try:
            raw_text = self.file_path.read_text(encoding="utf-8")
            data = json.loads(raw_text) if raw_text.strip() else {}
        except (OSError, json.JSONDecodeError):
            return None, []
        if not isinstance(data, dict):
            return None, []

        quiz: DailyQuiz | None = None
        if data.get("today") is not None:
            try:
                quiz = DailyQuiz.from_dict(data.get("today"))
            except ValidationError:
                quiz = None

        scores: list[QuizScore] = []
        seen: set[str] = set()
        raw_scores = data.get("scores")
        if isinstance(raw_scores, list):
            for raw in raw_scores:
                try:
                    line = QuizScore.from_dict(raw)
                except ValidationError:
                    continue
                if line.date in seen:
                    continue
                seen.add(line.date)
                scores.append(line)
        return quiz, scores

    def _write_state_unlocked(self, quiz: DailyQuiz | None, scores: list[QuizScore]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "today": quiz.to_dict() if quiz is not None else None,
            "scores": [s.to_dict() for s in scores],
        }
        temp_path = self.file_path.with_name(f"{self.file_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(self.file_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
