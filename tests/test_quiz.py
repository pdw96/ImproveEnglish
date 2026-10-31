"""조각 8(review-quiz) 자동 시험 — PR 1 몫: 설계 ② 보장 Q1(내 기록 부분) · Q2 ~ Q5 · Q10, PR 2 몫: Q1(AI 부분) · Q7 · Q9 · ③ 의 AI 응답.

두 모드를 같은 기준으로 본다.
- PC 서버 모드: `src/quiz_*.py` 와 `FeedbackApp` 의 퀴즈 길을 임시 폴더의 저장 파일로 직접 돈다.
- 단독 앱 모드: `tests/quiz_harness.mjs` 가 Node 로 `public/standalone-engine.js` 를 가짜 저장소 · 가짜 시계 위에서 돌리고,
  이 파일이 판정한다. Node 가 없으면 그 시험은 건너뛰고 이유를 남긴다.

시험 규칙(설계 ⑤): 거절 시험은 거절 뒤 저장 내용 전체가 거절 전과 같은지 본다. 성공 시험은 돌려준 값과 저장된 값을 함께 본다.
③ 의 내 기록 문제 세 종류(meaning · expression · blank)는 꼴마다 하나 이상.
"""

from __future__ import annotations

from datetime import date
import hashlib
import json
import pathlib
import random
import re
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import src.gemini as gemini_module
from src.app import FeedbackApp
from src.feedback_types import FeedbackRequest, FeedbackResponse, ValidationError
from src.history_store import HistoryStore
from src.quiz_ai import (
    AI_NOTICE_FAILED,
    AI_NOTICE_NO_KEY,
    QUIZ_SYSTEM_INSTRUCTION,
    AiQuestionsResult,
    generate_ai_questions,
    parse_ai_questions,
)
from src.quiz_service import build_daily_quiz, build_expression_pool, make_mine_questions
from src.quiz_store import QuizStore
from src.quiz_types import (
    CHOICE_COUNT,
    DailyQuiz,
    NOT_ENOUGH_MESSAGE,
    QuizQuestion,
    calculate_score,
    normalize_text,
)
from src.routine_store import RoutineStore
from src.vocab_store import VocabStore

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "tests" / "quiz_harness.mjs"
ENGINE_JS = REPO_ROOT / "public" / "standalone-engine.js"
NODE = shutil.which("node")

# 조각 8 착공 시점(main d099d54)의 첨삭 앵커볼트 지문 — 이 조각이 바꾸면 안 된다([Q10])
ANCHOR_PY_PROMPT_SCHEMA = "363183508305f639bd514b47de02fed3a7c5d14aa3d8245b6b2da2dd5109f5bb"
ANCHOR_FEEDBACK_TYPES_FILE = "a8df72d29ef4dcfff6d1309a870c64c6b06f5bba7b8cbffa813d07a14d874de5"
ANCHOR_JS_PROMPT_SCHEMA = "7a872fbd74653f1a54dfa5e474d36a2e6b9247aebde1c4de840b4fffbb066cb8"

WORDS = [
    ("give up", "포기하다", "Don't give up."),
    ("look forward to", "~을 고대하다", ""),
    ("run into", "우연히 만나다", ""),
    ("figure out", "알아내다", ""),
    ("put off", "미루다", ""),
    ("come up with", "생각해 내다", ""),
    ("get along", "잘 지내다", ""),
    ("hang out", "어울려 놀다", ""),
    ("catch up", "따라잡다", ""),
    ("turn down", "거절하다", ""),
    ("bring up", "꺼내다", ""),
]

HISTORY = [
    {
        "id": "fb-1",
        "createdAt": "2026-10-29T01:00:00Z",
        "text": "I am looking forward to meet you.",
        "inputMode": "text",
        "feedback": {
            "corrected": "I am looking forward to meeting you.",
            "explanation": "look forward to 뒤에는 동명사(-ing)가 온다.",
            "alternatives": [
                {"expression": "I can't wait to meet you.", "nuance": "더 가벼운 말"},
                {"expression": "I'm excited to meet you.", "nuance": "설렘"},
            ],
            "keyExpressions": [
                {
                    "expression": "looking forward to",
                    "meaning": "~을 기대하는 중이다",
                    "example": "I'm looking forward to it.",
                }
            ],
        },
    }
]

DAY1 = date(2026, 10, 30)
DAY2 = date(2026, 10, 31)


def vocab_dicts(n: int, next_review_date: str = "2026-10-01") -> list[dict]:
    return [
        {
            "id": f"v-{i}",
            "expression": e,
            "meaning": m,
            "example": x,
            "box": 0,
            "reviewCount": 0,
            "nextReviewDate": next_review_date,
            "createdAt": "2026-10-01T00:00:00Z",
            "lastReviewedAt": None,
        }
        for i, (e, m, x) in enumerate(WORDS[:n])
    ]


def check_question_shape(case: unittest.TestCase, q: dict) -> None:
    """[Q3] 보기 정확히 4개 · 정리 뒤 서로 다름 · 정답 번호 0 ~ 3 · 정답 보기가 대상과 맞음."""
    case.assertEqual(len(q["choices"]), CHOICE_COUNT)
    case.assertEqual(len({normalize_text(c) for c in q["choices"]}), CHOICE_COUNT)
    case.assertIn(q["answerIndex"], range(CHOICE_COUNT))
    case.assertNotIsInstance(q["answerIndex"], bool)
    answer = q["choices"][q["answerIndex"]]
    if q["kind"] == "meaning":
        case.assertEqual(answer, q["meaning"])
    else:
        case.assertEqual(answer, q["expression"])
    if q["kind"] == "blank":
        case.assertIn("____", q["question"])
        case.assertNotIn(q["expression"].lower(), q["question"].lower())
    QuizQuestion.from_dict(q)  # 저장 모양 검증을 지난다


def anchor_js_block() -> str:
    src = ENGINE_JS.read_text(encoding="utf-8")
    m = re.search(r"const SYSTEM_INSTRUCTION =.*?\n  const RESPONSE_SCHEMA = \{.*?\n  \};\n", src, re.S)
    assert m is not None, "엔진에서 첨삭 지시문 · 스키마 상수를 찾지 못했다"
    return m.group(0)


class TestQuizServer(unittest.TestCase):
    """PC 서버 모드 — FeedbackApp 의 퀴즈 길."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.vocab_path = base / "vocab.json"
        self.history_path = base / "history.json"
        self.quiz_path = base / "quiz.json"

        def no_ai(req: FeedbackRequest) -> FeedbackResponse:
            raise AssertionError("퀴즈는 첨삭 AI 를 부르지 않는다")

        self.app = FeedbackApp(
            store=HistoryStore(self.history_path),
            vocab_store=VocabStore(self.vocab_path),
            routine_store=RoutineStore(base / "routine.json"),
            quiz_store=QuizStore(self.quiz_path),
            ai_fn=no_ai,
            quiz_ai_fn=lambda pool, records: AiQuestionsResult([], "no_key"),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def seed(self, n_vocab: int, with_history: bool, next_review_date: str = "2026-10-01") -> None:
        self.vocab_path.write_text(json.dumps(vocab_dicts(n_vocab, next_review_date), ensure_ascii=False), encoding="utf-8")
        if with_history:
            self.history_path.write_text(json.dumps(HISTORY, ensure_ascii=False), encoding="utf-8")

    def quiz_file(self) -> str | None:
        return self.quiz_path.read_text(encoding="utf-8") if self.quiz_path.exists() else None

    def start(self, today: date = DAY1) -> dict:
        status, body = self.app.handle_post_quiz_today(today=today)
        self.assertEqual(status, 200)
        return body

    def attempt(self, body: object) -> tuple[int, dict]:
        raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        return self.app.handle_post_quiz_attempt(raw)

    # [Q1] 내 기록 부분
    def test_q1_mine_only_fills_ten_with_unique_targets(self) -> None:
        """[Q1] AI 문제가 없으면 내 기록으로 10문제를 채우고, 같은 대상 표현은 한 번만 묻는다."""
        self.seed(11, True)
        quiz = self.start()["quiz"]
        self.assertEqual(len(quiz["questions"]), 10)
        self.assertTrue(all(q["source"] == "mine" for q in quiz["questions"]))
        targets = [normalize_text(q["expression"]) for q in quiz["questions"]]
        self.assertEqual(len(targets), len(set(targets)))

    def test_q1_order_due_vocab_then_correction_then_rest(self) -> None:
        """[Q1] · ③ 표현 모음 순서 — 복습 예정 단어장 → 최근 첨삭 핵심 표현 → 나머지 단어장."""
        items = vocab_dicts(3, "2026-12-01") + [
            {**vocab_dicts(4)[3], "id": "due-1", "nextReviewDate": "2026-10-01"}
        ]
        self.vocab_path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        self.history_path.write_text(json.dumps(HISTORY, ensure_ascii=False), encoding="utf-8")
        pool = build_expression_pool(
            self.app.vocab_store.list_items(), self.app.store.list_records(), today=DAY1
        )
        self.assertEqual(
            [e.expression for e in pool],
            ["figure out", "looking forward to", "give up", "look forward to", "run into"],
        )

    def test_q1_same_expression_uses_vocab_data_even_when_not_due(self) -> None:
        """③ 대상 표현이 같으면 단어장 쪽 하나만 — 복습 예정이 아니어서 자리가 첨삭 쪽이어도 표현 · 뜻 · 예문은 단어장 것."""
        items = vocab_dicts(3, "2026-12-01") + [
            {**vocab_dicts(1)[0], "id": "dup", "expression": "Looking forward to", "meaning": "단어장에 적은 뜻",
             "example": "단어장 예문", "nextReviewDate": "2026-12-01"}
        ]
        self.vocab_path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        self.history_path.write_text(json.dumps(HISTORY, ensure_ascii=False), encoding="utf-8")
        pool = build_expression_pool(
            self.app.vocab_store.list_items(), self.app.store.list_records(), today=DAY1
        )
        self.assertEqual(
            [(e.expression, e.meaning, e.example) for e in pool][0],
            ("Looking forward to", "단어장에 적은 뜻", "단어장 예문"),
        )
        self.assertEqual(len(pool), 4)
        self.assertEqual(len(pool[0].blank_sources), 1)

    # [Q2]
    def test_q2_four_expressions_do_not_open_and_save_nothing(self) -> None:
        """[Q2] 5문제를 못 만들면(표현 4개 · AI 없음) 세트를 저장하지 않고 안내를 돌려준다."""
        self.seed(4, False)
        body = self.start()
        self.assertIsNone(body["quiz"])
        self.assertTrue(body["notEnough"])
        self.assertEqual(body["message"], NOT_ENOUGH_MESSAGE)
        self.assertIn("5개 이상", body["message"])
        self.assertIsNone(self.quiz_file())

    def test_q2_five_expressions_open_exactly_five(self) -> None:
        """[Q2] 경계 — 표현 5개면 5문제로 열린다."""
        self.seed(5, False)
        quiz = self.start()["quiz"]
        self.assertEqual(len(quiz["questions"]), 5)

    # [Q3]
    def test_q3_every_question_has_four_distinct_choices_one_answer(self) -> None:
        """[Q3] 모든 문제의 보기는 4개 · 서로 다르고 정답은 하나다(meaning · expression 꼴)."""
        self.seed(11, True)
        quiz = self.start()["quiz"]
        kinds = {q["kind"] for q in quiz["questions"]}
        self.assertTrue({"meaning", "expression"} <= kinds)
        for q in quiz["questions"]:
            with self.subTest(q=q["question"]):
                check_question_shape(self, q)

    def test_q3_blank_from_corrected_sentence(self) -> None:
        """[Q3] · ③ blank 꼴 — 교정 문장에 핵심 표현이 있으면 그 자리를 빈칸으로 바꾸고, 해설은 그 첨삭의 해설이다."""
        self.seed(11, True, "2026-12-01")
        quiz = self.start()["quiz"]
        blanks = [q for q in quiz["questions"] if q["kind"] == "blank"]
        self.assertEqual(len(blanks), 1)
        self.assertIn("I am ____ meeting you.", blanks[0]["question"])
        self.assertEqual(blanks[0]["explanation"], HISTORY[0]["feedback"]["explanation"])
        check_question_shape(self, blanks[0])

    def test_q3_no_question_when_three_distinct_distractors_missing(self) -> None:
        """[Q3] · ③ 서로 다른 오답 셋을 못 모으면 그 문제를 만들지 않는다(모음 4개 미만이면 0개)."""
        self.seed(3, False)
        pool = build_expression_pool(self.app.vocab_store.list_items(), [], today=DAY1)
        self.assertEqual(make_mine_questions(pool, 10, random.Random(1)), [])

    # [Q4]
    def test_q4_get_does_not_create_and_same_day_returns_same_set(self) -> None:
        """[Q4] GET 은 세트를 만들지 않고, 같은 날 [퀴즈 시작] 은 저장한 같은 세트를 돌려준다."""
        self.seed(11, True)
        status, got = self.app.handle_get_quiz_today(today=DAY1)
        self.assertEqual((status, got["quiz"]), (200, None))
        self.assertIsNone(self.quiz_file())
        first = self.start()
        stored = self.quiz_file()
        second = self.start()
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["quiz"], second["quiz"])
        self.assertEqual(stored, self.quiz_file())
        self.assertEqual(json.loads(stored)["today"], first["quiz"])

    def test_q4_new_day_makes_new_set_and_drops_old_questions(self) -> None:
        """[Q4] 날짜가 바뀐 뒤 처음 부르면 새 세트를 만들고 지난 세트의 문제 글은 지운다."""
        self.seed(11, True)
        old = self.start(DAY1)["quiz"]
        new = self.start(DAY2)
        self.assertTrue(new["created"])
        self.assertEqual(new["quiz"]["date"], DAY2.isoformat())
        saved = json.loads(self.quiz_file())
        self.assertEqual(saved["today"]["date"], DAY2.isoformat())
        old_ids = {q["id"] for q in old["questions"]}
        self.assertFalse(old_ids & {q["id"] for q in saved["today"]["questions"]})

    # [Q5]
    def test_q5_scoring_and_score_line(self) -> None:
        """[Q5] 점수 = round(맞힌 수 / 문제 수 × 100), 문제마다 맞음 · 정답 · 해설. 점수 줄은 첫 점수를 지킨다."""
        self.seed(11, True)
        quiz = self.start()["quiz"]
        right = [q["answerIndex"] for q in quiz["questions"]]
        wrong = right.copy()
        wrong[0] = (wrong[0] + 1) % 4
        status, r1 = self.attempt({"date": quiz["date"], "quizId": quiz["id"], "answers": wrong})
        self.assertEqual(status, 200)
        self.assertEqual((r1["score"], r1["correctCount"], r1["total"]), (90, 9, 10))
        self.assertFalse(r1["results"][0]["correct"])
        self.assertEqual(r1["results"][0]["answer"], quiz["questions"][0]["choices"][right[0]])
        self.assertEqual(r1["results"][0]["explanation"], quiz["questions"][0]["explanation"])
        status, r2 = self.attempt({"date": quiz["date"], "quizId": quiz["id"], "answers": right})
        self.assertEqual(r2["score"], 100)
        line = {"date": quiz["date"], "firstScore": 90, "bestScore": 100, "attemptCount": 2, "total": 10}
        self.assertEqual(r2["scoreLine"], line)
        self.assertEqual(json.loads(self.quiz_file())["scores"], [line])
        self.assertEqual(self.app.handle_get_quiz_today(today=DAY1)[1]["score"], line)

    def test_q5_score_rounding(self) -> None:
        """[Q5] 반올림 — 0.5 는 올린다."""
        cases = {(7, 8): 88, (1, 8): 13, (1, 6): 17, (5, 6): 83, (0, 5): 0, (5, 5): 100, (2, 3): 67}
        for (c, t), want in cases.items():
            with self.subTest(c=c, t=t):
                self.assertEqual(calculate_score(c, t), want)

    def test_q5_rejects_leave_storage_unchanged(self) -> None:
        """[Q5] 조건 밖 답안은 400 이고 저장 파일이 거절 전과 글자까지 같다."""
        self.seed(11, True)
        quiz = self.start()["quiz"]
        right = [q["answerIndex"] for q in quiz["questions"]]
        bad = {
            "notJson": "{bad",
            "notObject": [1, 2],
            "badDate": {"date": "2026/10/30", "quizId": quiz["id"], "answers": right},
            "impossibleDate": {"date": "2026-02-30", "quizId": quiz["id"], "answers": right},
            "noAnswers": {"date": quiz["date"], "quizId": quiz["id"], "answers": []},
            "answersNotList": {"date": quiz["date"], "quizId": quiz["id"], "answers": "0123"},
            "tooFew": {"date": quiz["date"], "quizId": quiz["id"], "answers": right[:9]},
            "tooMany": {"date": quiz["date"], "quizId": quiz["id"], "answers": [*right, 0]},
            "outOfRange": {"date": quiz["date"], "quizId": quiz["id"], "answers": [4] * 10},
            "negative": {"date": quiz["date"], "quizId": quiz["id"], "answers": [-1] * 10},
            "notInt": {"date": quiz["date"], "quizId": quiz["id"], "answers": [1.5] * 10},
            "boolean": {"date": quiz["date"], "quizId": quiz["id"], "answers": [True] * 10},
            "otherDate": {"date": "2026-10-29", "quizId": quiz["id"], "answers": right},
            "noQuizId": {"date": quiz["date"], "answers": right},
            "blankQuizId": {"date": quiz["date"], "quizId": "  ", "answers": right},
            "otherQuiz": {"date": quiz["date"], "quizId": "quiz-from-another-store", "answers": right},
        }
        before = self.quiz_file()
        for name, body in bad.items():
            with self.subTest(name=name):
                status, data = self.attempt(body)
                self.assertEqual(status, 400)
                self.assertIn("error", data)
                self.assertEqual(self.quiz_file(), before)

    def test_q5_answers_for_another_set_are_rejected(self) -> None:
        """[Q5] 경계(PR 1 2회차) — 답안은 화면에 보인 그 세트에만 채점한다. 같은 날짜라도 세트 id 가 다르면 거절하고 저장 그대로."""
        self.seed(11, True)
        quiz = self.start()["quiz"]
        before = self.quiz_file()
        other = {"date": quiz["date"], "quizId": "quiz-from-another-store",
                 "answers": [q["answerIndex"] for q in quiz["questions"]]}
        status, data = self.attempt(other)
        self.assertEqual(status, 400)
        self.assertTrue(data["dateChanged"])
        self.assertIn("퀴즈가 바뀌어", data["error"])
        self.assertEqual(self.quiz_file(), before)
        self.assertTrue(quiz["id"].startswith("quiz-"))
        self.assertEqual(json.loads(before)["today"]["id"], quiz["id"])

    def test_q5_rollover_keep_original_date(self) -> None:
        """[Q5] 날짜 넘김 ① — 세트 A 를 만든 뒤 날짜를 넘겨 A 의 답안을 내면 A 의 날짜로 기록된다."""
        self.seed(11, True)
        a = self.start(DAY1)["quiz"]
        status, r = self.attempt({"date": a["date"], "quizId": a["id"], "answers": [q["answerIndex"] for q in a["questions"]]})
        self.assertEqual(status, 200)
        self.assertEqual(r["scoreLine"]["date"], DAY1.isoformat())
        self.assertIsNone(self.app.handle_get_quiz_today(today=DAY2)[1]["score"])

    def test_q5_rollover_after_new_set_rejects_old_answers(self) -> None:
        """[Q5] 날짜 넘김 ② — 다음 날 세트 B 가 먼저 만들어지면 A 의 답안은 거절되고 저장 내용이 그대로다."""
        self.seed(11, True)
        a = self.start(DAY1)["quiz"]
        self.start(DAY2)
        before = self.quiz_file()
        status, data = self.attempt({"date": a["date"], "quizId": a["id"], "answers": [q["answerIndex"] for q in a["questions"]]})
        self.assertEqual(status, 400)
        self.assertTrue(data["dateChanged"])
        self.assertIn("날짜가 바뀌어", data["error"])
        self.assertEqual(self.quiz_file(), before)

    def test_corrupt_quiz_file_is_treated_as_no_set(self) -> None:
        """망가진 퀴즈 파일은 세트 없음으로 보고, [퀴즈 시작] 이 새로 만든다."""
        self.seed(11, True)
        self.quiz_path.write_text('{"today": {"date": "2026-10-30", "questions": [{"id": "x"}]}}', encoding="utf-8")
        self.assertIsNone(self.app.handle_get_quiz_today(today=DAY1)[1]["quiz"])
        self.assertTrue(self.start()["created"])

    def test_question_validation_rejects_bad_shapes(self) -> None:
        """[Q3] 저장 모양 검증 — 보기 3개 · 겹치는 보기 · 정답 번호 4 · 불 값 정답은 거절한다."""
        self.seed(11, True)
        good = self.start()["quiz"]["questions"][0]
        bads = [
            {**good, "choices": good["choices"][:3]},
            {**good, "choices": [good["choices"][0], good["choices"][0].upper(), *good["choices"][2:]]},
            {**good, "answerIndex": 4},
            {**good, "answerIndex": True},
            {**good, "kind": "ai"},
            {**good, "question": "x" * 301},
        ]
        quiz = json.loads(self.quiz_file())["today"]
        with self.assertRaises(ValidationError):
            DailyQuiz.from_dict({k: v for k, v in quiz.items() if k != "id"})
        for bad in bads:
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    QuizQuestion.from_dict(bad)

    def test_save_failure_is_not_reported_as_success(self) -> None:
        """[Q4] · [Q6] 저장 파일을 쓰지 못하면 세트를 열지 않고 점수를 기록했다고 하지 않는다(500 과 안내)."""
        self.seed(11, True)
        real_write = self.app.quiz_store._write_state_unlocked

        def broken_write(*args, **kwargs):
            raise OSError("disk full")

        self.app.quiz_store._write_state_unlocked = broken_write
        status, body = self.app.handle_post_quiz_today(today=DAY1)
        self.assertEqual(status, 500)
        self.assertTrue(body["saveFailed"])
        self.assertIsNone(self.quiz_file())

        self.app.quiz_store._write_state_unlocked = real_write
        quiz = self.start()["quiz"]
        before = self.quiz_file()
        self.app.quiz_store._write_state_unlocked = broken_write
        status, body = self.attempt({"date": quiz["date"], "quizId": quiz["id"], "answers": [q["answerIndex"] for q in quiz["questions"]]})
        self.assertEqual(status, 500)
        self.assertTrue(body["saveFailed"])
        self.assertNotIn("score", body)
        self.assertEqual(self.quiz_file(), before)

    def test_screen_drops_responses_that_arrive_after_reset(self) -> None:
        """화면 — 모드 전환 · 백업 불러오기로 초기화한 뒤 도착한 [퀴즈 시작] · 제출 응답은 버린다(다른 모드의 세트를 되살리지 않게)."""
        src = (REPO_ROOT / "public" / "app.js").read_text(encoding="utf-8")
        reset = re.search(r"function resetDailyQuiz\(\) \{(.*?)\n  \}", src, re.S).group(1)
        self.assertIn("dailyQuiz.epoch += 1;", reset)
        for fn in ("startDailyQuiz", "submitDailyQuiz"):
            with self.subTest(fn=fn):
                body = re.search(rf"async function {fn}\(\) \{{(.*?)\n  \}}\n", src, re.S).group(1)
                self.assertIn("const epoch = dailyQuiz.epoch;", body)
                after_json = body.split("await res.json();", 1)[1]
                self.assertTrue(after_json.lstrip().startswith("if (epoch !== dailyQuiz.epoch) return;"))
        self.assertIn("resetDailyQuiz();", re.search(r"async function refreshAllData\(\) \{(.*?)\n  \}", src, re.S).group(1))

    # [Q10]
    def test_q10_feedback_anchor_unchanged(self) -> None:
        """[Q10] 첨삭 요청 · 응답 구조와 첨삭 지시문 · 스키마가 조각 8 전과 글자까지 같다(서버 · 엔진)."""
        py_print = hashlib.sha256(
            (
                gemini_module.SYSTEM_INSTRUCTION
                + json.dumps(gemini_module.RESPONSE_SCHEMA, ensure_ascii=False, sort_keys=True)
            ).encode()
        ).hexdigest()
        self.assertEqual(py_print, ANCHOR_PY_PROMPT_SCHEMA)
        ft = (REPO_ROOT / "src" / "feedback_types.py").read_bytes()
        self.assertEqual(hashlib.sha256(ft).hexdigest(), ANCHOR_FEEDBACK_TYPES_FILE)
        self.assertEqual(hashlib.sha256(anchor_js_block().encode()).hexdigest(), ANCHOR_JS_PROMPT_SCHEMA)


FAKE_KEY = "TEST-ONLY-fake-gemini-key-quiz-0000"


def ai_item(expression: str, **overrides) -> dict:
    item = {
        "question": "I really want to ____ this habit.",
        "choices": [expression, "take after", "look into", "run out of"],
        "answerIndex": 0,
        "explanation": "정답 표현이 문장의 뜻에 맞는다.",
        "expression": expression,
        "meaning": "뜻",
        "example": f"I really want to {expression} this habit.",
    }
    item.update(overrides)
    return item


def gemini_reply(items: list) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps({"questions": items})}]}}]}


AI_BAD_FORMS = {
    "choicesThree": ai_item("cut down on", choices=["cut down on", "a", "b"]),
    "choicesFive": ai_item("cut down on", choices=["cut down on", "a", "b", "c", "d"]),
    "choicesDuplicate": ai_item("cut down on", choices=["cut down on", "Cut  down on", "b", "c"]),
    "choiceTooLong": ai_item("cut down on", choices=["cut down on", "x" * 201, "b", "c"]),
    "answerOutOfRange": ai_item("cut down on", answerIndex=4),
    "answerBoolean": ai_item("cut down on", answerIndex=True),
    "answerString": ai_item("cut down on", answerIndex="0"),
    "answerNotExpression": ai_item("cut down on", answerIndex=1),
    "noBlank": ai_item("cut down on", question="I really want to cut down on this habit."),
    "questionTooLong": ai_item("cut down on", question="____ " + "x" * 300),
    "questionEmpty": ai_item("cut down on", question=""),
    "explanationEmpty": ai_item("cut down on", explanation=" "),
    "explanationTooLong": ai_item("cut down on", explanation="가" * 501),
    "expressionTooLong": ai_item("x" * 201),
    "meaningEmpty": ai_item("cut down on", meaning=""),
    "meaningTooLong": ai_item("cut down on", meaning="가" * 301),
    "exampleTooLong": ai_item("cut down on", example="x" * 501),
    "missingField": {k: v for k, v in ai_item("cut down on").items() if k != "explanation"},
    "duplicateTarget": ai_item("Put Up With"),
    "notObject": "question",
}


class TestQuizAiServer(unittest.TestCase):
    """PC 서버 모드 — PR 2: AI 새 문제(Q1 AI 부분 · Q7 · Q9 · ③ 의 AI 응답)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        (base / "vocab.json").write_text(json.dumps(vocab_dicts(11), ensure_ascii=False), encoding="utf-8")
        (base / "history.json").write_text(json.dumps(HISTORY, ensure_ascii=False), encoding="utf-8")
        self.ai_calls = 0
        self.ai_result = AiQuestionsResult([], "no_key")

        def fake_quiz_ai(pool, records):
            self.ai_calls += 1
            return self.ai_result

        self.app = FeedbackApp(
            store=HistoryStore(base / "history.json"),
            vocab_store=VocabStore(base / "vocab.json"),
            routine_store=RoutineStore(base / "routine.json"),
            quiz_store=QuizStore(base / "quiz.json"),
            ai_fn=lambda req: (_ for _ in ()).throw(AssertionError("첨삭 AI 를 부르지 않는다")),
            quiz_ai_fn=fake_quiz_ai,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def parsed(self, items: list) -> list[QuizQuestion]:
        return parse_ai_questions(gemini_reply(items), rng=random.Random(3))

    def test_q1_ai_zero_to_three_always_ten_and_targets_unique(self) -> None:
        """[Q1] AI 문제 0 ~ 3개마다 내 기록으로 채워 10문제, AI 는 3을 넘지 않고, 같은 대상 표현은 한 번(내 기록에도 있는 give up)."""
        pool = ["give up", "put up with", "cut down on", "get rid of"]
        for n in range(0, 5):
            with self.subTest(n=n):
                quiz = build_daily_quiz(
                    self.app.vocab_store.list_items(),
                    self.app.store.list_records(),
                    today=DAY1,
                    ai_questions=self.parsed([ai_item(e) for e in pool[:n]]),
                    rng=random.Random(5),
                )
                ai = [q for q in quiz.questions if q.source == "ai"]
                self.assertEqual(len(quiz.questions), 10)
                self.assertEqual(len(ai), min(n, 3))
                targets = [normalize_text(q.expression) for q in quiz.questions]
                self.assertEqual(len(targets), len(set(targets)))

    def test_q9_notice_by_outcome_and_ai_called_once_per_day(self) -> None:
        """[Q9] · [Q4] 새로 만들 때만 안내(키 없음 · 실패 · 일부), 3개면 안내 없음. 같은 날 다시 불러도 AI 는 한 번만."""
        cases = [
            (AiQuestionsResult([], "no_key"), AI_NOTICE_NO_KEY, 0),
            (AiQuestionsResult([], "failed"), AI_NOTICE_FAILED, 0),
            (AiQuestionsResult(self.parsed([ai_item("put up with"), ai_item("cut down on")]), "ok"),
             "AI 새 문제를 2개만 만들어 나머지는 내 기록으로 채웠습니다.", 2),
            (AiQuestionsResult(self.parsed([ai_item(e) for e in ("put up with", "cut down on", "get rid of")]), "ok"), None, 3),
        ]
        for result, notice, count in cases:
            with self.subTest(notice=notice):
                self.app.quiz_store.file_path.unlink(missing_ok=True)
                self.ai_calls = 0
                self.ai_result = result
                status, first = self.app.handle_post_quiz_today(today=DAY1)
                self.assertEqual(status, 200)
                self.assertEqual(first["aiCount"], count)
                self.assertEqual(first.get("aiNotice"), notice)
                self.assertEqual(len(first["quiz"]["questions"]), 10)
                _, second = self.app.handle_post_quiz_today(today=DAY1)
                self.assertFalse(second["created"])
                self.assertNotIn("aiNotice", second)
                self.assertEqual(self.ai_calls, 1)

    def test_q4_concurrent_starts_call_ai_once_and_share_one_set(self) -> None:
        """[Q4] · [Q9] 겹친 [퀴즈 시작](서버는 요청마다 스레드) — AI 는 한 번, 세트는 하나, 새로 만든 응답은 하나."""
        import threading
        import time

        self.ai_result = AiQuestionsResult(self.parsed([ai_item("put up with")]), "ok")

        def slow_ai(pool, records):
            self.ai_calls += 1
            time.sleep(0.2)
            return self.ai_result

        self.app._quiz_ai_fn = slow_ai
        results: list[dict] = []
        threads = [
            threading.Thread(target=lambda: results.append(self.app.handle_post_quiz_today(today=DAY1)[1]))
            for _ in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(self.ai_calls, 1)
        self.assertEqual(len({r["quiz"]["id"] for r in results}), 1)
        self.assertEqual(sum(1 for r in results if r["created"]), 1)

    def test_q4_older_date_start_never_overwrites_newer_set(self) -> None:
        """[Q4] 경계(PR 2 2회차) — 저장된 세트보다 오래된 날짜의 [퀴즈 시작](자정 무렵 늦은 요청)은 새 세트를 덮지 않고 AI 도 부르지 않는다."""
        _, newer = self.app.handle_post_quiz_today(today=DAY2)
        self.assertTrue(newer["created"])
        before = self.app.quiz_store.file_path.read_text(encoding="utf-8")
        calls_before = self.ai_calls
        status, older = self.app.handle_post_quiz_today(today=DAY1)
        self.assertEqual(status, 200)
        self.assertFalse(older["created"])
        self.assertEqual(older["quiz"]["id"], newer["quiz"]["id"])
        self.assertEqual(older["quiz"]["date"], DAY2.isoformat())
        self.assertEqual(self.ai_calls, calls_before)
        self.assertEqual(self.app.quiz_store.file_path.read_text(encoding="utf-8"), before)

        def must_not_build():
            raise AssertionError("새 세트가 있으면 만들지 않는다")

        quiz, created = self.app.quiz_store.get_or_create(DAY1, must_not_build)
        self.assertEqual((quiz.id, created), (newer["quiz"]["id"], False))

    def test_q9_key_only_in_header_and_quiz_prompt_not_feedback_prompt(self) -> None:
        """[Q9] 키는 x-goog-api-key 헤더로만(주소에 없음), 요청은 퀴즈 전용 지시문 · 온도 0.7 · 배운 표현 최대 10개 · 교정 문장."""
        seen = {}

        def transport(url, headers, body):
            seen.update(url=url, headers=headers, body=json.loads(body))
            return gemini_reply([ai_item("put up with")])

        pool = build_expression_pool(self.app.vocab_store.list_items(), self.app.store.list_records(), today=DAY1)
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}, clear=False):
            result = generate_ai_questions(pool, self.app.store.list_records(), transport=transport)
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.questions), 1)
        self.assertEqual(seen["headers"]["x-goog-api-key"], FAKE_KEY)
        self.assertNotIn(FAKE_KEY, seen["url"])
        self.assertNotIn(FAKE_KEY, json.dumps(seen["body"], ensure_ascii=False))
        self.assertEqual(seen["body"]["systemInstruction"]["parts"][0]["text"], QUIZ_SYSTEM_INSTRUCTION)
        self.assertNotEqual(QUIZ_SYSTEM_INSTRUCTION, gemini_module.SYSTEM_INSTRUCTION)
        self.assertEqual(seen["body"]["generationConfig"]["temperature"], 0.7)
        user_text = seen["body"]["contents"][0]["parts"][0]["text"]
        self.assertEqual(user_text.count("\n- ") , min(len(pool), 10) + 1)
        self.assertIn("I am looking forward to meeting you.", user_text)

    def test_q9_failures_return_empty_without_leaking_key(self) -> None:
        """[Q9] 키 없음이면 부르지 않고 no_key, 전송 오류 · 해석 불가 응답이면 failed — 키는 결과 어디에도 없다."""
        pool = build_expression_pool(self.app.vocab_store.list_items(), self.app.store.list_records(), today=DAY1)

        def boom(url, headers, body):
            raise RuntimeError(f"HTTP 429 {headers['x-goog-api-key']}")

        def must_not_call(url, headers, body):
            raise AssertionError("키가 없으면 부르지 않는다")

        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            self.assertEqual(generate_ai_questions(pool, [], transport=must_not_call).status, "no_key")
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}, clear=False):
            failed = generate_ai_questions(pool, [], transport=boom)
            garbled = generate_ai_questions(pool, [], transport=lambda u, h, b: {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]})
        for result in (failed, garbled):
            self.assertEqual((result.status, result.questions), ("failed", []))
            self.assertEqual(result.notice(), AI_NOTICE_FAILED)
            self.assertNotIn(FAKE_KEY, repr(result))

    def test_ai_response_each_bad_form_drops_only_that_question(self) -> None:
        """③ AI 응답 — 꼴마다 그 문제만 버리고(좋은 문제 하나와 함께 보내 1개만 남음), 3개를 넘으면 앞의 3개만, 받은 보기는 다시 섞어도 정답이 맞다."""
        for name, bad in AI_BAD_FORMS.items():
            with self.subTest(form=name):
                kept = self.parsed([ai_item("put up with"), bad])
                self.assertEqual([q.expression for q in kept], ["put up with"])
        four = self.parsed([ai_item(e) for e in ("put up with", "cut down on", "get rid of", "make up for")])
        self.assertEqual(len(four), 3)
        for q in four:
            self.assertEqual(q.choices[q.answer_index], q.expression)
            self.assertEqual((q.kind, q.source), ("ai", "ai"))
        self.assertEqual(parse_ai_questions({"candidates": []}), [])
        self.assertEqual(parse_ai_questions({"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}), [])

    def test_q7_ai_expression_saves_to_vocab_and_reports_duplicate(self) -> None:
        """[Q7] AI 문제의 대상 표현 · 뜻 · 예문으로 단어장 추가 — 처음은 담고, 다시 누르면 「이미 있음」, 복습 일정은 그대로."""
        q = self.parsed([ai_item("put up with")])[0]
        payload = json.dumps({"expression": q.expression, "meaning": q.meaning, "example": q.example}).encode()
        status, first = self.app.handle_post_vocab(payload, today=DAY1)
        self.assertEqual((status, first["duplicated"]), (200, False))
        self.assertEqual((first["meaning"], first["example"]), (q.meaning, q.example))
        status, again = self.app.handle_post_vocab(payload, today=DAY1)
        self.assertTrue(again["duplicated"])
        self.assertEqual(again["nextReviewDate"], first["nextReviewDate"])

    def test_q7_screen_save_button_posts_ai_question_fields(self) -> None:
        """[Q7] 화면 — 결과의 「AI 가 낸 새 표현」 목록은 AI 문제마다 버튼을 두고, 그 문제의 표현 · 뜻 · 예문을 보내며 이미 있음을 알린다."""
        src = (REPO_ROOT / "public" / "app.js").read_text(encoding="utf-8")
        body = re.search(r"function renderDailyQuizAiWords\(\) \{(.*?)\n  \}\n", src, re.S).group(1)
        self.assertIn('q.source === "ai"', body)
        self.assertIn('fetch("/api/vocab"', body)
        self.assertIn("expression: q.expression, meaning: q.meaning, example: q.example", body)
        self.assertIn("data.duplicated", body)
        self.assertIn("renderDailyQuizAiWords();", src)


def _run_harness() -> dict:
    proc = subprocess.run(
        [NODE, str(HARNESS)], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False
    )
    if proc.returncode != 0:
        raise AssertionError(f"quiz_harness.mjs 실행 실패: {proc.stderr}")
    return json.loads(proc.stdout)


@unittest.skipIf(NODE is None, "Node 가 없어 단독 앱 엔진을 실제로 돌리는 퀴즈 시험을 건너뜁니다 (Node 18 이상 필요)")
class TestQuizEngine(unittest.TestCase):
    """단독 앱 모드 — 엔진을 실제로 돌려 같은 보장을 본다."""

    out: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.out = _run_harness()

    def test_q1_mine_only_fills_ten_with_unique_targets(self) -> None:
        """[Q1] AI 문제가 없으면 내 기록으로 10문제, 같은 대상 표현은 한 번."""
        quiz = self.out["full"]["first"]["body"]["quiz"]
        self.assertEqual(len(quiz["questions"]), 10)
        self.assertTrue(all(q["source"] == "mine" for q in quiz["questions"]))
        targets = [normalize_text(q["expression"]) for q in quiz["questions"]]
        self.assertEqual(len(targets), len(set(targets)))
        self.assertEqual(self.out["full"]["geminiCalls"], 0)

    def test_q1_same_expression_uses_vocab_data_even_when_not_due(self) -> None:
        """③ 대상 표현이 같으면 뜻 · 예문은 단어장 것(복습 예정이 아니어도)."""
        qs = [q for q in self.out["vocabWins"]["body"]["quiz"]["questions"]
              if normalize_text(q["expression"]) == "looking forward to"]
        self.assertEqual(len(qs), 1)
        self.assertEqual((qs[0]["meaning"], qs[0]["example"]), ("단어장에 적은 뜻", "단어장 예문"))

    def test_q2_four_expressions_do_not_open_and_save_nothing(self) -> None:
        """[Q2] 표현 4개면 열지 않고 안내만, 기기 저장소는 그대로."""
        scene = self.out["notEnough"]
        self.assertEqual(scene["res"]["status"], 200)
        self.assertIsNone(scene["res"]["body"]["quiz"])
        self.assertTrue(scene["res"]["body"]["notEnough"])
        self.assertEqual(scene["res"]["body"]["message"], NOT_ENOUGH_MESSAGE)
        self.assertEqual(scene["after"], scene["before"])

    def test_q2_five_expressions_open_exactly_five(self) -> None:
        """[Q2] 경계 — 표현 5개면 5문제."""
        self.assertEqual(len(self.out["five"]["body"]["quiz"]["questions"]), 5)

    def test_q3_every_question_has_four_distinct_choices_one_answer(self) -> None:
        """[Q3] 모든 문제 — 보기 4개 · 서로 다름 · 정답 하나(meaning · expression · blank 꼴)."""
        questions = self.out["full"]["first"]["body"]["quiz"]["questions"] + self.out["blank"]["body"]["quiz"]["questions"]
        kinds = {q["kind"] for q in questions}
        self.assertEqual(kinds, {"meaning", "expression", "blank"})
        for q in questions:
            with self.subTest(q=q["question"]):
                check_question_shape(self, q)

    def test_q3_blank_from_corrected_sentence(self) -> None:
        """[Q3] · ③ 복습 예정이 없으면 첨삭 핵심 표현이 앞에 오고, 교정 문장으로 빈칸 문제가 나온다."""
        blanks = [q for q in self.out["blank"]["body"]["quiz"]["questions"] if q["kind"] == "blank"]
        self.assertEqual(len(blanks), 1)
        self.assertIn("I am ____ meeting you.", blanks[0]["question"])
        self.assertEqual(blanks[0]["explanation"], HISTORY[0]["feedback"]["explanation"])

    def test_q4_get_does_not_create_and_same_day_returns_same_set(self) -> None:
        """[Q4] GET 은 만들지 않고, 같은 날 [퀴즈 시작] 은 같은 세트."""
        full = self.out["full"]
        self.assertIsNone(full["getBefore"]["body"]["quiz"])
        self.assertIsNone(full["storedAfterGet"])
        self.assertTrue(full["first"]["body"]["created"])
        self.assertFalse(full["second"]["body"]["created"])
        self.assertEqual(full["first"]["body"]["quiz"], full["second"]["body"]["quiz"])
        self.assertEqual(full["getAfter"]["body"]["quiz"], full["first"]["body"]["quiz"])

    def test_q4_new_day_makes_new_set(self) -> None:
        """[Q4] 날짜가 바뀐 뒤 처음 부르면 새 세트 — 지난 문제는 남지 않는다."""
        scene = self.out["rolloverReplaced"]
        self.assertEqual(scene["bDate"], "2026-10-31")
        self.assertTrue(scene["bCreated"])
        self.assertEqual(scene["aIdsInB"], 0)

    def test_q5_scoring_and_score_line(self) -> None:
        """[Q5] 채점과 점수 줄 — 첫 점수 90 을 지키고 최고 100 · 2회."""
        full = self.out["full"]
        self.assertEqual(full["attemptWrong"]["status"], 200)
        self.assertEqual(full["attemptWrong"]["body"]["score"], 90)
        self.assertFalse(full["attemptWrong"]["body"]["results"][0]["correct"])
        line = {"date": "2026-10-30", "firstScore": 90, "bestScore": 100, "attemptCount": 2, "total": 10}
        self.assertEqual(full["attemptRight"]["body"]["scoreLine"], line)
        self.assertEqual(full["getScored"]["body"]["score"], line)

    def test_q5_rejects_leave_storage_unchanged(self) -> None:
        """[Q5] 조건 밖 답안 16꼴 — 400 이고 기기 저장소가 거절 전과 같다."""
        rejects = self.out["full"]["rejects"]
        self.assertEqual(len(rejects), 16)
        for name, r in rejects.items():
            with self.subTest(name=name):
                self.assertEqual(r["status"], 400)
                self.assertIn("error", r["body"])
                self.assertTrue(r["unchanged"])

    def test_q5_answers_for_another_store_set_are_rejected(self) -> None:
        """[Q5] 경계(PR 1 2회차) — 서버 모드에서 서버가 끊겨 엔진으로 넘어온, 같은 날짜 · 같은 문제 수의 다른 세트 답안은 거절하고 저장 그대로."""
        scene = self.out["fallback"]
        self.assertEqual(scene["res"]["status"], 400)
        self.assertTrue(scene["res"]["body"]["dateChanged"])
        self.assertIn("퀴즈가 바뀌어", scene["res"]["body"]["error"])
        self.assertTrue(scene["unchanged"])

    def test_q5_rollover_keep_original_date(self) -> None:
        """[Q5] 날짜 넘김 ① — A 의 날짜로 기록된다."""
        scene = self.out["rolloverKeep"]
        self.assertEqual(scene["res"]["status"], 200)
        self.assertEqual(scene["res"]["body"]["scoreLine"]["date"], "2026-10-30")
        self.assertIsNone(scene["getNext"]["body"]["score"])

    def test_q5_rollover_after_new_set_rejects_old_answers(self) -> None:
        """[Q5] 날짜 넘김 ② — 거절되고 저장 내용이 그대로."""
        scene = self.out["rolloverReplaced"]
        self.assertEqual(scene["res"]["status"], 400)
        self.assertTrue(scene["res"]["body"]["dateChanged"])
        self.assertTrue(scene["unchanged"])

    def test_storage_full_is_not_reported_as_success(self) -> None:
        """[Q4] · [Q6] 기기 저장 공간이 꽉 차면 세트를 열지 않고(500), 점수를 기록했다고 하지 않는다(500 · 저장 그대로)."""
        scene = self.out["storageFull"]
        self.assertEqual(scene["createRes"]["status"], 500)
        self.assertTrue(scene["createRes"]["body"]["saveFailed"])
        self.assertFalse(scene["createStored"])
        self.assertEqual(scene["attemptRes"]["status"], 500)
        self.assertNotIn("score", scene["attemptRes"]["body"])
        self.assertTrue(scene["attemptUnchanged"])
        self.assertIsNone(scene["scoreAfter"])

    # PR 2 — AI 새 문제
    def test_q1_ai_zero_to_three_always_ten(self) -> None:
        """[Q1] AI 문제 0 ~ 3개마다 내 기록으로 채워 10문제, 안내는 모자랄 때만."""
        for n, scene in self.out["aiCounts"].items():
            with self.subTest(n=n):
                self.assertEqual(scene["total"], 10)
                self.assertEqual(scene["ai"], int(n))
                self.assertEqual(scene["aiCount"], int(n))
                self.assertEqual(scene["aiNotice"] is None, int(n) == 3)

    def test_q1_ai_target_not_repeated_in_mine_and_called_once(self) -> None:
        """[Q1] · [Q4] AI 3개 중 내 기록에도 있는 표현(give up)은 내 기록 쪽에서 빠지고, 같은 날 다시 불러도 AI 는 한 번."""
        scene = self.out["aiOk"]
        quiz = scene["first"]["body"]["quiz"]
        targets = [normalize_text(q["expression"]) for q in quiz["questions"]]
        self.assertEqual(len(targets), len(set(targets)))
        self.assertIn("give up", targets)
        self.assertEqual(sum(q["source"] == "ai" for q in quiz["questions"]), 3)
        self.assertFalse(scene["second"]["body"]["created"])
        self.assertNotIn("aiNotice", scene["second"]["body"])
        self.assertEqual(len(scene["aiCalls"]), 1)
        for q in quiz["questions"]:
            check_question_shape(self, q)

    def test_q9_key_only_in_header_and_quiz_prompt(self) -> None:
        """[Q9] 키는 x-goog-api-key 헤더로만, 주소 · 본문에 없음. 요청은 퀴즈 전용 지시문 · 온도 0.7."""
        call = self.out["aiOk"]["aiCalls"][0]
        key = self.out["aiOk"]["KEY"]
        self.assertEqual(call["apiKeyHeader"], key)
        self.assertNotIn(key, call["url"])
        self.assertNotIn(key, call["body"])
        body = json.loads(call["body"])
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], QUIZ_SYSTEM_INSTRUCTION)
        self.assertEqual(body["generationConfig"]["temperature"], 0.7)

    def test_q9_failed_no_key_locked_fill_with_mine_and_notice(self) -> None:
        """[Q9] 호출 실패 · 키 없음 · 금고 잠김 — 내 기록으로 10문제와 안내, 키 없음 · 잠김이면 부르지 않음, 안내에 키 없음."""
        failed, no_key, locked = self.out["aiFailed"], self.out["aiNoKey"], self.out["aiLocked"]
        self.assertEqual((failed["total"], failed["aiNotice"], failed["aiCalls"]), (10, AI_NOTICE_FAILED, 2))
        self.assertNotIn(failed["KEY"], failed["bodyText"])
        for scene in (no_key, locked):
            self.assertEqual((scene["total"], scene["aiNotice"], scene["aiCalls"]), (10, AI_NOTICE_NO_KEY, 0))

    def test_ai_response_each_bad_form_drops_only_that_question(self) -> None:
        """③ AI 응답 — 꼴마다 그 문제만 버리고, 3개를 넘으면 앞의 3개, 해석 못 하면 0개와 실패 안내."""
        bad = dict(self.out["aiBad"])
        unparsable = bad.pop("unparsable")
        more = bad.pop("moreThanThree")
        self.assertEqual(set(bad), set(AI_BAD_FORMS))
        for name, kept in bad.items():
            with self.subTest(form=name):
                self.assertEqual(kept, 1)
        self.assertEqual(more, 3)
        self.assertEqual(unparsable, {"ai": 0, "total": 10, "aiNotice": AI_NOTICE_FAILED})

    def test_q4_concurrent_starts_same_tab_share_one_set(self) -> None:
        """[Q4] · [Q9] 같은 화면에서 겹친 [퀴즈 시작] — 만들기 하나를 함께 기다려 AI 한 번 · 세트 하나."""
        scene = self.out["concurrentSameTab"]
        self.assertEqual(scene, {"sameSet": True, "storedIsThatSet": True, "aiCalls": 1})

    def test_q4_two_tabs_late_start_does_not_overwrite_set_or_scores(self) -> None:
        """[Q4] · [Q6] 두 탭 — A 가 AI 를 기다리는 사이 B 가 세트를 만들고 점수를 냈으면, A 는 B 의 세트를 돌려받고 점수를 덮지 않는다."""
        scene = self.out["concurrentTwoTabs"]
        self.assertEqual(scene, {"bAttemptStatus": 200, "aCreated": False, "aGotBSet": True,
                                 "storedIsBSet": True, "scoresKept": True})

    def test_q4_midnight_late_start_does_not_overwrite_next_day_set(self) -> None:
        """[Q4] 경계(PR 2 2회차) — 자정을 넘겨 끝난 늦은 시작 · 시계가 늦은 탭의 시작은 다음 날 세트를 덮지 않고, 그 세트의 답안은 받아진다."""
        self.assertEqual(self.out["midnight"], {
            "bDate": "2026-10-31", "storedDate": "2026-10-31", "storedIsBSet": True,
            "aCreated": False, "aGotBSet": True, "bAttemptStatus": 200,
            "olderClockCreated": False, "olderClockGotBSet": True, "olderClockAiCalls": 0,
            "storedAfterOlderClock": True,
        })

    def test_q7_ai_expression_saves_to_vocab_and_reports_duplicate(self) -> None:
        """[Q7] AI 문제의 표현 · 뜻 · 예문으로 단어장 추가 — 처음 담고, 다시 누르면 이미 있음."""
        self.assertEqual(self.out["aiOk"]["save1"]["status"], 200)
        self.assertFalse(self.out["aiOk"]["save1"]["body"]["duplicated"])
        self.assertTrue(self.out["aiOk"]["save2"]["body"]["duplicated"])

    def test_corrupt_quiz_storage_is_treated_as_no_set(self) -> None:
        """망가진 퀴즈 저장 값은 세트 없음으로 보고 새로 만든다."""
        self.assertIsNone(self.out["corrupt"]["getRes"]["body"]["quiz"])
        self.assertTrue(self.out["corrupt"]["postRes"]["body"]["created"])


if __name__ == "__main__":
    unittest.main()
