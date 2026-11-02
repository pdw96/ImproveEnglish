"""조각 9(ai-provider-choice): 첨삭 · 퀴즈 AI 새 문제를 고른 회사(Gemini · ChatGPT · Claude) 하나로 보내는 한 자리(설계 ④).

- 고른 회사는 `.env` 의 `AI_PROVIDER`(gemini · openai · anthropic, 그 밖은 gemini)에서 읽는다([P1]).
- 한 요청은 고른 회사 하나만 부른다. 그 회사 안의 모델 후보만 HTTP 404 일 때 다음으로 넘어간다([P2]).
- 지시문 · 응답 스키마는 부르는 쪽(`src/gemini.py` · `src/quiz_ai.py`)의 상수를 그대로 받아 회사 요청 꼴로만 옮긴다 —
  Gemini 요청은 지금과 글자까지 같다([P9] · 앵커볼트).
- 키는 회사마다 머리글로만 보낸다(주소에 넣지 않는다). 오류 글에 키가 섞여 오면 가린다([P7]).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any, Callable

import src.gemini as gemini_module
from src.feedback_types import FeedbackRequest, FeedbackResponse, ValidationError

# 오류 이름은 조각 ai-feedback 때부터 쓰던 것을 그대로 쓴다 — 부르는 쪽(app.py)이 이 이름으로 받는다
AiServiceError = gemini_module.GeminiServiceError

Transport = Callable[[str, dict[str, str], bytes], dict[str, Any]]

PROVIDERS = ("gemini", "openai", "anthropic")
DEFAULT_PROVIDER = "gemini"
PROVIDER_LABELS = {"gemini": "Gemini", "openai": "ChatGPT", "anthropic": "Claude"}
KEY_ENV_NAMES = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

# 회사마다 빠르고 싼 급 하나(저자 판정 2026-11-02). 앞 모델이 HTTP 404(없는 모델)일 때만 다음 후보로 넘어간다
MODEL_CANDIDATES: dict[str, tuple[str, ...]] = {
    "gemini": tuple(gemini_module.FALLBACK_MODELS),
    "openai": ("gpt-5.4-mini", "gpt-5-mini"),
    "anthropic": ("claude-haiku-5-5",),
}

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2026-10-21"
ANTHROPIC_MAX_TOKENS = 8000
ANTHROPIC_EFFORT = "low"

# 크레딧 소진 · 한도 초과로 보는 HTTP 상태 — PC 첨삭은 이때 내장 스마트 코치로 답한다([P4])
CREDIT_OR_LIMIT_STATUS = {
    "gemini": {402, 429},
    "openai": {429},
    "anthropic": {402, 429},
}

_HTTP_STATUS = re.compile(r"HTTP (\d{3})")


@dataclass(frozen=True)
class AiCall:
    """회사와 상관없는 한 번의 AI 요청 — 지시문 · 사용자 글 · Gemini 꼴 응답 스키마 · 온도(Gemini 에만 보냄)."""

    system: str
    user_text: str
    schema: dict[str, Any]
    schema_name: str
    temperature: float


def get_provider() -> str:
    """`AI_PROVIDER` 를 읽는다. 앞뒤 공백 · 대소문자를 맞춘 뒤 목록 밖이면 gemini 다([P1] · ③)."""
    if os.environ.get("DOTENV_AUTORELOAD") == "1":
        gemini_module.load_dotenv_file(override=True)
    value = os.environ.get("AI_PROVIDER", "").strip().lower()
    return value if value in PROVIDERS else DEFAULT_PROVIDER


def _is_placeholder(value: str) -> bool:
    return value.startswith("your_") and value.endswith("_here")


def get_api_key(provider: str) -> str:
    """고른 회사의 키를 환경변수에서 읽는다. 비었거나 `.env.example` 자리표시 값이면 키 없음 오류(키 값은 담지 않음)."""
    if provider == "gemini":
        return gemini_module.get_api_key()
    if os.environ.get("DOTENV_AUTORELOAD") == "1":
        gemini_module.load_dotenv_file(override=True)
    env_name = KEY_ENV_NAMES[provider]
    api_key = os.environ.get(env_name, "").strip()
    if not api_key or _is_placeholder(api_key):
        raise AiServiceError(
            f"{env_name} 환경변수가 설정되지 않았습니다. .env 파일에 유효한 "
            f"{PROVIDER_LABELS[provider]} API 키를 설정해 주세요."
        )
    return api_key


def to_json_schema(gemini_schema: dict[str, Any]) -> dict[str, Any]:
    """Gemini 꼴 응답 스키마를 OpenAI · Anthropic 의 JSON 스키마 꼴로 옮긴다(꼴만 — 칸 · 필수 · 설명은 그대로).

    타입 이름을 소문자로, 모든 객체에 `additionalProperties: false` 를 붙이고, 두 회사가 받지 않는 배열 개수 제한
    (`minItems` · `maxItems`)은 뺀다 — 개수는 받은 뒤 지금의 응답 검사가 문다([P3]).
    """
    out: dict[str, Any] = {}
    for key, value in gemini_schema.items():
        if key in ("minItems", "maxItems"):
            continue
        if key == "type" and isinstance(value, str):
            out["type"] = value.lower()
        elif key == "properties" and isinstance(value, dict):
            out["properties"] = {name: to_json_schema(sub) for name, sub in value.items()}
        elif key == "items" and isinstance(value, dict):
            out["items"] = to_json_schema(value)
        else:
            out[key] = value
    if out.get("type") == "object":
        out["additionalProperties"] = False
    return out


def build_request(provider: str, model: str, api_key: str, call: AiCall) -> tuple[str, dict[str, str], dict[str, Any]]:
    """회사 요청 꼴(주소 · 머리글 · 본문)을 만든다. 키는 머리글에만 넣는다([P7])."""
    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"Content-Type": "application/json; charset=utf-8", "x-goog-api-key": api_key}
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": call.system}]},
            "contents": [{"role": "user", "parts": [{"text": call.user_text}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": call.schema,
                "temperature": call.temperature,
            },
        }
        return url, headers, body
    if provider == "openai":
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
        }
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": call.system},
                {"role": "user", "content": call.user_text},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": call.schema_name, "strict": True, "schema": to_json_schema(call.schema)},
            },
        }
        return OPENAI_ENDPOINT, headers, body
    if provider == "anthropic":
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        body = {
            "model": model,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "system": call.system,
            "messages": [{"role": "user", "content": call.user_text}],
            "output_config": {
                "effort": ANTHROPIC_EFFORT,
                "format": {"type": "json_schema", "schema": to_json_schema(call.schema)},
            },
        }
        return ANTHROPIC_ENDPOINT, headers, body
    raise ValueError(f"알 수 없는 AI 회사: {provider}")


def extract_text(provider: str, raw: Any) -> str:
    """회사 응답에서 JSON 글을 꺼낸다(③). 그 밖의 모양 · 거절 · 잘림은 AiServiceError."""
    try:
        if provider == "gemini":
            text = raw["candidates"][0]["content"]["parts"][0]["text"]
        elif provider == "openai":
            message = raw["choices"][0]["message"]
            if message.get("refusal"):
                raise AiServiceError("AI 가 이 요청에 답하지 않았습니다. 잠시 후 다시 시도해 주세요.")
            text = message["content"]
        elif provider == "anthropic":
            if raw.get("stop_reason") != "end_turn":
                raise AiServiceError("AI 응답이 끝까지 오지 않았습니다. 잠시 후 다시 시도해 주세요.")
            text = next(block["text"] for block in raw["content"] if block.get("type") == "text")
        else:
            raise ValueError(f"알 수 없는 AI 회사: {provider}")
    except AiServiceError:
        raise
    except (KeyError, IndexError, TypeError, AttributeError, StopIteration):
        raise AiServiceError("AI 응답을 해석할 수 없습니다. 잠시 후 다시 시도해 주세요.") from None
    if not isinstance(text, str) or not text.strip():
        raise AiServiceError("AI 응답을 해석할 수 없습니다. 잠시 후 다시 시도해 주세요.")
    return text


def _default_transport(api_key: str) -> Transport:
    def send(url: str, headers: dict[str, str], body: bytes) -> dict[str, Any]:
        return gemini_module._default_http_transport(url, headers, body, api_key_to_mask=api_key)

    return send


def request_text(provider: str, api_key: str, call: AiCall, transport: Transport | None = None) -> str:
    """고른 회사 하나에 보낸다([P2]). 모델 후보는 HTTP 404 일 때만 다음으로 넘어가고, 그 밖의 실패는 바로 올린다."""
    sender = transport or _default_transport(api_key)
    errors: list[str] = []
    for model in MODEL_CANDIDATES[provider]:
        url, headers, body = build_request(provider, model, api_key, call)
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        try:
            raw = sender(url, headers, payload)
        except AiServiceError as exc:
            errors.append(str(exc).replace(api_key, "[REDACTED]"))
            if http_status(exc) != 404:
                break
            continue
        return extract_text(provider, raw)
    raise AiServiceError(" | ".join(dict.fromkeys(errors)))


def http_status(exc: BaseException) -> int | None:
    match = _HTTP_STATUS.search(str(exc))
    return int(match.group(1)) if match else None


def is_credit_or_limit(provider: str, exc: BaseException) -> bool:
    """크레딧 소진 · 한도 초과로 보는 오류인가([P4] — PC 첨삭의 내장 코치 넘김)."""
    return http_status(exc) in CREDIT_OR_LIMIT_STATUS[provider]


def feedback_call(req: FeedbackRequest) -> AiCall:
    """첨삭 요청 — 지시문 · 스키마 · 사용자 글 · 온도는 `build_gemini_payload` 와 같은 값이다(앵커볼트)."""
    payload = gemini_module.build_gemini_payload(req)
    return AiCall(
        system=gemini_module.SYSTEM_INSTRUCTION,
        user_text=payload["contents"][0]["parts"][0]["text"],
        schema=gemini_module.RESPONSE_SCHEMA,
        schema_name="english_feedback",
        temperature=payload["generationConfig"]["temperature"],
    )


def generate_feedback(req: FeedbackRequest, transport: Transport | None = None) -> FeedbackResponse:
    """고른 회사로 3단 첨삭을 받아 지금의 응답 검사(FeedbackResponse.from_dict)를 지나게 한다([P2] · [P3] · [P4])."""
    provider = get_provider()
    api_key = get_api_key(provider)
    try:
        text = request_text(provider, api_key, feedback_call(req), transport)
    except AiServiceError as exc:
        if is_credit_or_limit(provider, exc):
            return gemini_module._build_local_coach_feedback(req)
        raise
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AiServiceError("AI 응답을 해석할 수 없습니다. 잠시 후 다시 시도해 주세요.") from exc
    try:
        return FeedbackResponse.from_dict(parsed)
    except ValidationError as exc:
        raise AiServiceError(f"AI 응답 형식이 규약과 맞지 않습니다: {exc}") from exc
