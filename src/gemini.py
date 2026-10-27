"""Google Gemini API를 호출해 3단 영어 첨삭 결과를 받아오는 모듈."""

from __future__ import annotations

import json
import os
import pathlib
import urllib.error
import urllib.request
from typing import Any, Callable

from src.feedback_types import FeedbackRequest, FeedbackResponse, ValidationError

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)
VERTEX_EXPRESS_ENDPOINT = (
    f"https://aiplatform.googleapis.com/v1/publishers/google/models/{GEMINI_MODEL}:generateContent"
)


def resolve_gemini_endpoint(api_key: str) -> str:
    """키 종류(AI Studio 'AIza...' vs Vertex AI Express 'AQ....')에 맞는 엔드포인트를 반환한다."""
    if api_key.startswith("AQ."):
        return VERTEX_EXPRESS_ENDPOINT
    return GEMINI_ENDPOINT

# 앵커볼트: AI 첨삭 프롬프트 핵심 규약 및 구조화 출력 스키마(responseSchema)
SYSTEM_INSTRUCTION = (
    "당신은 한국인 학습자를 돕는 친절하고 정확한 원어민 영어 첨삭 코치입니다. "
    "사용자가 입력한 영어 문장(또는 한국어가 섞인 문장, 음성 인식으로 변환된 문장)의 의도를 파악하여 "
    "반드시 지정된 JSON 스키마에 맞춰 다음 3가지를 작성하세요:\n"
    "1. corrected / explanation: 문법 오류나 어색한 표현을 자연스러운 영어로 고친 문장(corrected)과, "
    "왜 그렇게 고쳤는지 이해하기 쉬운 한국어 설명(explanation).\n"
    "2. alternatives: 실제 원어민이 일상이나 비즈니스에서 자주 쓰는 자연스러운 대체 표현 2~3가지. "
    "각 표현(expression)마다 어떤 상황·느낌(뉘앙스)으로 쓰는지 한국어 설명(nuance)을 포함하세요.\n"
    "3. keyExpressions: 이번 문장에서 꼭 외워두면 좋은 핵심 단어나 숙어·패턴 요약(최소 1개 이상). "
    "각 표현(expression), 한국어 뜻(meaning), 짧은 영어 예문(example)을 포함하세요."
)

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "required": ["corrected", "explanation", "alternatives", "keyExpressions"],
    "properties": {
        "corrected": {
            "type": "STRING",
            "description": "어색하거나 틀린 부분을 자연스럽게 교정한 영어 문장",
        },
        "explanation": {
            "type": "STRING",
            "description": "교정한 이유와 문법·표현 포인트를 설명하는 한국어 해설",
        },
        "alternatives": {
            "type": "ARRAY",
            "minItems": 2,
            "maxItems": 3,
            "items": {
                "type": "OBJECT",
                "required": ["expression", "nuance"],
                "properties": {
                    "expression": {
                        "type": "STRING",
                        "description": "원어민이 자주 쓰는 자연스러운 추천 영어 문장",
                    },
                    "nuance": {
                        "type": "STRING",
                        "description": "이 표현이 쓰이는 상황과 뉘앙스에 대한 한국어 설명",
                    },
                },
            },
        },
        "keyExpressions": {
            "type": "ARRAY",
            "minItems": 1,
            "items": {
                "type": "OBJECT",
                "required": ["expression", "meaning", "example"],
                "properties": {
                    "expression": {
                        "type": "STRING",
                        "description": "외워두면 좋은 핵심 영어 단어·숙어·패턴",
                    },
                    "meaning": {
                        "type": "STRING",
                        "description": "핵심 표현의 한국어 뜻",
                    },
                    "example": {
                        "type": "STRING",
                        "description": "핵심 표현을 활용한 짧은 영어 예문",
                    },
                },
            },
        },
    },
}


class GeminiServiceError(RuntimeError):
    """Gemini API 호출 또는 설정 과정에서 발생한 예외(키 값은 절대 포함하지 않음)."""


def load_dotenv_file(
    dotenv_path: pathlib.Path | None = None,
    override: bool = False,
) -> None:
    """저장소 루트의 .env 파일이 있으면 환경변수를 불러온다."""
    target = dotenv_path or (pathlib.Path(__file__).resolve().parent.parent / ".env")
    if not target.is_file():
        return
    try:
        content = target.read_text(encoding="utf-8")
    except OSError:
        return

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and (override or key not in os.environ):
            os.environ[key] = value


def get_api_key() -> str:
    """환경변수(또는 .env 파일)에서 GEMINI_API_KEY를 읽는다([G4] 보장)."""
    if os.environ.get("DOTENV_AUTORELOAD") == "1":
        load_dotenv_file(override=True)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        raise GeminiServiceError(
            "GEMINI_API_KEY 환경변수가 설정되지 않았습니다. .env 파일에 유효한 API 키를 설정해 주세요."
        )
    return api_key


def build_gemini_payload(req: FeedbackRequest) -> dict[str, Any]:
    """요청 문장과 입력 모드를 바탕으로 Gemini API 요청 본문을 생성한다."""
    mode_label = "음성(마이크) 입력 문장" if req.input_mode == "voice" else "키보드 입력 문장"
    user_prompt = f"[{mode_label}]\n{req.text}"
    return {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.3,
        },
    }


def generate_feedback(
    req: FeedbackRequest,
    transport: Callable[[str, dict[str, str], bytes], dict[str, Any]] | None = None,
) -> FeedbackResponse:
    """Gemini API를 호출해 3단 첨삭 결과를 받아 검증한 뒤 반환한다([G2], [G4] 보장)."""
    api_key = get_api_key()
    payload = build_gemini_payload(req)
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    # URL 쿼리 문자열 대신 HTTP 헤더(x-goog-api-key)를 사용해 에러 로그에 키가 노출되지 않도록 보호
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-goog-api-key": api_key,
    }

    sender = transport or _default_http_transport
    endpoint = resolve_gemini_endpoint(api_key)
    raw_response = sender(endpoint, headers, body_bytes)

    try:
        candidates = raw_response.get("candidates") or []
        first_part = candidates[0]["content"]["parts"][0]["text"]
        parsed_json = json.loads(first_part)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise GeminiServiceError("AI 응답을 해석할 수 없습니다. 잠시 후 다시 시도해 주세요.") from exc

    try:
        return FeedbackResponse.from_dict(parsed_json)
    except ValidationError as exc:
        raise GeminiServiceError(f"AI 응답 형식이 규약과 맞지 않습니다: {exc}") from exc


def _default_http_transport(
    url: str, headers: dict[str, str], body: bytes
) -> dict[str, Any]:
    """표준 urllib을 사용해 Gemini REST 엔드포인트를 호출한다."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise GeminiServiceError(
            f"AI 서버 요청이 실패했습니다(HTTP {exc.code}). API 키 또는 사용 한도를 확인해 주세요."
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise GeminiServiceError(
            "AI 서버에 연결할 수 없습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요."
        ) from None
