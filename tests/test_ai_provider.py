"""조각 9(ai-provider-choice) 자동 시험.

- PC 서버 모드(PR 1): [P1] 고르기 · [P2] 고른 회사 하나만 · [P3] 같은 모양 · [P4] 실패하면 지금처럼 · [P7] 키 안전 ·
  [P8] 로컬 서버는 자기 화면만 · [P9] 앵커볼트 그대로.
- 폰 앱 금고와 고르기(PR 2): [P1] 폰 저장 · [P5] 금고 하나 · [P6] 옛 Gemini 키 그대로 · [P7] 백업 · 화면에 가린 키 —
  `tests/provider_harness.mjs` 가 Node 로 엔진을 실제로 돌린 결과를 판정한다. Node 가 없으면 건너뛰고 이유를 남긴다.

모든 시험은 가짜 전송 함수 · 가짜 저장소로 돈다 — 실제 회사로 요청을 보내지 않고, 키도 가짜다.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

import src.ai_provider as ai_provider
import src.gemini as gemini_module
import src.quiz_ai as quiz_ai
from src.app import FOREIGN_ORIGIN_MESSAGE, FeedbackApp, create_http_server
from src.feedback_types import FeedbackRequest
from src.history_store import HistoryStore
from src.quiz_ai import AiQuestionsResult
from src.quiz_service import build_expression_pool
from src.quiz_store import QuizStore
from src.routine_store import RoutineStore
from src.vocab_store import VocabStore

KEYS = {
    "gemini": "TEST-ONLY-fake-gemini-key-0001",
    "openai": "TEST-ONLY-fake-openai-key-0002",
    "anthropic": "TEST-ONLY-fake-anthropic-key-0003",
}
HOSTS = {
    "gemini": "https://generativelanguage.googleapis.com/",
    "openai": "https://api.openai.com/",
    "anthropic": "https://api.anthropic.com/",
}
KEY_HEADERS = {"gemini": "x-goog-api-key", "openai": "Authorization", "anthropic": "x-api-key"}

# 이 조각 전 커밋(1cac33f)의 첨삭 · 퀴즈 지시문 · 스키마 상수 지문 — [P9] 글자까지 같은지
ANCHOR_SHA256 = {
    "SYSTEM_INSTRUCTION": "53b58c421c3bf2f11d3c6ddae66c5d4cf8211194683ecf5827904600cb08991b",
    "RESPONSE_SCHEMA": "722a1717b59ca37835ccd8bf873068d029a42c278248d5a4b7c54da5f119c122",
    "QUIZ_SYSTEM_INSTRUCTION": "887f3044beed4b07bca6ac38e0224aa96c886eeda3481094573a786b0bea1655",
    "QUIZ_RESPONSE_SCHEMA": "3d6b768e01222af39478da2da77495833f57081a8f4244a0d41309cb18040e52",
}

FEEDBACK = {
    "corrected": "I'd like to get off work early today.",
    "explanation": "'퇴근하다'는 'get off work' 로 씁니다.",
    "alternatives": [
        {"expression": "I'm hoping to leave work a bit early today.", "nuance": "부드럽게 말할 때."},
        {"expression": "I want to clock out early today.", "nuance": "캐주얼하게."},
    ],
    "keyExpressions": [
        {"expression": "get off work", "meaning": "퇴근하다", "example": "What time do you get off work?"}
    ],
}


def env_for(provider: str | None, **keys: str) -> dict[str, str]:
    """고른 회사와 키를 정한 환경 — 정하지 않은 회사의 키는 비운다."""
    env = {"AI_PROVIDER": provider or "", "DOTENV_AUTORELOAD": ""}
    for name, env_name in ai_provider.KEY_ENV_NAMES.items():
        env[env_name] = keys.get(name, "")
    return env


def reply(provider: str, payload: object) -> dict:
    """회사 응답 꼴 — ③ 의 꺼내는 자리에 JSON 글을 넣는다."""
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    if provider == "gemini":
        return {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    if provider == "openai":
        return {"choices": [{"message": {"role": "assistant", "content": text, "refusal": None}}]}
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": text}],
    }


class Recorder:
    """가짜 전송 — 받은 주소 · 머리글 · 본문을 남기고, 정한 응답(또는 오류)을 차례로 돌려준다."""

    def __init__(self, *answers: object) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, dict[str, str], dict]] = []

    def __call__(self, url: str, headers: dict[str, str], body: bytes) -> dict:
        self.calls.append((url, dict(headers), json.loads(body)))
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, BaseException):
            raise answer
        return answer


def http_error(code: int, extra: str = "") -> ai_provider.AiServiceError:
    return ai_provider.AiServiceError(f"AI 서버 요청이 실패했습니다(HTTP {code}){extra}. API 키 또는 사용 한도를 확인해 주세요.")


REQ = FeedbackRequest(text="I want to 퇴근하다 early today", input_mode="text")


class TestP1Choice(unittest.TestCase):
    def test_p1_closed_list_and_default(self) -> None:
        """[P1] · ③ — 목록 셋은 공백 · 대소문자를 맞춰 받고, 비었거나 목록 밖이면 gemini."""
        cases = {
            "": "gemini",
            "gemini": "gemini",
            " OpenAI ": "openai",
            "ANTHROPIC": "anthropic",
            "claude": "gemini",
            "chatgpt": "gemini",
            "gpt": "gemini",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {"AI_PROVIDER": raw, "DOTENV_AUTORELOAD": ""}):
                self.assertEqual(ai_provider.get_provider(), expected)
        with mock.patch.dict(os.environ, {"DOTENV_AUTORELOAD": ""}):
            os.environ.pop("AI_PROVIDER", None)
            self.assertEqual(ai_provider.get_provider(), "gemini")


class TestP2P3FeedbackThroughApp(unittest.TestCase):
    """첨삭을 FeedbackApp 의 실제 길로 — 기본 전송(gemini._default_http_transport)만 가짜로 바꾼다."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.history_path = pathlib.Path(self.tmp.name) / "history.json"
        self.app = FeedbackApp(store=HistoryStore(self.history_path))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def post(self) -> tuple[int, dict]:
        body = json.dumps({"text": REQ.text, "inputMode": "text"}, ensure_ascii=False).encode("utf-8")
        return self.app.handle_post_feedback(body)

    def history_text(self) -> str:
        return self.history_path.read_text(encoding="utf-8") if self.history_path.exists() else ""

    def test_p2_p3_each_provider_only_its_host_and_same_record_shape(self) -> None:
        """[P2] 고른 회사 주소 하나만 부른다 · [P3] 첨삭 결과와 저장된 기록 모양(칸 이름)이 회사와 상관없이 같다."""
        shapes = {}
        for provider in ai_provider.PROVIDERS:
            with self.subTest(provider=provider):
                rec = Recorder(reply(provider, FEEDBACK))
                with mock.patch.dict(os.environ, env_for(provider, **KEYS)), mock.patch.object(
                    gemini_module, "_default_http_transport", lambda u, h, b, api_key_to_mask="": rec(u, h, b)
                ):
                    status, record = self.post()
                self.assertEqual(status, 200)
                self.assertEqual(len(rec.calls), 1)
                self.assertTrue(rec.calls[0][0].startswith(HOSTS[provider]))
                self.assertEqual(record["feedback"], FEEDBACK)
                saved = json.loads(self.history_text())[0]
                self.assertEqual(saved["id"], record["id"])
                shapes[provider] = (sorted(record), sorted(record["feedback"]), sorted(saved))
        self.assertEqual(shapes["openai"], shapes["gemini"])
        self.assertEqual(shapes["anthropic"], shapes["gemini"])

    def test_p3_bad_shape_is_rejected_and_nothing_saved(self) -> None:
        """[P3] 거절 — 응답 칸이 모자라면(대체 표현 1개) 어느 회사든 502 이고 기록이 그대로다."""
        bad = dict(FEEDBACK, alternatives=FEEDBACK["alternatives"][:1])
        for provider in ai_provider.PROVIDERS:
            with self.subTest(provider=provider):
                before = self.history_text()
                rec = Recorder(reply(provider, bad))
                with mock.patch.dict(os.environ, env_for(provider, **KEYS)), mock.patch.object(
                    gemini_module, "_default_http_transport", lambda u, h, b, api_key_to_mask="": rec(u, h, b)
                ):
                    status, data = self.post()
                self.assertEqual(status, 502)
                self.assertIn("error", data)
                self.assertEqual(self.history_text(), before)


class TestP2ModelCandidates(unittest.TestCase):
    def test_p2_next_model_only_on_404_inside_same_provider(self) -> None:
        """[P2] 404 면 그 회사의 다음 모델 후보로, 다른 실패(500)면 바로 멈춘다 — 다른 회사 주소는 부르지 않는다."""
        rec = Recorder(http_error(404), reply("openai", FEEDBACK))
        with mock.patch.dict(os.environ, env_for("openai", **KEYS)):
            result = ai_provider.generate_feedback(REQ, transport=rec)
        self.assertEqual(result.corrected, FEEDBACK["corrected"])
        self.assertEqual([c[2]["model"] for c in rec.calls], list(ai_provider.MODEL_CANDIDATES["openai"]))
        self.assertTrue(all(c[0] == ai_provider.OPENAI_ENDPOINT for c in rec.calls))

        rec = Recorder(http_error(500), reply("openai", FEEDBACK))
        with mock.patch.dict(os.environ, env_for("openai", **KEYS)):
            with self.assertRaises(ai_provider.AiServiceError):
                ai_provider.generate_feedback(REQ, transport=rec)
        self.assertEqual(len(rec.calls), 1)

        rec = Recorder(http_error(404))
        with mock.patch.dict(os.environ, env_for("gemini", **KEYS)):
            with self.assertRaises(ai_provider.AiServiceError):
                ai_provider.generate_feedback(REQ, transport=rec)
        self.assertEqual(len(rec.calls), len(gemini_module.FALLBACK_MODELS))
        self.assertTrue(all(c[0].startswith(HOSTS["gemini"]) for c in rec.calls))


class TestP3ResponseForms(unittest.TestCase):
    """③ 회사 응답에서 꺼내는 자리 — 꼴마다 하나."""

    def test_extract_each_provider_success_form(self) -> None:
        for provider in ai_provider.PROVIDERS:
            with self.subTest(provider=provider):
                self.assertEqual(ai_provider.extract_text(provider, reply(provider, "{}")), "{}")

    def test_extract_failure_forms(self) -> None:
        cases = {
            "gemini-empty": ("gemini", {"candidates": []}),
            "gemini-no-text": ("gemini", {"candidates": [{"content": {"parts": [{}]}}]}),
            "openai-refusal": ("openai", {"choices": [{"message": {"content": "{}", "refusal": "I can't help with that."}}]}),
            "openai-empty": ("openai", {"choices": []}),
            "openai-null-content": ("openai", {"choices": [{"message": {"content": None, "refusal": None}}]}),
            "anthropic-refusal": ("anthropic", {"stop_reason": "refusal", "content": [{"type": "text", "text": "{}"}]}),
            "anthropic-max-tokens": ("anthropic", {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "{"}]}),
            "anthropic-no-text-block": ("anthropic", {"stop_reason": "end_turn", "content": [{"type": "thinking", "thinking": ""}]}),
            "not-a-dict": ("openai", ["x"]),
        }
        for name, (provider, raw) in cases.items():
            with self.subTest(name=name), self.assertRaises(ai_provider.AiServiceError):
                ai_provider.extract_text(provider, raw)

    def test_schema_translation_keeps_fields_and_drops_count_limits(self) -> None:
        """JSON 스키마 옮기기 — 칸 · 필수 · 설명은 그대로, 타입은 소문자, 모든 객체에 additionalProperties: false, 개수 제한은 뺀다."""
        for schema in (gemini_module.RESPONSE_SCHEMA, quiz_ai.QUIZ_RESPONSE_SCHEMA):
            out = ai_provider.to_json_schema(schema)
            dumped = json.dumps(out)
            self.assertNotIn("minItems", dumped)
            self.assertNotIn("maxItems", dumped)

            def walk(src: dict, dst: dict) -> None:
                self.assertEqual(dst["type"], src["type"].lower())
                if src["type"] == "OBJECT":
                    self.assertIs(dst["additionalProperties"], False)
                    self.assertEqual(dst["required"], src["required"])
                    self.assertEqual(sorted(dst["properties"]), sorted(src["properties"]))
                    for name in src["properties"]:
                        walk(src["properties"][name], dst["properties"][name])
                if src["type"] == "ARRAY":
                    walk(src["items"], dst["items"])
                if "description" in src:
                    self.assertEqual(dst["description"], src["description"])

            walk(schema, out)
        self.assertIn("minItems", json.dumps(gemini_module.RESPONSE_SCHEMA))  # 원본은 그대로


class TestP4Failures(unittest.TestCase):
    def test_p4_credit_or_limit_goes_to_local_coach_per_provider(self) -> None:
        """[P4] PC 첨삭 — 회사마다 크레딧 소진 · 한도 초과 상태면 내장 스마트 코치, 그 밖(500 · 529 · OpenAI 402)은 오류."""
        coach = gemini_module._build_local_coach_feedback(REQ)
        for provider, codes in ai_provider.CREDIT_OR_LIMIT_STATUS.items():
            for code in sorted(codes):
                with self.subTest(provider=provider, code=code), mock.patch.dict(os.environ, env_for(provider, **KEYS)):
                    result = ai_provider.generate_feedback(REQ, transport=Recorder(http_error(code)))
                    self.assertEqual(result, coach)
        for provider, code in (("gemini", 500), ("openai", 402), ("anthropic", 529), ("anthropic", 401)):
            with self.subTest(provider=provider, code=code), mock.patch.dict(os.environ, env_for(provider, **KEYS)):
                with self.assertRaises(ai_provider.AiServiceError):
                    ai_provider.generate_feedback(REQ, transport=Recorder(http_error(code)))

    def test_p4_final_failure_status_decides_after_404(self) -> None:
        """[P4] 앞 모델이 404 이고 다음 모델이 크레딧 · 한도면 내장 코치 — 묶은 오류의 첫 상태(404)가 아니라 마지막 실패로 판정한다(PR 1 리뷰 1회차)."""
        coach = gemini_module._build_local_coach_feedback(REQ)
        for provider, last in (("gemini", 429), ("gemini", 402), ("openai", 429)):
            with self.subTest(provider=provider, last=last), mock.patch.dict(os.environ, env_for(provider, **KEYS)):
                rec = Recorder(http_error(404), http_error(last))
                self.assertEqual(ai_provider.generate_feedback(REQ, transport=rec), coach)
                self.assertEqual(len(rec.calls), 2)
        with mock.patch.dict(os.environ, env_for("gemini", **KEYS)):
            with self.assertRaises(ai_provider.AiServiceError):
                ai_provider.generate_feedback(REQ, transport=Recorder(http_error(404), http_error(500)))

    def test_p4_auto_reload_mode_keeps_error_handling(self) -> None:
        """[P4] 실제 PC 서버처럼 DOTENV_AUTORELOAD=1 로 돌 때도 — 키 없음은 502 오류 안내(저장 없음), 크레딧 · 한도는 내장 코치로 저장된다
        (PR 1 리뷰 1회차: 모듈을 다시 읽어 오류 클래스가 어긋나던 것)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        history_path = pathlib.Path(tmp.name) / "history.json"
        app = FeedbackApp(store=HistoryStore(history_path))
        body = json.dumps({"text": REQ.text, "inputMode": "text"}, ensure_ascii=False).encode("utf-8")
        coach = gemini_module._build_local_coach_feedback(REQ)

        def limit(url, headers, payload, api_key_to_mask=""):
            raise http_error(429)

        no_key = env_for("openai", gemini=KEYS["gemini"])
        no_key["DOTENV_AUTORELOAD"] = "1"
        with mock.patch.dict(os.environ, no_key), mock.patch.object(gemini_module, "load_dotenv_file", lambda **kw: None):
            for _ in range(2):  # 두 번째 요청도 같다
                status, data = app.handle_post_feedback(body)
                self.assertEqual(status, 502)
                self.assertIn("OPENAI_API_KEY", data["error"])
        self.assertFalse(history_path.exists())

        limited = env_for("anthropic", **KEYS)
        limited["DOTENV_AUTORELOAD"] = "1"
        with mock.patch.dict(os.environ, limited), mock.patch.object(
            gemini_module, "load_dotenv_file", lambda **kw: None
        ), mock.patch.object(gemini_module, "_default_http_transport", limit):
            for _ in range(2):
                status, record = app.handle_post_feedback(body)
                self.assertEqual(status, 200)
                self.assertEqual(record["feedback"], coach.to_dict())

    def test_p4_no_key_for_chosen_provider_names_its_env_and_never_calls(self) -> None:
        """[P4] 고른 회사 키가 없으면(다른 회사 키가 있어도) 부르지 않고 그 회사 환경변수 이름을 담은 안내 — 자리표시 값도 키 없음."""

        def must_not_call(url, headers, body):
            raise AssertionError("키가 없으면 부르지 않는다")

        for provider in ("openai", "anthropic"):
            others = {k: v for k, v in KEYS.items() if k != provider}
            env_name = ai_provider.KEY_ENV_NAMES[provider]
            for placeholder in ("", f"your_{provider}_api_key_here"):
                env = env_for(provider, **others)
                env[env_name] = placeholder
                with self.subTest(provider=provider, placeholder=placeholder), mock.patch.dict(os.environ, env):
                    with self.assertRaises(ai_provider.AiServiceError) as ctx:
                        ai_provider.generate_feedback(REQ, transport=must_not_call)
                    self.assertIn(env_name, str(ctx.exception))
                    for key in KEYS.values():
                        self.assertNotIn(key, str(ctx.exception))

    def test_p4_quiz_uses_chosen_provider_and_falls_back_to_my_records(self) -> None:
        """[P4] 퀴즈 — 고른 회사로 부르고, 키 없음이면 no_key(부르지 않음), 실패 · 꼴 밖 응답이면 failed."""
        pool = build_expression_pool([], _history_records(), today=None)
        item = {
            "question": "I really want to ____ this habit.",
            "choices": ["kick", "take after", "look into", "run out of"],
            "answerIndex": 0,
            "explanation": "정답 표현이 문장의 뜻에 맞는다.",
            "expression": "kick",
            "meaning": "끊다",
            "example": "I really want to kick this habit.",
        }
        for provider in ai_provider.PROVIDERS:
            with self.subTest(provider=provider):
                rec = Recorder(reply(provider, {"questions": [item]}))
                with mock.patch.dict(os.environ, env_for(provider, **KEYS)):
                    ok = quiz_ai.generate_ai_questions(pool, [], transport=rec)
                    failed = quiz_ai.generate_ai_questions(pool, [], transport=Recorder(http_error(429)))
                    garbled = quiz_ai.generate_ai_questions(pool, [], transport=Recorder(reply(provider, "not json")))
                self.assertEqual((ok.status, len(ok.questions)), ("ok", 1))
                self.assertTrue(all(c[0].startswith(HOSTS[provider]) for c in rec.calls))
                self.assertEqual((failed.status, failed.questions), ("failed", []))
                self.assertEqual((garbled.status, garbled.questions), ("failed", []))
                with mock.patch.dict(os.environ, env_for(provider)):
                    self.assertEqual(quiz_ai.generate_ai_questions(pool, [], transport=_must_not_call).status, "no_key")


def _must_not_call(url, headers, body):
    raise AssertionError("키가 없으면 부르지 않는다")


def _history_records():
    from src.feedback_types import FeedbackRecord, FeedbackResponse

    expressions = ["kick the habit", "take after", "look into", "run out of", "put up with"]
    return [
        FeedbackRecord.create(
            REQ,
            FeedbackResponse.from_dict(
                dict(
                    FEEDBACK,
                    keyExpressions=[{"expression": e, "meaning": f"뜻 {i}", "example": f"I {e} today."}],
                )
            ),
        )
        for i, e in enumerate(expressions)
    ]


class TestP7KeySafety(unittest.TestCase):
    def test_p7_key_only_in_its_header_never_in_url_or_body(self) -> None:
        """[P7] 회사마다 키는 정한 머리글에만 — 주소 · 본문에 없다. 첨삭 · 퀴즈 둘 다."""
        pool = build_expression_pool([], _history_records(), today=None)
        for provider in ai_provider.PROVIDERS:
            key = KEYS[provider]
            with self.subTest(provider=provider), mock.patch.dict(os.environ, env_for(provider, **KEYS)):
                fb = Recorder(reply(provider, FEEDBACK))
                ai_provider.generate_feedback(REQ, transport=fb)
                qz = Recorder(reply(provider, {"questions": []}))
                quiz_ai.generate_ai_questions(pool, [], transport=qz)
                for url, headers, body in fb.calls + qz.calls:
                    self.assertNotIn(key, url)
                    self.assertNotIn(key, json.dumps(body, ensure_ascii=False))
                    expected = f"Bearer {key}" if provider == "openai" else key
                    self.assertEqual(headers[KEY_HEADERS[provider]], expected)
                    for other in (k for p, k in KEYS.items() if p != provider):
                        self.assertNotIn(other, json.dumps(headers))

    def test_p7_key_echoed_in_error_is_masked(self) -> None:
        """[P7] 회사 오류 글에 키가 섞여 와도 오류 안내에는 가려진다."""
        for provider in ai_provider.PROVIDERS:
            key = KEYS[provider]
            with self.subTest(provider=provider), mock.patch.dict(os.environ, env_for(provider, **KEYS)):
                with self.assertRaises(ai_provider.AiServiceError) as ctx:
                    ai_provider.generate_feedback(REQ, transport=Recorder(http_error(500, f" (bad key {key})")))
                self.assertNotIn(key, str(ctx.exception))
                self.assertIn("[REDACTED]", str(ctx.exception))


class TestP8Origin(unittest.TestCase):
    """[P8] 실제 서버를 띄워 Origin 을 바꿔 보낸다."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.ai_calls = 0
        self.quiz_ai_calls = 0

        def fake_ai(req):
            self.ai_calls += 1
            from src.feedback_types import FeedbackResponse

            return FeedbackResponse.from_dict(FEEDBACK)

        def fake_quiz_ai(pool, records):
            self.quiz_ai_calls += 1
            return AiQuestionsResult([], "no_key")

        self.base = base
        (base / "vocab.json").write_text(
            json.dumps(
                [
                    {
                        "id": "v-1",
                        "expression": "get off work",
                        "meaning": "퇴근하다",
                        "example": "I get off work at six.",
                        "createdAt": "2026-10-29T01:00:00Z",
                        "box": 1,
                        "nextReviewDate": "2026-10-01",
                        "reviewCount": 0,
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        app = FeedbackApp(
            store=HistoryStore(base / "history.json"),
            vocab_store=VocabStore(base / "vocab.json"),
            routine_store=RoutineStore(base / "routine.json"),
            quiz_store=QuizStore(base / "quiz.json"),
            ai_fn=fake_ai,
            quiz_ai_fn=fake_quiz_ai,
        )
        os.environ["QUIET_SERVER_LOG"] = "1"
        self.server = create_http_server(host="127.0.0.1", port=0, app=app)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def snapshot(self) -> dict[str, str]:
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(self.base.iterdir())}

    def request(self, method: str, path: str, origin: str | None, body: dict | None = None) -> tuple[int, dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if origin is not None:
            headers["Origin"] = origin
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        conn.request(method, path, body=payload, headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        conn.close()
        return res.status, data

    def test_p8_foreign_origin_rejected_without_saving_or_calling_ai(self) -> None:
        """[P8] 거절 — 다른 사이트 · null · 다른 포트의 Origin 은 403, 저장 파일이 그대로이고 AI 를 부르지 않는다."""
        feedback = {"text": "I want to 퇴근하다 early", "inputMode": "text"}
        foreign = ["http://evil.example", "null", f"http://127.0.0.1:{self.port + 1}", f"https://127.0.0.1:{self.port}"]
        before = self.snapshot()
        for origin in foreign:
            for method, path, body in (
                ("POST", "/api/feedback", feedback),
                ("POST", "/api/quiz/today", {}),
                ("POST", "/api/vocab", {"expression": "x", "meaning": "y"}),
                ("DELETE", "/api/vocab/v-1", None),
            ):
                with self.subTest(origin=origin, path=path, method=method):
                    status, data = self.request(method, path, origin, body)
                    self.assertEqual(status, 403)
                    self.assertEqual(data, {"error": FOREIGN_ORIGIN_MESSAGE})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.ai_calls, self.quiz_ai_calls), (0, 0))

    def test_p8_own_origin_and_no_origin_still_work(self) -> None:
        """[P8] 성공 — 자기 주소 Origin 과 Origin 없는 요청은 지금처럼 받는다(첨삭 저장 · AI 호출)."""
        feedback = {"text": "I want to 퇴근하다 early", "inputMode": "text"}
        status, record = self.request("POST", "/api/feedback", f"http://127.0.0.1:{self.port}", feedback)
        self.assertEqual(status, 200)
        status2, _ = self.request("POST", "/api/feedback", None, feedback)
        self.assertEqual(status2, 200)
        self.assertEqual(self.ai_calls, 2)
        saved = json.loads((self.base / "history.json").read_text(encoding="utf-8"))
        self.assertIn(record["id"], [r["id"] for r in saved])
        status3, _ = self.request("GET", "/api/history", "http://evil.example")
        self.assertEqual(status3, 200)  # 읽기는 막지 않는다 — 브라우저가 다른 사이트에 응답을 보여 주지 않는다


class TestP9Anchor(unittest.TestCase):
    def test_p9_constants_unchanged_since_before_slice(self) -> None:
        """[P9] 첨삭 · 퀴즈 지시문 · 스키마 상수가 이 조각 전 커밋과 글자까지 같다."""
        values = {
            "SYSTEM_INSTRUCTION": gemini_module.SYSTEM_INSTRUCTION,
            "RESPONSE_SCHEMA": gemini_module.RESPONSE_SCHEMA,
            "QUIZ_SYSTEM_INSTRUCTION": quiz_ai.QUIZ_SYSTEM_INSTRUCTION,
            "QUIZ_RESPONSE_SCHEMA": quiz_ai.QUIZ_RESPONSE_SCHEMA,
        }
        for name, value in values.items():
            digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            self.assertEqual(digest, ANCHOR_SHA256[name], name)

    def test_p9_gemini_request_body_is_same_as_before(self) -> None:
        """[P9] Gemini 로 보내는 첨삭 · 퀴즈 본문이 조각 전의 본문 함수(build_gemini_payload · build_quiz_ai_payload)와 같다."""
        rec = Recorder(reply("gemini", FEEDBACK))
        with mock.patch.dict(os.environ, env_for("gemini", **KEYS)):
            ai_provider.generate_feedback(REQ, transport=rec)
        self.assertEqual(rec.calls[0][2], gemini_module.build_gemini_payload(REQ))

        records = _history_records()
        pool = build_expression_pool([], records, today=None)
        rec = Recorder(reply("gemini", {"questions": []}))
        with mock.patch.dict(os.environ, env_for("gemini", **KEYS)):
            quiz_ai.generate_ai_questions(pool, records, transport=rec)
        self.assertEqual(rec.calls[0][2], quiz_ai.build_quiz_ai_payload(pool, records))

    def test_p9_other_providers_carry_same_instruction_and_user_text(self) -> None:
        """[P9] OpenAI · Anthropic 본문에도 같은 지시문 · 사용자 글이 그대로 실리고, 온도는 보내지 않는다."""
        gemini_body = gemini_module.build_gemini_payload(REQ)
        user_text = gemini_body["contents"][0]["parts"][0]["text"]
        for provider in ("openai", "anthropic"):
            rec = Recorder(reply(provider, FEEDBACK))
            with self.subTest(provider=provider), mock.patch.dict(os.environ, env_for(provider, **KEYS)):
                ai_provider.generate_feedback(REQ, transport=rec)
                body = rec.calls[0][2]
                self.assertNotIn("temperature", json.dumps(body))
                if provider == "openai":
                    self.assertEqual(body["messages"][0], {"role": "system", "content": gemini_module.SYSTEM_INSTRUCTION})
                    self.assertEqual(body["messages"][1], {"role": "user", "content": user_text})
                    self.assertEqual(
                        body["response_format"]["json_schema"]["schema"],
                        ai_provider.to_json_schema(gemini_module.RESPONSE_SCHEMA),
                    )
                else:
                    self.assertEqual(body["system"], gemini_module.SYSTEM_INSTRUCTION)
                    self.assertEqual(body["messages"], [{"role": "user", "content": user_text}])
                    self.assertEqual(
                        body["output_config"]["format"]["schema"],
                        ai_provider.to_json_schema(gemini_module.RESPONSE_SCHEMA),
                    )


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROVIDER_HARNESS = REPO_ROOT / "tests" / "provider_harness.mjs"
NODE = shutil.which("node")
VAULT_PARTS = ("", "_salt", "_iv", "_encrypted")


def vault_names(provider: str) -> set[str]:
    return {f"ie_{provider}_api_key{part}" for part in VAULT_PARTS}


def locked_names(*providers: str) -> set[str]:
    return {f"ie_{p}_api_key{part}" for p in providers for part in ("_salt", "_iv", "_encrypted")}


def session_names(*providers: str) -> set[str]:
    return {f"ie_{p}_api_key_session" for p in providers}


@unittest.skipIf(NODE is None, "Node 가 없어 폰 앱 엔진을 실제로 돌리는 시험을 건너뜁니다 (Node 18 이상 필요)")
class TestPhoneVaultAndChoice(unittest.TestCase):
    """PR 2 — 폰 앱 엔진의 세 키 금고와 지금 쓸 AI."""

    out: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        proc = subprocess.run(
            [NODE, str(PROVIDER_HARNESS)], cwd=REPO_ROOT, capture_output=True, text=True, timeout=180, check=False
        )
        if proc.returncode != 0:
            raise AssertionError(f"provider_harness.mjs 실행 실패: {proc.stderr}")
        cls.out = json.loads(proc.stdout)

    def keys(self) -> dict[str, str]:
        return self.out["KEYS"]

    def assert_no_plain_key(self, local: dict) -> None:
        dumped = json.dumps(local, ensure_ascii=False)
        for key in self.keys().values():
            self.assertNotIn(key, dumped)

    # ── P1 ──
    def test_p1_phone_default_set_and_survives_reopen(self) -> None:
        """[P1] 폰 — 고른 적 없으면 gemini, 고르면 ie_ai_provider 에 남아 창을 다시 열어도 같다. 목록 밖 값은 저장하지 않는다."""
        self.assertEqual(self.out["p1Default"]["provider"], "gemini")
        self.assertEqual(self.out["p1Default"]["local"], {})
        p1 = self.out["p1Set"]
        self.assertTrue(p1["okSet"])
        self.assertFalse(p1["badSet"])
        self.assertEqual(p1["after"]["local"], {"ie_ai_provider": "anthropic"})
        self.assertEqual(p1["reopened"]["provider"], "anthropic")

    def test_p1_phone_stored_value_closed_list(self) -> None:
        """[P1] · ③ 폰 — 저장된 값은 공백 · 대소문자를 맞춰 읽고, 목록 밖이면 gemini."""
        self.assertEqual(
            self.out["p1Stored"],
            {"claude": "gemini", "": "gemini", " OpenAI ": "openai", "ANTHROPIC": "anthropic", "gpt": "gemini"},
        )

    # ── P5 ──
    def test_p5_save_two_with_pin_locks_both_and_ignores_blank_slot(self) -> None:
        """[P5] 성공 — 두 칸을 비밀번호와 함께 저장하면 둘 다 암호문 · 소금 · 초기값만 남고, 빈 칸 회사는 건드리지 않는다."""
        r = self.out["p5SaveTwo"]
        self.assertTrue(r["ok"])
        self.assertEqual(set(r["local"]), locked_names("gemini", "openai"))
        self.assertEqual(set(r["session"]), session_names("gemini", "openai"))
        self.assert_no_plain_key(r["local"])
        self.assertEqual(r["keyStates"], {"gemini": "ready", "openai": "ready", "anthropic": "none"})

    def test_p5_one_unlock_opens_all_and_wrong_pin_opens_none(self) -> None:
        """[P5] 다시 열면 둘 다 잠김, 틀린 비밀번호는 하나도 풀지 않고(저장 그대로), 맞는 비밀번호 한 번에 모두 풀린다."""
        self.assertEqual(self.out["p5Reopened"]["keyStates"], {"gemini": "locked", "openai": "locked", "anthropic": "none"})
        wrong = self.out["p5WrongUnlock"]
        self.assertFalse(wrong["ok"])
        self.assertEqual(wrong["local"], self.out["p5Reopened"]["local"])
        self.assertEqual(wrong["session"], {})
        right = self.out["p5RightUnlock"]
        self.assertTrue(right["ok"])
        self.assertEqual(right["keyStates"], {"gemini": "ready", "openai": "ready", "anthropic": "none"})
        self.assertEqual(right["session"], {f"ie_{p}_api_key_session": self.keys()[p] for p in ("gemini", "openai")})
        self.assertEqual(right["local"], self.out["p5Reopened"]["local"])

    def test_p5_rejections_leave_everything_as_before(self) -> None:
        """[P5] 거절 — 잠긴 키가 남는데 비밀번호 없음 · 틀린 비밀번호 · 남는 잠긴 키가 있는데 하나만 평문으로 바꾸기 ·
        짧은 비밀번호 · 채운 칸 없음은 모두 false 이고 기기 저장 값이 거절 전과 같고 창에 푼 키도 생기지 않는다."""
        for name in ("p5NoPinWithLocked", "p5WrongPinSave", "p5ReplaceOneOfTwoWithoutPin", "p5ShortPin", "p5NothingFilled"):
            with self.subTest(name=name):
                r = self.out[name]
                self.assertFalse(r["ok"])
                self.assertFalse(r["threw"])
                self.assertEqual(r["local"], r["before"])
                self.assertEqual(r["session"], {})

    def test_p5_right_pin_adds_third_key_to_same_vault(self) -> None:
        """[P5] 성공 — 잠긴 금고에 맞는 비밀번호로 새 회사 키를 더하면 셋이 한 금고가 되고, 다시 열어 한 번에 풀린다."""
        r = self.out["p5RightPinSave"]
        self.assertTrue(r["ok"])
        self.assertEqual(set(r["local"]), locked_names("gemini", "openai", "anthropic"))
        self.assert_no_plain_key(r["local"])
        again = self.out["p5ThreeReopenUnlock"]
        self.assertTrue(again["ok"])
        self.assertEqual(again["session"], {f"ie_{p}_api_key_session": k for p, k in self.keys().items()})

    def test_p5_pin_save_also_locks_plain_keys_and_no_pin_keeps_plain(self) -> None:
        """[P5] 통째로 — 평문 Gemini 키가 있는 기기에 비밀번호와 함께 저장하면 Gemini 키도 잠기고(평문 없음),
        비밀번호 없이 저장하면 둘 다 평문이다."""
        locked = self.out["p5LockAlsoPlain"]
        self.assertTrue(locked["ok"])
        self.assertEqual(set(locked["local"]), locked_names("gemini", "openai"))
        self.assert_no_plain_key(locked["local"])
        plain = self.out["p5PlainPlusPlain"]
        self.assertTrue(plain["ok"])
        self.assertEqual(plain["local"], {"ie_gemini_api_key": self.keys()["gemini"], "ie_openai_api_key": self.keys()["openai"]})

    def test_p5_storage_full_rolls_back_all_slots(self) -> None:
        """[P5] 저장 공간이 차서 두 번째 회사 칸을 못 쓰면 예외로 알리고, 먼저 쓴 칸까지 되돌린다(섞인 금고를 남기지 않음)."""
        empty = self.out["p5QuotaRollback"]
        self.assertTrue(empty["threw"])
        self.assertEqual(empty["local"], {})
        self.assertEqual(empty["session"], {})
        vault = self.out["p5QuotaRollbackVault"]
        self.assertTrue(vault["threw"])
        self.assertEqual(vault["local"], vault["before"])

    def test_p5_clear_one_provider_only(self) -> None:
        """[P5] 지우기는 그 회사 키만 — 평문 · 소금 · 초기값 · 암호문 · 창의 푼 키. 다른 회사 키는 그대로."""
        r = self.out["p5ClearOne"]
        self.assertEqual(set(r["local"]), locked_names("gemini"))
        self.assertEqual(set(r["session"]), session_names("gemini"))
        self.assertEqual(r["keyStates"]["openai"], "none")
        self.assertEqual(r["keyStates"]["gemini"], "ready")

    # ── P6 ──
    def test_p6_legacy_gemini_vault_unlocks_without_rewrite(self) -> None:
        """[P6] 조각 api-key-vault 때 만든 Gemini 금고 값(새 엔진과 따로 만든 것)이 그 비밀번호로 풀리고, 저장 값은 옮기거나 다시 쓰지 않는다."""
        r = self.out["p6Legacy"]
        self.assertEqual(r["lockedState"]["keyStates"]["gemini"], "locked")
        self.assertTrue(r["ok"])
        self.assertEqual(r["keyStates"]["gemini"], "ready")
        self.assertEqual(r["local"], r["before"])
        self.assertEqual(r["session"], {"ie_gemini_api_key_session": self.keys()["gemini"]})
        self.assertEqual(self.out["p6LegacyPlain"]["keyStates"]["gemini"], "ready")
        self.assertEqual(self.out["p6LegacyPlain"]["local"], {"ie_gemini_api_key": self.keys()["gemini"]})

    def test_p6_add_new_provider_to_legacy_vault_with_same_pin(self) -> None:
        """[P6] 옛 Gemini 금고에 같은 비밀번호로 ChatGPT 키를 더하면 한 금고가 되고 Gemini 키도 그대로 풀린다."""
        r = self.out["p6LegacyAdd"]
        self.assertTrue(r["ok"])
        self.assertEqual(set(r["local"]), locked_names("gemini", "openai"))
        self.assertEqual(r["keyStates"], {"gemini": "ready", "openai": "ready", "anthropic": "none"})

    # ── P7 ──
    def test_p7_backup_has_no_keys_vault_values_or_choice(self) -> None:
        """[P7] 백업 파일에는 세 회사의 키 · 금고 값 · 지금 쓸 AI 가 없다(하지 않을 일 5)."""
        r = self.out["p7"]
        text = r["backupText"]
        for provider, key in self.keys().items():
            self.assertNotIn(key, text)
            for name in vault_names(provider) | session_names(provider):
                self.assertNotIn(name, text)
            self.assertNotIn(r["local"][f"ie_{provider}_api_key_encrypted"], text)
        self.assertNotIn("ie_ai_provider", text)
        # 백업 칸은 이 조각 전과 같다 — 키 · 고른 AI 칸이 새로 생기지 않는다
        self.assertEqual(sorted(json.loads(text)), ["exportedAt", "history", "quiz", "routine", "version", "vocab"])
        self.assertNotIn('"openai"', text)

    def test_p7_masked_key_on_screen_hides_the_middle(self) -> None:
        """[P7] 화면에 보이는 키는 앞 4 · 뒤 4 글자만 — 가운데는 가린다."""
        masked = self.out["p7"]["masked"]
        for provider, key in self.keys().items():
            self.assertNotIn(key, masked[provider])
            self.assertTrue(masked[provider].startswith(key[:4]))
            self.assertTrue(masked[provider].endswith(key[-4:]))


class TestPhoneSettingsScreen(unittest.TestCase):
    """PR 2 — 설정 탭 화면 코드(`public/index.html` · `public/app.js`)를 읽어 고르기 단추 · 키 칸 셋 · 저장 갈래를 본다."""

    def setUp(self) -> None:
        self.html = (REPO_ROOT / "public" / "index.html").read_text(encoding="utf-8")
        self.app = (REPO_ROOT / "public" / "app.js").read_text(encoding="utf-8")

    def test_three_provider_buttons_and_three_key_inputs(self) -> None:
        for provider in ai_provider.PROVIDERS:
            self.assertIn(f'data-ai-provider="{provider}"', self.html)
            self.assertIn(f'data-key-clear="{provider}"', self.html)
            self.assertIn(f'data-key-state="{provider}"', self.html)
        for input_id in ("settings-apikey-input", "settings-apikey-openai-input", "settings-apikey-anthropic-input"):
            self.assertIn(f'id="{input_id}"', self.html)
        self.assertNotIn('id="apikey-clear-btn"', self.html)

    def test_save_branches_order(self) -> None:
        """금고 풀기(키 칸 없이 비밀번호만) → 빈 입력 안내 → 짧은 비밀번호 → 잠긴 키가 남는데 비밀번호 없음 → 저장 순서."""
        order = [
            "if (!val && engine.isEncrypted() && pin)",
            "저장할 API 키를 한 칸 이상 넣어 주세요",
            "pin.length < engine.MIN_PIN_LENGTH",
            "if (!pin && keepsLockedKey)",
            "saved = await engine.saveApiKeyWithPin(val, pin)",
        ]
        positions = [self.app.index(text) for text in order]
        self.assertEqual(positions, sorted(positions))

    def test_choice_buttons_call_engine(self) -> None:
        self.assertIn("engine.setProvider(provider)", self.app)
        self.assertIn("engine.clearApiKey(provider)", self.app)


if __name__ == "__main__":
    unittest.main()
