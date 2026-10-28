"""조각 3(study-routine) 자동 시험 — [R1] 하루 학습 목표 입력 검증 · [R2] 연속 학습일(스트릭) 및 달성률 계산 · [R3] 로컬 영속성 및 첨삭·복습 연동 보장."""

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
from src.routine_store import RoutineStore
from src.routine_types import DailyGoal, ReviewLogEntry, calculate_streaks
from src.vocab_store import VocabStore
from tests.test_app import sample_valid_ai_dict


class TestSlice3RoutineGuarantees(unittest.TestCase):
    """설계 ② 보장하는 것 [R1] ~ [R3] 검증 시험."""

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

    def test_r1_rejects_invalid_daily_goal_inputs(self) -> None:
        """[R1] 일일 목표(첨삭 1~20, 복습 1~50) 범위를 벗어나거나 정수가 아닌 입력은 400으로 거절한다."""
        bad_payloads = [
            b"",
            b"not-json",
            json.dumps({"dailyFeedbackGoal": 0, "dailyReviewGoal": 3}).encode("utf-8"),
            json.dumps({"dailyFeedbackGoal": 21, "dailyReviewGoal": 3}).encode("utf-8"),
            json.dumps({"dailyFeedbackGoal": -1, "dailyReviewGoal": 3}).encode("utf-8"),
            json.dumps({"dailyFeedbackGoal": 1, "dailyReviewGoal": 0}).encode("utf-8"),
            json.dumps({"dailyFeedbackGoal": 1, "dailyReviewGoal": 51}).encode("utf-8"),
            json.dumps({"dailyFeedbackGoal": True, "dailyReviewGoal": 3}).encode("utf-8"),
            json.dumps({"dailyFeedbackGoal": 1, "dailyReviewGoal": False}).encode("utf-8"),
            json.dumps({"dailyFeedbackGoal": "2", "dailyReviewGoal": 3}).encode("utf-8"),
            json.dumps({"dailyFeedbackGoal": 2, "dailyReviewGoal": "5"}).encode("utf-8"),
        ]
        for raw in bad_payloads:
            with self.subTest(payload=raw[:45]):
                status, body = self.app.handle_post_routine_goal(
                    raw, today=self.fixed_today
                )
                self.assertEqual(status, 400)
                self.assertIn("error", body)

        # 거절된 후에도 기본값(첨삭 1, 복습 3)이 그대로 유지되어야 함
        goal = self.routine_store.get_goal()
        self.assertEqual(goal.daily_feedback_goal, 1)
        self.assertEqual(goal.daily_review_goal, 3)

        # 정상 범위(첨삭 2, 복습 5) 변경 시 200 OK 및 반영 확인
        ok_raw = json.dumps(
            {"dailyFeedbackGoal": 2, "dailyReviewGoal": 5}
        ).encode("utf-8")
        status_ok, res_ok = self.app.handle_post_routine_goal(
            ok_raw, today=self.fixed_today
        )
        self.assertEqual(status_ok, 200)
        self.assertEqual(res_ok["goal"]["dailyFeedbackGoal"], 2)
        self.assertEqual(res_ok["goal"]["dailyReviewGoal"], 5)

    def test_r2_streak_calculation_and_mutations(self) -> None:
        """[R2] 오늘·어제 기준 연속 학습일(currentStreak), 최장 연속일(longestStreak), 총 학습일 계산을 검증한다."""
        today = date(2026, 10, 28)

        # 1) 학습 기록이 전혀 없을 때
        self.assertEqual(calculate_streaks(set(), today=today), (0, 0, 0))

        # 2) 오늘 포함 3일 연속 학습 (10/26, 10/27, 10/28)
        dates_3_days = {"2026-10-26", "2026-10-27", "2026-10-28"}
        self.assertEqual(calculate_streaks(dates_3_days, today=today), (3, 3, 3))

        # 3) 오늘(10/28)은 아직 학습 전이지만 어제(10/27)까지 3일 연속(10/25, 10/26, 10/27)인 경우 스트릭 3 유지
        dates_until_yesterday = {"2026-10-25", "2026-10-26", "2026-10-27"}
        self.assertEqual(
            calculate_streaks(dates_until_yesterday, today=today), (3, 3, 3)
        )

        # 4) 과거에 4일 연속(10/10~10/13)이 있었고, 어제·오늘(10/27~10/28) 2일 연속 학습한 경우:
        #    currentStreak = 2, longestStreak = 4, totalStudyDays = 6
        dates_with_gap = {
            "2026-10-10",
            "2026-10-11",
            "2026-10-12",
            "2026-10-13",
            "2026-10-27",
            "2026-10-28",
        }
        self.assertEqual(calculate_streaks(dates_with_gap, today=today), (2, 4, 6))

        # 5) 어제와 오늘 모두 공백(마지막 학습이 그제 10/26)인 경우: currentStreak = 0, longestStreak = 2
        dates_broken = {"2026-10-25", "2026-10-26"}
        self.assertEqual(calculate_streaks(dates_broken, today=today), (0, 2, 2))

        # 변조본(Mutation) 대조: 잘못된 ReviewLogEntry 입력 시 ValidationError 발생 확인
        valid_log = {
            "date": "2026-10-28",
            "vocabId": "v-1",
            "expression": "get off work",
            "meaning": "퇴근하다",
            "rating": "easy",
            "reviewedAt": "2026-10-28T06:00:00+00:00",
        }
        mutations = [
            {**valid_log, "date": "invalid-date"},
            {**valid_log, "vocabId": ""},
            {**valid_log, "rating": "invalid-rating"},
        ]
        for broken in mutations:
            with self.subTest(broken=broken):
                with self.assertRaises(ValidationError):
                    ReviewLogEntry.from_dict(broken)

    def test_r3_end_to_end_routine_aggregation_and_persistence(self) -> None:
        """[R3] 첨삭·단어 복습 수행 시 오늘의 루틴 달성·최근 14일 달력·날짜별 내역이 집계되고 재로드 후에도 유지된다."""
        # 하루 목표를 첨삭 1문장, 복습 2단어로 설정
        self.app.handle_post_routine_goal(
            json.dumps({"dailyFeedbackGoal": 1, "dailyReviewGoal": 2}).encode("utf-8"),
            today=self.fixed_today,
        )

        # 과거(어제 2026-10-27) 첨삭 기록 1건 저장
        past_record = FeedbackRecord(
            id="rec-yesterday",
            created_at="2026-10-27T11:00:00+00:00",
            text="I want to 퇴근하다 early",
            input_mode="text",
            feedback=FeedbackResponse.from_dict(sample_valid_ai_dict()),
        )
        self.history_store.save_record(past_record)

        # 오늘(2026-10-28) 첨삭 기록 1건 저장
        today_record = FeedbackRecord(
            id="rec-today",
            created_at="2026-10-28T09:00:00+00:00",
            text="Can we 미루다 our meeting?",
            input_mode="voice",
            feedback=FeedbackResponse.from_dict(sample_valid_ai_dict()),
        )
        self.history_store.save_record(today_record)

        # 단어 2개 등록 후 오늘 복습 2회 수행
        _, v1 = self.app.handle_post_vocab(
            json.dumps({"expression": "get off work", "meaning": "퇴근하다"}).encode("utf-8"),
            today=self.fixed_today,
        )
        _, v2 = self.app.handle_post_vocab(
            json.dumps({"expression": "push back", "meaning": "미루다"}).encode("utf-8"),
            today=self.fixed_today,
        )
        self.app.handle_post_vocab_review(
            json.dumps({"id": v1["id"], "rating": "easy"}).encode("utf-8"),
            today=self.fixed_today,
        )
        self.app.handle_post_vocab_review(
            json.dumps({"id": v2["id"], "rating": "hard"}).encode("utf-8"),
            today=self.fixed_today,
        )

        # 새 RoutineStore 인스턴스로 디스크에서 다시 읽어 검증
        reloaded_routine = RoutineStore(self.routine_path)
        reloaded_app = FeedbackApp(
            store=HistoryStore(self.history_path),
            vocab_store=VocabStore(self.vocab_path),
            routine_store=reloaded_routine,
        )
        status, summary = reloaded_app.handle_get_routine(today=self.fixed_today)
        self.assertEqual(status, 200)
        self.assertEqual(summary["currentStreak"], 2)  # 어제(10/27) + 오늘(10/28)
        self.assertEqual(summary["longestStreak"], 2)
        self.assertEqual(summary["totalStudyDays"], 2)

        today_info = summary["todaySummary"]
        self.assertEqual(today_info["feedbackCount"], 1)
        self.assertEqual(today_info["reviewCount"], 2)
        self.assertTrue(today_info["studied"])
        self.assertTrue(today_info["goalMet"])
        self.assertEqual(today_info["progressPercent"], 100)
        self.assertEqual(len(today_info["feedbacks"]), 1)
        self.assertEqual(len(today_info["reviews"]), 2)
        self.assertEqual(len(summary["recentDays"]), 14)
        self.assertEqual(summary["recentDays"][-1]["date"], "2026-10-28")

    def test_http_server_routine_endpoints_and_ui_end_to_end(self) -> None:
        """PR 2 학습 루틴·달력 웹 화면(HTML/JS/CSS) 및 API(GET /api/routine, POST /api/routine/goal) 전체 시나리오 확인."""
        status_html, _, raw_html = self.app.handle_static("/")
        html = raw_html.decode("utf-8")
        self.assertEqual(status_html, 200)
        self.assertIn("내 학습 루틴 · 기록", html)
        self.assertIn("최근 14일 학습 달력", html)
        self.assertIn("내 하루 학습 목표 설정", html)
        self.assertIn("목표 저장하기", html)

        status_js, _, raw_js = self.app.handle_static("/app.js")
        js = raw_js.decode("utf-8")
        self.assertEqual(status_js, 200)
        self.assertIn("/api/routine", js)
        self.assertIn("/api/routine/goal", js)

        status_css, _, raw_css = self.app.handle_static("/styles.css")
        self.assertEqual(status_css, 200)
        self.assertIn(".routine-banner", raw_css.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
