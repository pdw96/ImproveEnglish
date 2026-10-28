"""조각 4(daily-mission) 자동 시험 — [M1] 카테고리·미션 ID 검증 · [M2] 상황별 미션 선정 및 전환 · [M3] 내 단어장 추천 표현 연동 및 오늘 미션 완료 상태 보장."""

from __future__ import annotations

from datetime import date
import json
import pathlib
import tempfile
import unittest

from src.app import FeedbackApp
from src.feedback_types import (
    FeedbackRecord,
    FeedbackRequest,
    FeedbackResponse,
    ValidationError,
)
from src.history_store import HistoryStore
from src.mission_service import (
    build_daily_mission_status,
    pick_vocab_suggestions,
    select_mission_prompt,
)
from src.mission_types import (
    MISSION_BY_ID,
    VALID_MISSION_CATEGORIES,
    validate_mission_query,
)
from src.routine_store import RoutineStore
from src.vocab_store import VocabStore
from tests.test_app import sample_valid_ai_dict


class TestSlice4DailyMissionGuarantees(unittest.TestCase):
    """설계 ② 보장하는 것 [M1] ~ [M3] 검증 시험."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_path = pathlib.Path(self.temp_dir.name) / "feedback-history.json"
        self.vocab_path = pathlib.Path(self.temp_dir.name) / "vocab-items.json"
        self.routine_path = pathlib.Path(self.temp_dir.name) / "routine-settings.json"

        self.history_store = HistoryStore(self.history_path)
        self.vocab_store = VocabStore(self.vocab_path)
        self.routine_store = RoutineStore(self.routine_path)

        def fake_ai(req: FeedbackRequest) -> FeedbackResponse:
            return FeedbackResponse.from_dict(sample_valid_ai_dict())

        self.app = FeedbackApp(
            store=self.history_store,
            vocab_store=self.vocab_store,
            routine_store=self.routine_store,
            ai_fn=fake_ai,
        )
        self.fixed_today = date(2026, 10, 28)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_m1_rejects_invalid_category_and_mission_ids(self) -> None:
        """[M1] 닫힌 목록 밖의 category나 존재하지 않는 missionId / excludeId는 400으로 거절한다."""
        bad_queries = [
            {"category": "invalid-cat", "mission_id": None, "exclude_id": None},
            {"category": "sports", "mission_id": None, "exclude_id": None},
            {"category": "all", "mission_id": "non-existent-id", "exclude_id": None},
            {"category": "work", "mission_id": None, "exclude_id": "unknown-exclude"},
        ]
        for q in bad_queries:
            with self.subTest(query=q):
                status, body = self.app.handle_get_mission_today(
                    category=q["category"],
                    mission_id=q["mission_id"],
                    exclude_id=q["exclude_id"],
                    today=self.fixed_today,
                )
                self.assertEqual(status, 400)
                self.assertIn("error", body)

        # 변조본(Mutation) 직접 검증
        with self.assertRaises(ValidationError):
            validate_mission_query(category="unknown")
        with self.assertRaises(ValidationError):
            validate_mission_query(mission_id="missing-id")
        with self.assertRaises(ValidationError):
            validate_mission_query(exclude_id="missing-exclude")

        # 허용된 모든 카테고리는 정상 통과해야 함
        for cat in VALID_MISSION_CATEGORIES:
            with self.subTest(valid_category=cat):
                status, body = self.app.handle_get_mission_today(
                    category=cat,
                    today=self.fixed_today,
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["selectedCategory"], cat)
                if cat != "all":
                    self.assertEqual(body["mission"]["category"], cat)

    def test_m2_mission_selection_and_rotation_by_category_and_exclude_id(self) -> None:
        """[M2] 오늘 날짜 기반 기본 미션 반환 및 카테고리 필터·excludeId 전환 시 다른 미션이 선택된다."""
        # 1) 같은 날짜에 기본 호출 시 항상 일관된 미션을 반환
        m_first = select_mission_prompt(category="all", today=self.fixed_today)
        m_second = select_mission_prompt(category="all", today=self.fixed_today)
        self.assertEqual(m_first.id, m_second.id)

        # 2) excludeId 전달 시 직전 미션과 다른 미션이 반환됨
        m_next = select_mission_prompt(
            category="all",
            exclude_id=m_first.id,
            today=self.fixed_today,
        )
        self.assertNotEqual(m_first.id, m_next.id)

        # 3) 특정 카테고리(work, daily, travel, opinion) 내에서도 excludeId로 다른 미션 전환 가능
        for cat in ("work", "daily", "travel", "opinion"):
            with self.subTest(category=cat):
                first_in_cat = select_mission_prompt(
                    category=cat, today=self.fixed_today
                )
                self.assertEqual(first_in_cat.category, cat)
                second_in_cat = select_mission_prompt(
                    category=cat,
                    exclude_id=first_in_cat.id,
                    today=self.fixed_today,
                )
                self.assertEqual(second_in_cat.category, cat)
                self.assertNotEqual(first_in_cat.id, second_in_cat.id)

        # 4) 특정 missionId 지정 시 해당 미션 정확히 반환
        target_id = "travel-hotel-checkin"
        picked = select_mission_prompt(mission_id=target_id, today=self.fixed_today)
        self.assertEqual(picked.id, target_id)
        self.assertEqual(picked.title, MISSION_BY_ID[target_id].title)

    def test_m3_vocab_suggestions_due_priority_and_completion_status(self) -> None:
        """[M3] 내 단어장의 복습 예정 표현을 우선으로 최대 2개 추천하고, 오늘 첨삭 완료 시 completedToday=True로 전환된다."""
        # 초기 상태: 단어장 비어 있음, 오늘 첨삭 0건 -> completedToday = False
        status0, initial = self.app.handle_get_mission_today(today=self.fixed_today)
        self.assertEqual(status0, 200)
        self.assertFalse(initial["completedToday"])
        self.assertEqual(initial["todayFeedbackCount"], 0)
        self.assertEqual(initial["vocabSuggestions"], [])

        # 단어 3개 등록: v1, v2, v3
        _, v1 = self.app.handle_post_vocab(
            json.dumps(
                {
                    "expression": "call it a day",
                    "meaning": "오늘 일을 마무리하다",
                    "example": "Let's call it a day.",
                }
            ).encode("utf-8"),
            today=self.fixed_today,
        )
        _, v2 = self.app.handle_post_vocab(
            json.dumps(
                {
                    "expression": "push back",
                    "meaning": "일정을 미루다",
                    "example": "Can we push back the meeting?",
                }
            ).encode("utf-8"),
            today=self.fixed_today,
        )
        _, v3 = self.app.handle_post_vocab(
            json.dumps(
                {
                    "expression": "under the weather",
                    "meaning": "몸 컨디션이 좋지 않은",
                    "example": "I'm feeling a bit under the weather.",
                }
            ).encode("utf-8"),
            today=self.fixed_today,
        )

        # v3와 v2를 easy로 복습 완료하여 다음 복습일을 7일 뒤로 넘김 -> 오늘 복습 대상(isDue=True)은 v1만 남음
        self.app.handle_post_vocab_review(
            json.dumps({"id": v3["id"], "rating": "easy"}).encode("utf-8"),
            today=self.fixed_today,
        )
        self.app.handle_post_vocab_review(
            json.dumps({"id": v2["id"], "rating": "easy"}).encode("utf-8"),
            today=self.fixed_today,
        )

        status1, mid_state = self.app.handle_get_mission_today(today=self.fixed_today)
        self.assertEqual(status1, 200)
        suggestions = mid_state["vocabSuggestions"]
        self.assertEqual(len(suggestions), 2)
        # 첫 번째 추천 표현은 반드시 오늘 복습 대상(isDue=True)인 v1("call it a day")이어야 함
        self.assertEqual(suggestions[0]["expression"], "call it a day")
        self.assertTrue(suggestions[0]["isDue"])
        # 두 번째 추천 표현은 복습 완료된 최근 단어 중 하나
        self.assertFalse(suggestions[1]["isDue"])

        # 오늘 첨삭 1건 수행 후 completedToday = True 전환 확인
        today_rec = FeedbackRecord(
            id="rec-mission-today",
            created_at="2026-10-28T10:30:00+00:00",
            text="I'd like to call it a day early because I'm under the weather.",
            input_mode="text",
            feedback=FeedbackResponse.from_dict(sample_valid_ai_dict()),
        )
        self.history_store.save_record(today_rec)

        status2, done_state = self.app.handle_get_mission_today(today=self.fixed_today)
        self.assertEqual(status2, 200)
        self.assertTrue(done_state["completedToday"])
        self.assertEqual(done_state["todayFeedbackCount"], 1)

    def test_http_server_mission_endpoints_and_ui_end_to_end(self) -> None:
        """PR 2 오늘의 미션 카드 웹 화면(HTML/JS/CSS) 및 API(GET /api/mission/today) 전체 시나리오 확인."""
        status_html, _, raw_html = self.app.handle_static("/")
        html = raw_html.decode("utf-8")
        self.assertEqual(status_html, 200)
        self.assertIn("오늘의 영작·말하기 미션", html)
        self.assertIn("다른 미션 보기", html)
        self.assertIn("오늘 문장에 써볼 내 단어장 표현", html)

        status_js, _, raw_js = self.app.handle_static("/app.js")
        js = raw_js.decode("utf-8")
        self.assertEqual(status_js, 200)
        self.assertIn("/api/mission/today", js)
        self.assertIn("insertExpressionIntoInput", js)

        status_css, _, raw_css = self.app.handle_static("/styles.css")
        self.assertEqual(status_css, 200)
        self.assertIn(".mission-card", raw_css.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
