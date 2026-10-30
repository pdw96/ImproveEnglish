"""조각 8(review-quiz) 자동 시험 — PR 1 몫: 설계 ② 보장 Q1(내 기록 부분) · Q2 ~ Q5 · Q10.

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
import shutil
import subprocess
import tempfile
import unittest

import src.gemini as gemini_module
from src.app import FeedbackApp
from src.feedback_types import FeedbackRequest, FeedbackResponse, ValidationError
from src.history_store import HistoryStore
from src.quiz_service import build_daily_quiz, build_expression_pool, make_mine_questions
from src.quiz_store import QuizStore
from src.quiz_types import (
    CHOICE_COUNT,
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
        status, r1 = self.attempt({"date": quiz["date"], "answers": wrong})
        self.assertEqual(status, 200)
        self.assertEqual((r1["score"], r1["correctCount"], r1["total"]), (90, 9, 10))
        self.assertFalse(r1["results"][0]["correct"])
        self.assertEqual(r1["results"][0]["answer"], quiz["questions"][0]["choices"][right[0]])
        self.assertEqual(r1["results"][0]["explanation"], quiz["questions"][0]["explanation"])
        status, r2 = self.attempt({"date": quiz["date"], "answers": right})
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
            "badDate": {"date": "2026/10/30", "answers": right},
            "impossibleDate": {"date": "2026-02-30", "answers": right},
            "noAnswers": {"date": quiz["date"], "answers": []},
            "answersNotList": {"date": quiz["date"], "answers": "0123"},
            "tooFew": {"date": quiz["date"], "answers": right[:9]},
            "tooMany": {"date": quiz["date"], "answers": [*right, 0]},
            "outOfRange": {"date": quiz["date"], "answers": [4] * 10},
            "negative": {"date": quiz["date"], "answers": [-1] * 10},
            "notInt": {"date": quiz["date"], "answers": [1.5] * 10},
            "boolean": {"date": quiz["date"], "answers": [True] * 10},
            "otherDate": {"date": "2026-10-29", "answers": right},
        }
        before = self.quiz_file()
        for name, body in bad.items():
            with self.subTest(name=name):
                status, data = self.attempt(body)
                self.assertEqual(status, 400)
                self.assertIn("error", data)
                self.assertEqual(self.quiz_file(), before)

    def test_q5_rollover_keep_original_date(self) -> None:
        """[Q5] 날짜 넘김 ① — 세트 A 를 만든 뒤 날짜를 넘겨 A 의 답안을 내면 A 의 날짜로 기록된다."""
        self.seed(11, True)
        a = self.start(DAY1)["quiz"]
        status, r = self.attempt({"date": a["date"], "answers": [q["answerIndex"] for q in a["questions"]]})
        self.assertEqual(status, 200)
        self.assertEqual(r["scoreLine"]["date"], DAY1.isoformat())
        self.assertIsNone(self.app.handle_get_quiz_today(today=DAY2)[1]["score"])

    def test_q5_rollover_after_new_set_rejects_old_answers(self) -> None:
        """[Q5] 날짜 넘김 ② — 다음 날 세트 B 가 먼저 만들어지면 A 의 답안은 거절되고 저장 내용이 그대로다."""
        self.seed(11, True)
        a = self.start(DAY1)["quiz"]
        self.start(DAY2)
        before = self.quiz_file()
        status, data = self.attempt({"date": a["date"], "answers": [q["answerIndex"] for q in a["questions"]]})
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
        for bad in bads:
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    QuizQuestion.from_dict(bad)

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
        """[Q5] 조건 밖 답안 13꼴 — 400 이고 기기 저장소가 거절 전과 같다."""
        rejects = self.out["full"]["rejects"]
        self.assertEqual(len(rejects), 13)
        for name, r in rejects.items():
            with self.subTest(name=name):
                self.assertEqual(r["status"], 400)
                self.assertIn("error", r["body"])
                self.assertTrue(r["unchanged"])

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

    def test_corrupt_quiz_storage_is_treated_as_no_set(self) -> None:
        """망가진 퀴즈 저장 값은 세트 없음으로 보고 새로 만든다."""
        self.assertIsNone(self.out["corrupt"]["getRes"]["body"]["quiz"])
        self.assertTrue(self.out["corrupt"]["postRes"]["body"]["created"])


if __name__ == "__main__":
    unittest.main()
