"""첨삭 요청(POST /api/feedback)과 기록 조회(GET /api/history) 및 정적 웹 화면을 제공하는 로컬 서버."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import pathlib
from typing import Callable
from urllib.parse import urlparse

from src.feedback_types import (
    FeedbackRecord,
    FeedbackRequest,
    FeedbackResponse,
    ValidationError,
)
from src.gemini import GeminiServiceError, generate_feedback, load_dotenv_file
from src.history_store import HistoryStore

PUBLIC_DIR = pathlib.Path(__file__).resolve().parent.parent / "public"
MAX_BODY_BYTES = 32 * 1024  # 32KB 상한으로 비정상 대용량 요청 차단


class FeedbackApp:
    """HTTP 핸들러와 독립적으로 시험·호출할 수 있는 애플리케이션 코어."""

    def __init__(
        self,
        store: HistoryStore | None = None,
        ai_fn: Callable[[FeedbackRequest], FeedbackResponse] | None = None,
        public_dir: pathlib.Path | None = None,
    ) -> None:
        self.store = store or HistoryStore()
        self.ai_fn = ai_fn or generate_feedback
        self.public_dir = public_dir or PUBLIC_DIR

    def handle_get_history(self) -> tuple[int, dict[str, object]]:
        """저장된 첨삭 기록 목록을 최신순으로 반환한다([G3])."""
        records = self.store.list_records()
        return HTTPStatus.OK, {"items": [rec.to_dict() for rec in records]}

    def handle_post_feedback(self, raw_body: bytes) -> tuple[int, dict[str, object]]:
        """입력 문장을 검증([G1])하고 AI 3단 첨삭([G2]) 후 로컬 기록에 자동 저장([G3])한다."""
        if len(raw_body) > MAX_BODY_BYTES:
            return HTTPStatus.BAD_REQUEST, {
                "error": "요청 크기가 너무 큽니다. 1,000자 이하의 문장으로 입력해 주세요."
            }
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return HTTPStatus.BAD_REQUEST, {
                "error": "올바른 JSON 형식의 요청이 아닙니다."
            }

        try:
            req = FeedbackRequest.from_dict(payload)
        except ValidationError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        try:
            feedback = self.ai_fn(req)
        except ValidationError as exc:
            return HTTPStatus.BAD_GATEWAY, {
                "error": f"AI 응답 형식이 규약과 맞지 않습니다: {exc}"
            }
        except GeminiServiceError as exc:
            return HTTPStatus.BAD_GATEWAY, {"error": str(exc)}

        record = FeedbackRecord.create(req, feedback)
        self.store.save_record(record)
        return HTTPStatus.OK, record.to_dict()

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
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/history":
                status, data = active_app.handle_get_history()
                self._send_json(status, data)
                return

            self._serve_static(parsed.path)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/api/feedback":
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    {"error": "요청하신 API 경로를 찾을 수 없습니다."},
                )
                return

            content_length_Header = self.headers.get("Content-Length", "0")
            try:
                length = int(content_length_Header)
            except ValueError:
                length = 0

            raw_body = self.rfile.read(max(0, min(length, MAX_BODY_BYTES + 1)))
            status, data = active_app.handle_post_feedback(raw_body)
            self._send_json(status, data)

        def _serve_static(self, url_path: str) -> None:
            status, mime, body = active_app.handle_static(url_path)
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
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
    load_dotenv_file()
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
