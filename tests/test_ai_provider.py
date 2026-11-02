"""조각 9(ai-provider-choice) 자동 시험 — PC 서버 모드(PR 1): [P1] 고르기 · [P2] 고른 회사 하나만 · [P3] 같은 모양 ·
[P4] 실패하면 지금처럼 · [P7] 키 안전 · [P8] 로컬 서버는 자기 화면만 · [P9] 앵커볼트 그대로.

모든 시험은 가짜 전송 함수로 돈다 — 실제 회사로 요청을 보내지 않고, 키도 가짜다.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import pathlib
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


if __name__ == "__main__":
    unittest.main()
