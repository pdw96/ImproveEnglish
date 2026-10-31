"""첨삭(POST /api/feedback, GET /api/history), 단어장·복습(GET/POST /api/vocab, POST /api/vocab/review, DELETE /api/vocab/<id>), 학습 루틴(GET /api/routine, POST /api/routine/goal), 오늘의 퀴즈(GET/POST /api/quiz/today, POST /api/quiz/attempt) 및 정적 웹 화면을 제공하는 로컬 서버."""

from __future__ import annotations

from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import mimetypes
import os
import pathlib
import threading
from typing import Callable
from urllib.parse import parse_qs, unquote, urlparse

import src.gemini as gemini_module
from src.feedback_types import (
    FeedbackRecord,
    FeedbackRequest,
    FeedbackResponse,
    ValidationError,
)
from src.gemini import GeminiServiceError, generate_feedback, load_dotenv_file
from src.history_store import HistoryStore
from src.mission_service import build_daily_mission_status
from src.quiz_ai import AiQuestionsResult, generate_ai_questions
from src.quiz_service import build_daily_quiz, build_expression_pool
from src.quiz_store import QuizDateMismatch, QuizStore
from src.quiz_types import (
    NOT_ENOUGH_MESSAGE,
    SAVE_FAILED_MESSAGE,
    QuizAttemptRequest,
    build_score_summary,
)
from src.routine_store import RoutineStore
from src.routine_types import DailyGoal
from src.vocab_store import VocabStore
from src.vocab_types import VocabCreateRequest, VocabReviewRequest

PUBLIC_DIR = pathlib.Path(__file__).resolve().parent.parent / "public"
MAX_BODY_BYTES = 32 * 1024  # 32KB 상한으로 비정상 대용량 요청 차단


class FeedbackApp:
    """HTTP 핸들러와 독립적으로 시험·호출할 수 있는 애플리케이션 코어."""

    def __init__(
        self,
        store: HistoryStore | None = None,
        ai_fn: Callable[[FeedbackRequest], FeedbackResponse] | None = None,
        public_dir: pathlib.Path | None = None,
        vocab_store: VocabStore | None = None,
        routine_store: RoutineStore | None = None,
        quiz_store: QuizStore | None = None,
        quiz_ai_fn: Callable[[list, list], AiQuestionsResult] | None = None,
    ) -> None:
        self.store = store or HistoryStore()
        self.vocab_store = vocab_store or VocabStore()
        self.routine_store = routine_store or RoutineStore()
        self.quiz_store = quiz_store or QuizStore()
        # AI 새 문제 요청은 이 한 자리에서만 부른다(설계 ④ — 다음 조각 ai-provider-choice 가 갈아 끼울 자리)
        self._quiz_ai_fn = quiz_ai_fn or generate_ai_questions
        # 오늘 세트 만들기(AI 호출 포함)는 한 번에 하나 — 겹친 [퀴즈 시작] 이 AI 를 두 번 부르지 않게([Q4] · [Q9])
        self._quiz_create_lock = threading.Lock()
        self._custom_ai_fn = ai_fn
        self.public_dir = public_dir or PUBLIC_DIR

    def _call_ai(self, req: FeedbackRequest) -> FeedbackResponse:
        if self._custom_ai_fn is not None:
            return self._custom_ai_fn(req)
        if os.environ.get("DOTENV_AUTORELOAD") == "1":
            importlib.reload(gemini_module)
        return gemini_module.generate_feedback(req)

    def _parse_json_body(
        self, raw_body: bytes
    ) -> tuple[dict[str, object] | None, tuple[int, dict[str, object]] | None]:
        """요청 본문 크기와 JSON 구문을 검증한다."""
        if len(raw_body) > MAX_BODY_BYTES:
            return None, (
                HTTPStatus.BAD_REQUEST,
                {"error": "요청 크기가 너무 큽니다. 허용된 길이 이내로 입력해 주세요."},
            )
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, (
                HTTPStatus.BAD_REQUEST,
                {"error": "올바른 JSON 형식의 요청이 아닙니다."},
            )
        if not isinstance(payload, dict):
            return None, (
                HTTPStatus.BAD_REQUEST,
                {"error": "요청 본문은 JSON 객체여야 합니다."},
            )
        return payload, None

    def handle_get_history(self) -> tuple[int, dict[str, object]]:
        """저장된 첨삭 기록 목록을 최신순으로 반환한다([G3])."""
        records = self.store.list_records()
        return HTTPStatus.OK, {"items": [rec.to_dict() for rec in records]}

    def handle_post_feedback(self, raw_body: bytes) -> tuple[int, dict[str, object]]:
        """입력 문장을 검증([G1])하고 AI 3단 첨삭([G2]) 후 로컬 기록에 자동 저장([G3])한다."""
        payload, err = self._parse_json_body(raw_body)
        if err is not None:
            return err

        try:
            req = FeedbackRequest.from_dict(payload)
        except ValidationError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        try:
            feedback = self._call_ai(req)
        except ValidationError as exc:
            return HTTPStatus.BAD_GATEWAY, {
                "error": f"AI 응답 형식이 규약과 맞지 않습니다: {exc}"
            }
        except gemini_module.GeminiServiceError as exc:
            return HTTPStatus.BAD_GATEWAY, {"error": str(exc)}

        record = FeedbackRecord.create(req, feedback)
        self.store.save_record(record)
        return HTTPStatus.OK, record.to_dict()

    def handle_get_vocab(
        self, today: date | None = None
    ) -> tuple[int, dict[str, object]]:
        """전체 단어장 목록과 오늘 복습할 대상(nextReviewDate <= 오늘) 목록을 반환한다([V2], [V3])."""
        base_today = today or date.today()
        items = self.vocab_store.list_items()
        due_items = [item for item in items if item.is_due(today=base_today)]
        return HTTPStatus.OK, {
            "items": [item.to_dict() for item in items],
            "dueItems": [item.to_dict() for item in due_items],
            "totalCount": len(items),
            "dueCount": len(due_items),
            "today": base_today.isoformat(),
        }

    def handle_post_vocab(
        self, raw_body: bytes, today: date | None = None
    ) -> tuple[int, dict[str, object]]:
        """단어장에 새 표현을 추가하거나 이미 있는 표현이면 중복 생성 없이 기존 항목을 안내한다([V1], [V3])."""
        payload, err = self._parse_json_body(raw_body)
        if err is not None:
            return err

        try:
            req = VocabCreateRequest.from_dict(payload)
        except ValidationError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        item, duplicated = self.vocab_store.add_item(req, today=today)
        message = (
            "이미 단어장에 담긴 표현입니다. 기존 항목을 안내합니다."
            if duplicated
            else "단어장에 새로운 표현을 담았습니다."
        )
        item_dict = item.to_dict()
        return HTTPStatus.OK, {
            **item_dict,
            "item": item_dict,
            "duplicated": duplicated,
            "message": message,
        }

    def handle_post_vocab_review(
        self, raw_body: bytes, today: date | None = None
    ) -> tuple[int, dict[str, object]]:
        """복습 난이도(again / hard / easy) 평가를 반영해 다음 복습 예정일과 오늘의 학습 루틴 기록을 갱신한다([V2], [V3], [R2])."""
        payload, err = self._parse_json_body(raw_body)
        if err is not None:
            return err

        try:
            req = VocabReviewRequest.from_dict(payload)
        except ValidationError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        updated = self.vocab_store.review_item(req, today=today)
        if updated is None:
            return HTTPStatus.NOT_FOUND, {
                "error": "해당 단어장 항목을 찾을 수 없습니다."
            }

        self.routine_store.record_review(updated, req.rating, today=today)

        item_dict = updated.to_dict()
        return HTTPStatus.OK, {
            **item_dict,
            "item": item_dict,
            "message": f"복습 결과가 반영되었습니다(다음 복습일: {updated.next_review_date}).",
        }

    def handle_delete_vocab(self, item_id: str) -> tuple[int, dict[str, object]]:
        """지정한 ID의 단어장 항목을 삭제한다([V3])."""
        if not isinstance(item_id, str) or not item_id.strip():
            return HTTPStatus.BAD_REQUEST, {
                "error": "삭제할 단어장 항목 ID를 입력해 주세요."
            }

        deleted = self.vocab_store.delete_item(item_id)
        if not deleted:
            return HTTPStatus.NOT_FOUND, {
                "error": "해당 단어장 항목을 찾을 수 없습니다."
            }

        return HTTPStatus.OK, {
            "deletedId": item_id.strip(),
            "message": "단어장 항목이 삭제되었습니다.",
        }

    def handle_get_routine(
        self, today: date | None = None
    ) -> tuple[int, dict[str, object]]:
        """연속 학습일(스트릭), 오늘 목표 진행률, 최근 14일 달력 및 날짜별 학습 내역을 반환한다([R2], [R3])."""
        records = self.store.list_records()
        vocab_items = self.vocab_store.list_items()
        summary = self.routine_store.build_routine_summary(
            feedback_records=records,
            vocab_items=vocab_items,
            today=today,
        )
        return HTTPStatus.OK, summary

    def handle_post_routine_goal(
        self, raw_body: bytes, today: date | None = None
    ) -> tuple[int, dict[str, object]]:
        """하루 학습 목표(첨삭 문장 수·복습 단어 수)를 검증·저장하고 갱신된 루틴 현황을 반환한다([R1], [R3])."""
        payload, err = self._parse_json_body(raw_body)
        if err is not None:
            return err

        try:
            goal = DailyGoal.from_dict(payload)
        except ValidationError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        self.routine_store.save_goal(goal)
        records = self.store.list_records()
        vocab_items = self.vocab_store.list_items()
        summary = self.routine_store.build_routine_summary(
            feedback_records=records,
            vocab_items=vocab_items,
            today=today,
        )
        return HTTPStatus.OK, {
            **summary,
            "message": "하루 학습 목표가 저장되었습니다.",
        }

    def handle_get_mission_today(
        self,
        category: str | None = None,
        mission_id: str | None = None,
        exclude_id: str | None = None,
        today: date | None = None,
    ) -> tuple[int, dict[str, object]]:
        """오늘의 상황별 미션, 내 단어장 추천 표현(최대 2개), 오늘 미션 완료 여부를 반환한다([M1]~[M3])."""
        try:
            records = self.store.list_records()
            vocab_items = self.vocab_store.list_items()
            result = build_daily_mission_status(
                feedback_records=records,
                vocab_items=vocab_items,
                category=category,
                mission_id=mission_id,
                exclude_id=exclude_id,
                today=today,
            )
        except ValidationError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}
        return HTTPStatus.OK, result

    def handle_get_quiz_today(
        self, today: date | None = None
    ) -> tuple[int, dict[str, object]]:
        """오늘 세트(있으면)와 오늘 점수 줄을 돌려준다. 세트를 만들지 않는다 — AI 를 부르지 않는다([Q4])."""
        base_today = today or date.today()
        quiz, score = self.quiz_store.get_today_state(base_today)
        return HTTPStatus.OK, {
            "today": base_today.isoformat(),
            "quiz": quiz.to_dict() if quiz is not None else None,
            "score": score.to_dict() if score is not None else None,
        }

    def handle_post_quiz_today(
        self, today: date | None = None
    ) -> tuple[int, dict[str, object]]:
        """[퀴즈 시작] — 오늘 세트가 없으면 만들어 저장하고, 있으면 같은 세트를 돌려준다([Q1] · [Q2] · [Q4] · [Q9]).

        AI 는 오늘 세트가 없을 때만, 세트를 만들기 전에 한 번 부른다 — 같은 날 다시 불러도 · [다시 풀기] 도 부르지 않는다.
        """
        base_today = today or date.today()
        existing, existing_score = self.quiz_store.current_set(base_today)
        if existing is not None:
            return HTTPStatus.OK, {
                "today": base_today.isoformat(),
                "quiz": existing.to_dict(),
                "created": False,
                "score": existing_score.to_dict() if existing_score is not None else None,
            }

        with self._quiz_create_lock:
            # 잠금을 기다리는 사이 다른 요청이 오늘 세트를 만들었으면 그것을 돌려준다 — AI 를 부르지 않는다
            existing, existing_score = self.quiz_store.current_set(base_today)
            if existing is not None:
                return HTTPStatus.OK, {
                    "today": base_today.isoformat(),
                    "quiz": existing.to_dict(),
                    "created": False,
                    "score": existing_score.to_dict() if existing_score is not None else None,
                }
            vocab_items = self.vocab_store.list_items()
            records = self.store.list_records()
            pool = build_expression_pool(vocab_items, records, today=base_today)
            ai_result = self._quiz_ai_fn(pool, records)

            def factory():
                return build_daily_quiz(
                    vocab_items=vocab_items,
                    feedback_records=records,
                    today=base_today,
                    ai_questions=ai_result.questions,
                )

            try:
                quiz, created = self.quiz_store.get_or_create(base_today, factory)
            except OSError:
                return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": SAVE_FAILED_MESSAGE, "saveFailed": True}
        _, score = self.quiz_store.get_today_state(base_today)
        if quiz is None:
            return HTTPStatus.OK, {
                "today": base_today.isoformat(),
                "quiz": None,
                "notEnough": True,
                "message": NOT_ENOUGH_MESSAGE,
                "score": None,
            }
        body: dict[str, object] = {
            "today": base_today.isoformat(),
            "quiz": quiz.to_dict(),
            "created": created,
            "score": score.to_dict() if score is not None else None,
        }
        if created:
            body["aiCount"] = sum(1 for q in quiz.questions if q.source == "ai")
            notice = ai_result.notice()
            if notice:
                body["aiNotice"] = notice
        return HTTPStatus.OK, body

    def handle_get_quiz_scores(
        self, today: date | None = None
    ) -> tuple[int, dict[str, object]]:
        """학습 기록 탭 「퀴즈 점수」 — 최근 14일 날짜별 첫 점수 · 최고 점수와 최근 7일 평균([Q6])."""
        base_today = today or date.today()
        return HTTPStatus.OK, build_score_summary(self.quiz_store.list_scores(), base_today)

    def handle_post_quiz_attempt(self, raw_body: bytes) -> tuple[int, dict[str, object]]:
        """답안을 채점하고 그 세트 날짜의 점수 줄을 고친다. 조건 밖이면 400 이고 저장하지 않는다([Q5] · [Q6])."""
        payload, err = self._parse_json_body(raw_body)
        if err is not None:
            return err
        try:
            req = QuizAttemptRequest.from_dict(payload)
            result, line = self.quiz_store.submit_attempt(req)
        except QuizDateMismatch as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc), "dateChanged": True}
        except OSError:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": SAVE_FAILED_MESSAGE, "saveFailed": True}
        except ValidationError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}
        return HTTPStatus.OK, {**result, "scoreLine": line.to_dict()}

    def handle_static(self, url_path: str) -> tuple[int, str, bytes]:
        """정적 웹 화면 파일(index.html, app.js, styles.css)을 읽고 경로 탐색 공격을 차단한다."""
        rel_path = "index.html" if url_path in ("", "/") else url_path.lstrip("/")
        candidate = (self.public_dir / rel_path).resolve()
        public_root = self.public_dir.resolve()

        if not candidate.is_relative_to(public_root) or not candidate.is_file():
            err_body = json.dumps(
                {"error": "요청하신 페이지를 찾을 수 없습니다."},
                ensure_ascii=False,
            ).encode("utf-8")
            return HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", err_body

        content_type, _ = mimetypes.guess_type(str(candidate))
        if candidate.name.endswith(".webmanifest"):
            mime = "application/manifest+json; charset=utf-8"
        elif candidate.name.endswith(".svg"):
            mime = "image/svg+xml; charset=utf-8"
        else:
            mime = content_type or "application/octet-stream"
            if mime.startswith("text/") or mime in ("application/javascript", "application/json"):
                mime = f"{mime}; charset=utf-8"

        return HTTPStatus.OK, mime, candidate.read_bytes()


def create_http_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    app: FeedbackApp | None = None,
) -> ThreadingHTTPServer:
    """FeedbackApp을 연결한 ThreadingHTTPServer 인스턴스를 생성한다."""
    active_app = app or FeedbackApp()

    class RequestHandler(BaseHTTPRequestHandler):
        def _read_request_body(self) -> bytes:
            content_length_header = self.headers.get("Content-Length", "0")
            try:
                length = int(content_length_header)
            except ValueError:
                length = 0
            return self.rfile.read(max(0, min(length, MAX_BODY_BYTES + 1)))

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/history":
                status, data = active_app.handle_get_history()
                self._send_json(status, data)
                return
            if parsed.path == "/api/vocab":
                status, data = active_app.handle_get_vocab()
                self._send_json(status, data)
                return
            if parsed.path == "/api/routine":
                status, data = active_app.handle_get_routine()
                self._send_json(status, data)
                return
            if parsed.path == "/api/mission/today":
                qs = parse_qs(parsed.query, keep_blank_values=True)
                category = qs["category"][0] if "category" in qs else None
                mission_id = qs["missionId"][0] if "missionId" in qs else None
                exclude_id = qs["excludeId"][0] if "excludeId" in qs else None
                status, data = active_app.handle_get_mission_today(
                    category=category,
                    mission_id=mission_id,
                    exclude_id=exclude_id,
                )
                self._send_json(status, data)
                return
            if parsed.path == "/api/quiz/today":
                status, data = active_app.handle_get_quiz_today()
                self._send_json(status, data)
                return
            if parsed.path == "/api/quiz/scores":
                status, data = active_app.handle_get_quiz_scores()
                self._send_json(status, data)
                return
            if parsed.path.startswith("/api/"):
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    {"error": "요청하신 API 경로를 찾을 수 없습니다."},
                )
                return

            self._serve_static(parsed.path)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            raw_body = self._read_request_body()

            if parsed.path == "/api/feedback":
                status, data = active_app.handle_post_feedback(raw_body)
                self._send_json(status, data)
                return
            if parsed.path == "/api/vocab":
                status, data = active_app.handle_post_vocab(raw_body)
                self._send_json(status, data)
                return
            if parsed.path == "/api/vocab/review":
                status, data = active_app.handle_post_vocab_review(raw_body)
                self._send_json(status, data)
                return
            if parsed.path == "/api/routine/goal":
                status, data = active_app.handle_post_routine_goal(raw_body)
                self._send_json(status, data)
                return
            if parsed.path == "/api/quiz/today":
                status, data = active_app.handle_post_quiz_today()
                self._send_json(status, data)
                return
            if parsed.path == "/api/quiz/attempt":
                status, data = active_app.handle_post_quiz_attempt(raw_body)
                self._send_json(status, data)
                return

            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "요청하신 API 경로를 찾을 수 없습니다."},
            )

        def do_DELETE(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            prefix = "/api/vocab/"
            if parsed.path.startswith(prefix):
                item_id = unquote(parsed.path[len(prefix) :])
                status, data = active_app.handle_delete_vocab(item_id)
                self._send_json(status, data)
                return

            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "요청하신 API 경로를 찾을 수 없습니다."},
            )

        def _serve_static(self, url_path: str) -> None:
            status, mime, body = active_app.handle_static(url_path)
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            # 기본 표준 에러 로그는 유지하되 테스트 중에는 조용히 동작할 수 있게 함
            if os.environ.get("QUIET_SERVER_LOG") == "1":
                return
            super().log_message(format, *args)

    return ThreadingHTTPServer((host, port), RequestHandler)


def main() -> None:
    """로컬 서버 진입점."""
    os.environ["DOTENV_AUTORELOAD"] = "1"
    load_dotenv_file(override=True)
    port_str = os.environ.get("PORT", "8000").strip()
    port = int(port_str) if port_str.isdigit() else 8000
    server = create_http_server(host="127.0.0.1", port=port)
    print(f"ImproveEnglish 서버가 시작되었습니다: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
