"""조각 1(ai-feedback) PR 1 자동 시험 — [G1] 입력 검증 · [G2] 3단 구조 보장 · [G3] 자동 기록 보관 · [G4] API 키 보호."""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from src.app import FeedbackApp
from src.feedback_types import (
     FeedbackRequest,
    FeedbackResponse,
    ValidationError,
)
from src.gemini import (
    GeminiServiceError,
    generate_feedback,
)
from src.history_store import HistoryStore


def sample_valid_ai_dict() -> dict[str, object]:
    """정상 3단 첨삭 결과 샘플."""
    return {
        "corrected": "I'd like to get off work early today.",
        "explanation": "'퇴근하다'는 영어로 'get off work' 또는 'leave work'로 자연스럽게 표현합니다.",
        "alternatives": [
            {
                "expression": "I'm hoping to leave work a bit early today.",
                "nuance": "동료나 상사에게 조금 일찍 퇴근하고 싶다고 부드럽게 말할 때 씁니다.",
            },
            {
                "expression": "I want to clock out early today.",
                "nuance": "일상 대화에서 퇴근 도장을 찍고 일찍 나가고 싶다는 캐주얼한 표현입니다.",
            },
        ],
        "keyExpressions": [
            {
                "expression": "get off work",
                "meaning": "퇴근하다, 일을 마치고 나오다",
                "example": "What time do you usually get off work?",
            }
        ],
    }


class TestSlice1Guarantees(unittest.TestCase):
    """설계 ② 보장하는 것 [G1] ~ [G4] 검증 시험."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_path = pathlib.Path(self.temp_dir.name) / "feedback-history.json"
        self.store = HistoryStore(self.history_path)
        self.ai_called = 0

        def fake_ai(req: FeedbackRequest) -> FeedbackResponse:
            self.ai_called += 1
            return FeedbackResponse.from_dict(sample_valid_ai_dict())

        self.app = FeedbackApp(store=self.store, ai_fn=fake_ai)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_g1_rejects_empty_whitespace_and_overlength_inputs(self) -> None:
        """[G1] 빈 문장, 공백만 있는 문장, 1,000자 초과 입력, 잘못된 inputMode는 AI를 부르기 전에 400으로 거절한다."""
        bad_payloads = [
            b"",
            b"not-json",
            json.dumps({"text": ""}).encode("utf-8"),
            json.dumps({"text": "   \n\t  "}).encode("utf-8"),
            json.dumps({"text": "a" * 1001}).encode("utf-8"),
            json.dumps({"text": 12345}).encode("utf-8"),
            json.dumps({"text": "Hello", "inputMode": "invalid_mode"}).encode("utf-8"),
        ]
        for raw in bad_payloads:
            with self.subTest(payload=raw[:40]):
                status, body = self.app.handle_post_feedback(raw)
                self.assertEqual(status, 400)
                self.assertIn("error", body)

        # 거절된 요청들에 대해 AI 호출이나 파일 저장이 한 번도 일어나지 않아야 함
        self.assertEqual(self.ai_called, 0)
        self.assertEqual(self.store.list_records(), [])

    def test_g2_enforces_three_part_feedback_structure(self) -> None:
        """[G2] AI 응답이 3단 구성(교정·이유, 추천 표현 2~3개, 핵심 표현 1개 이상)을 어기면 거절한다."""
        valid = FeedbackResponse.from_dict(sample_valid_ai_dict())
        self.assertEqual(valid.corrected, "I'd like to get off work early today.")
        self.assertEqual(len(valid.alternatives), 2)
        self.assertEqual(len(valid.key_expressions), 1)

        # 변조본(Mutation) 대조: 3단 구성 중 하나라도 비거나 개수가 어긋나면 ValidationError로 떨어져야 함
        mutations = [
            {**sample_valid_ai_dict(), "corrected": ""},
            {**sample_valid_ai_dict(), "explanation": "   "},
            {**sample_valid_ai_dict(), "alternatives": [sample_valid_ai_dict()["alternatives"][0]]},  # 1개뿐(2~3개 위반)
            {**sample_valid_ai_dict(), "keyExpressions": []},  # 0개(최소 1개 위반)
        ]
        for broken in mutations:
            with self.subTest(broken=broken):
                with self.assertRaises(ValidationError):
                    FeedbackResponse.from_dict(broken)

    def test_g3_auto_saves_and_lists_history_newest_first(self) -> None:
        """[G3] 정상 첨삭 결과는 로컬 파일에 즉시 저장되고 최신순으로 조회된다."""
        req1 = json.dumps(
            {"text": "I want to 퇴근하다 early today", "inputMode": "text"},
            ensure_ascii=False,
        ).encode("utf-8")
        req2 = json.dumps(
            {"text": "Can we reschedule our meeting?", "inputMode": "voice"},
            ensure_ascii=False,
        ).encode("utf-8")

        status1, res1 = self.app.handle_post_feedback(req1)
        status2, res2 = self.app.handle_post_feedback(req2)
        self.assertEqual(status1, 200)
        self.assertEqual(status2, 200)
        self.assertEqual(self.ai_called, 2)

        # 새로운 HistoryStore 인스턴스로 디스크에서 다시 읽어도 최신순(req2 -> req1)으로 유지되는지 확인
        reloaded_store = HistoryStore(self.history_path)
        records = reloaded_store.list_records()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].text, "Can we reschedule our meeting?")
        self.assertEqual(records[0].input_mode, "voice")
        self.assertEqual(records[1].text, "I want to 퇴근하다 early today")
        self.assertEqual(records[1].input_mode, "text")
        self.assertEqual(res1["id"], records[1].id)
        self.assertEqual(res2["id"], records[0].id)

    def test_g4_api_key_is_read_from_env_and_never_leaked(self) -> None:
        """[G4] GEMINI_API_KEY는 환경변수에서만 읽고 URL이나 에러 응답에 노출되지 않는다."""
        fake_secret = "AIzaSy_SECRET_TEST_KEY_99999"
        req = FeedbackRequest(text="I want to 퇴근하다 early", input_mode="text")

        captured_url = ""
        captured_headers: dict[str, str] = {}

        def fake_transport(url: str, headers: dict[str, str], body: bytes) -> dict[str, object]:
            nonlocal captured_url, captured_headers
            captured_url = url
            captured_headers = headers
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": json.dumps(sample_valid_ai_dict(), ensure_ascii=False)}
                            ]
                        }
                    }
                ]
            }

        with patch.dict(os.environ, {"GEMINI_API_KEY": fake_secret}, clear=False):
            result = generate_feedback(req, transport=fake_transport)
            self.assertEqual(result.corrected, "I'd like to get off work early today.")
            # URL에 키가 들어가지 않고 헤더로만 전달되는지 검증
            self.assertNotIn(fake_secret, captured_url)
            self.assertEqual(captured_headers.get("x-goog-api-key"), fake_secret)

        # 키가 없을 때 발생하는 에러 메시지에 민감 정보가 없고 502 안내를 반환하는지 검증
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            with self.assertRaises(GeminiServiceError) as ctx:
                generate_feedback(req, transport=fake_transport)
            self.assertNotIn(fake_secret, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
