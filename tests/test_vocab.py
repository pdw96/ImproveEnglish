"""조각 2(vocab-review) 자동 시험 — [V1] 입력 검증 및 중복 방지 · [V2] 난이도 3단계 복습 주기(SRS) 계산 · [V3] 로컬 파일 영속성 및 삭제 보장."""

from __future__ import annotations

from datetime import date
import json
import pathlib
import tempfile
import unittest

from src.app import FeedbackApp
from src.feedback_types import ValidationError
from src.history_store import HistoryStore
from src.vocab_store import VocabStore
from src.vocab_types import (
    VocabCreateRequest,
    VocabItem,
    VocabReviewRequest,
    calculate_next_review,
)


class TestSlice2VocabGuarantees(unittest.TestCase):
    """설계 ② 보장하는 것 [V1] ~ [V3] 검증 시험."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vocab_path = pathlib.Path(self.temp_dir.name) / "vocab-items.json"
        self.history_path = pathlib.Path(self.temp_dir.name) / "feedback-history.json"
        self.vocab_store = VocabStore(self.vocab_path)
        self.history_store = HistoryStore(self.history_path)
        self.app = FeedbackApp(
            store=self.history_store,
            vocab_store=self.vocab_store,
        )
        self.fixed_today = date(2026, 10, 28)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_v1_rejects_invalid_inputs_and_prevents_duplicates(self) -> None:
        """[V1] 빈 표현, 빈 뜻, 길이 상한(표현 200자, 뜻 300자, 예문 500자) 초과 입력은 400으로 거절하고, 동일 표현(대소문자·앞뒤 공백 무시)은 중복 생성하지 않는다."""
        bad_payloads = [
            b"",
            b"not-json",
            json.dumps({"expression": "", "meaning": "퇴근하다"}).encode("utf-8"),
            json.dumps({"expression": "   ", "meaning": "퇴근하다"}).encode("utf-8"),
            json.dumps({"expression": "get off work", "meaning": ""}).encode("utf-8"),
            json.dumps({"expression": "get off work", "meaning": "   \n "}).encode("utf-8"),
            json.dumps({"expression": "a" * 201, "meaning": "길이 초과 표현"}).encode("utf-8"),
            json.dumps({"expression": "get off work", "meaning": "뜻" * 301}).encode("utf-8"),
            json.dumps(
                {
                    "expression": "get off work",
                    "meaning": "퇴근하다",
                    "example": "e" * 501,
                }
            ).encode("utf-8"),
            json.dumps({"expression": 123, "meaning": "퇴근하다"}).encode("utf-8"),
            json.dumps({"expression": "get off work", "meaning": 456}).encode("utf-8"),
        ]
        for raw in bad_payloads:
            with self.subTest(payload=raw[:45]):
                status, body = self.app.handle_post_vocab(raw, today=self.fixed_today)
                self.assertEqual(status, 400)
                self.assertIn("error", body)

        self.assertEqual(self.vocab_store.list_items(), [])

        # 정상 등록 1회
        first_payload = json.dumps(
            {
                "expression": "get off work",
                "meaning": "퇴근하다, 일을 마치고 나오다",
                "example": "What time do you usually get off work?",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        status1, res1 = self.app.handle_post_vocab(first_payload, today=self.fixed_today)
        self.assertEqual(status1, 200)
        self.assertFalse(res1["duplicated"])
        self.assertEqual(res1["expression"], "get off work")
        self.assertEqual(res1["nextReviewDate"], "2026-10-28")

        # 대소문자와 앞뒤 공백만 다른 동일 표현 재등록 시 중복 생성 방지 및 기존 항목 반환
        dup_payload = json.dumps(
            {
                "expression": "  GET OFF WORK  ",
                "meaning": "다른 뜻으로 다시 눌러봄",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        status2, res2 = self.app.handle_post_vocab(dup_payload, today=self.fixed_today)
        self.assertEqual(status2, 200)
        self.assertTrue(res2["duplicated"])
        self.assertEqual(res2["id"], res1["id"])
        self.assertEqual(len(self.vocab_store.list_items()), 1)

    def test_v2_srs_interval_calculation_and_mutations(self) -> None:
        """[V2] 기준 날짜(2026-10-28) 고정 상태에서 again(1일 뒤), hard(3일 뒤), easy 연속(7일 -> 14일 -> 30일 뒤) 계산과 복습 상태 갱신을 검증한다."""
        create_raw = json.dumps(
            {
                "expression": "under the weather",
                "meaning": "몸이 안 좋은, 컨디션이 별로인",
                "example": "I'm feeling a bit under the weather today.",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        status, created = self.app.handle_post_vocab(create_raw, today=self.fixed_today)
        self.assertEqual(status, 200)
        item_id = created["id"]

        # 신규 추가 직후에는 오늘(2026-10-28) 바로 복습 대상(dueItems)에 포함되어야 함
        _, vocab_state = self.app.handle_get_vocab(today=self.fixed_today)
        self.assertEqual(vocab_state["dueCount"], 1)
        self.assertEqual(vocab_state["dueItems"][0]["id"], item_id)

        # 1) easy 1회차: box 0 -> 1, 7일 뒤 (2026-11-04)
        status, rev1 = self.app.handle_post_vocab_review(
            json.dumps({"id": item_id, "rating": "easy"}).encode("utf-8"),
            today=self.fixed_today,
        )
        self.assertEqual(status, 200)
        self.assertEqual(rev1["box"], 1)
        self.assertEqual(rev1["reviewCount"], 1)
        self.assertEqual(rev1["nextReviewDate"], "2026-11-04")

        # 오늘 기준으로는 복습 완료되어 dueCount가 0이 되어야 함
        _, after_rev1 = self.app.handle_get_vocab(today=self.fixed_today)
        self.assertEqual(after_rev1["dueCount"], 0)

        # 2) easy 2회차 (2026-11-04 도래 가정): box 1 -> 2, 14일 뒤 (2026-11-18)
        day2 = date(2026, 11, 4)
        status, rev2 = self.app.handle_post_vocab_review(
            json.dumps({"id": item_id, "rating": "easy"}).encode("utf-8"),
            today=day2,
        )
        self.assertEqual(status, 200)
        self.assertEqual(rev2["box"], 2)
        self.assertEqual(rev2["reviewCount"], 2)
        self.assertEqual(rev2["nextReviewDate"], "2026-11-18")

        # 3) easy 3회차 (2026-11-18 도래 가정): box 2 -> 3, 30일 뒤 (2026-12-18)
        day3 = date(2026, 11, 18)
        status, rev3 = self.app.handle_post_vocab_review(
            json.dumps({"id": item_id, "rating": "easy"}).encode("utf-8"),
            today=day3,
        )
        self.assertEqual(status, 200)
        self.assertEqual(rev3["box"], 3)
        self.assertEqual(rev3["reviewCount"], 3)
        self.assertEqual(rev3["nextReviewDate"], "2026-12-18")

        # 4) hard 선택 시: box = max(1, 현재 box=3) = 3 유지, 3일 뒤 (2026-12-21)
        day4 = date(2026, 12, 18)
        status, rev4 = self.app.handle_post_vocab_review(
            json.dumps({"id": item_id, "rating": "hard"}).encode("utf-8"),
            today=day4,
        )
        self.assertEqual(status, 200)
        self.assertEqual(rev4["box"], 3)
        self.assertEqual(rev4["reviewCount"], 4)
        self.assertEqual(rev4["nextReviewDate"], "2026-12-21")

        # 5) again(몰랐음) 선택 시: box = 0 초기화, 1일 뒤 (2026-12-22)
        day5 = date(2026, 12, 21)
        status, rev5 = self.app.handle_post_vocab_review(
            json.dumps({"id": item_id, "rating": "again"}).encode("utf-8"),
            today=day5,
        )
        self.assertEqual(status, 200)
        self.assertEqual(rev5["box"], 0)
        self.assertEqual(rev5["reviewCount"], 5)
        self.assertEqual(rev5["nextReviewDate"], "2026-12-22")

        # 6) box 0 상태에서 hard 선택 시: box = max(1, 0) = 1, 3일 뒤 (2026-12-25)
        day6 = date(2026, 12, 22)
        status, rev6 = self.app.handle_post_vocab_review(
            json.dumps({"id": item_id, "rating": "hard"}).encode("utf-8"),
            today=day6,
        )
        self.assertEqual(status, 200)
        self.assertEqual(rev6["box"], 1)
        self.assertEqual(rev6["reviewCount"], 6)
        self.assertEqual(rev6["nextReviewDate"], "2026-12-25")

        # 잘못된 rating이나 존재하지 않는 ID 거절 확인
        bad_rating_status, _ = self.app.handle_post_vocab_review(
            json.dumps({"id": item_id, "rating": "wrong"}).encode("utf-8"),
            today=self.fixed_today,
        )
        self.assertEqual(bad_rating_status, 400)

        missing_id_status, _ = self.app.handle_post_vocab_review(
            json.dumps({"id": "non-existent-id", "rating": "easy"}).encode("utf-8"),
            today=self.fixed_today,
        )
        self.assertEqual(missing_id_status, 404)

        # 변조본(Mutation) 대조: 잘못된 box/reviewCount/nextReviewDate가 저장소에 들어오면 ValidationError 발생 확인
        valid_dict = rev6["item"]
        broken_mutations = [
            {**valid_dict, "box": -1},
            {**valid_dict, "box": 4},
            {**valid_dict, "reviewCount": -1},
            {**valid_dict, "nextReviewDate": "not-a-date"},
        ]
        for broken in broken_mutations:
            with self.subTest(broken=broken):
                with self.assertRaises(ValidationError):
                    VocabItem.from_dict(broken)

    def test_v3_persistence_across_reload_and_deletion(self) -> None:
        """[V3] 단어 추가·복습·삭제 결과가 로컬 JSON 파일에 원자적으로 저장되어 재로드 후에도 유지된다."""
        req1 = VocabCreateRequest(
            expression="call it a day",
            meaning="오늘 일은 여기서 마치다, 퇴근하다",
            example="Let's call it a day.",
        )
        req2 = VocabCreateRequest(
            expression="push back",
            meaning="(일정을) 미루다, 연기하다",
            example="Can we push back our meeting?",
        )
        item1, _ = self.vocab_store.add_item(req1, today=self.fixed_today)
        item2, _ = self.vocab_store.add_item(req2, today=self.fixed_today)

        # item1 복습 반영
        self.vocab_store.review_item(
            VocabReviewRequest(id=item1.id, rating="easy"),
            today=self.fixed_today,
        )

        # 새 VocabStore 인스턴스로 디스크에서 다시 읽었을 때 상태가 그대로 유지되는지 확인
        reloaded = VocabStore(self.vocab_path)
        items = reloaded.list_items()
        self.assertEqual(len(items), 2)
        by_id = {it.id: it for it in items}
        self.assertEqual(by_id[item1.id].box, 1)
        self.assertEqual(by_id[item1.id].review_count, 1)
        self.assertEqual(by_id[item1.id].next_review_date, "2026-11-04")
        self.assertEqual(by_id[item2.id].box, 0)
        self.assertEqual(by_id[item2.id].next_review_date, "2026-10-28")

        # 삭제 API 호출 후 디스크에서도 제거되는지 확인
        del_status, del_body = self.app.handle_delete_vocab(item2.id)
        self.assertEqual(del_status, 200)
        self.assertEqual(del_body["deletedId"], item2.id)

        reloaded_after_del = VocabStore(self.vocab_path)
        remaining = reloaded_after_del.list_items()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].id, item1.id)

        # 이미 삭제된 ID 재삭제 시 404 반환 확인
        del_again_status, _ = self.app.handle_delete_vocab(item2.id)
        self.assertEqual(del_again_status, 404)

    def test_http_server_vocab_endpoints_and_ui_end_to_end(self) -> None:
        """PR 2 단어장·복습 웹 화면(HTML/JS/CSS) 및 API(GET/POST/DELETE) 전체 시나리오 확인."""
        status_html, _, raw_html = self.app.handle_static("/")
        html = raw_html.decode("utf-8")
        self.assertEqual(status_html, 200)
        self.assertIn("내 단어장 · 오늘의 복습", html)
        self.assertIn("오늘 복습할 표현 카드", html)
        self.assertIn("정답 보기", html)
        self.assertIn("몰랐음 (1일 뒤)", html)
        self.assertIn("헷갈림 (3일 뒤)", html)
        self.assertIn("쉬웠음 (7일→14일→30일 뒤)", html)

        status_js, _, raw_js = self.app.handle_static("/app.js")
        js = raw_js.decode("utf-8")
        self.assertEqual(status_js, 200)
        self.assertIn("/api/vocab", js)
        self.assertIn("/api/vocab/review", js)
        self.assertIn("+ 단어장에 담기", js)

        # 1) POST /api/vocab
        raw_post = json.dumps(
            {
                "expression": "rain check",
                "meaning": "다음 기회로 미루는 약속",
                "example": "Can I take a rain check on dinner?",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        status_create, created = self.app.handle_post_vocab(
            raw_post, today=self.fixed_today
        )
        self.assertEqual(status_create, 200)
        self.assertFalse(created["duplicated"])
        item_id = created["id"]

        # 2) GET /api/vocab
        status_list, listed = self.app.handle_get_vocab(today=self.fixed_today)
        self.assertEqual(status_list, 200)
        self.assertEqual(listed["totalCount"], 1)
        self.assertEqual(listed["dueCount"], 1)

        # 3) POST /api/vocab/review
        raw_review = json.dumps({"id": item_id, "rating": "easy"}).encode("utf-8")
        status_rev, reviewed = self.app.handle_post_vocab_review(
            raw_review, today=self.fixed_today
        )
        self.assertEqual(status_rev, 200)
        self.assertEqual(reviewed["box"], 1)
        self.assertEqual(reviewed["reviewCount"], 1)
        self.assertEqual(reviewed["nextReviewDate"], "2026-11-04")

        # 4) DELETE /api/vocab/<id>
        status_del, deleted = self.app.handle_delete_vocab(item_id)
        self.assertEqual(status_del, 200)
        self.assertEqual(deleted["deletedId"], item_id)

        # 5) 이미 삭제된 ID 재삭제 시 404 확인
        status_del_again, _ = self.app.handle_delete_vocab(item_id)
        self.assertEqual(status_del_again, 404)


if __name__ == "__main__":
    unittest.main()
