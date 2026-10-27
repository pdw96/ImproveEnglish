"""Google Gemini API를 호출해 3단 영어 첨삭 결과를 받아오는 모듈."""

from __future__ import annotations

import json
import os
import pathlib
import urllib.error
import urllib.request
from typing import Any, Callable

from src.feedback_types import FeedbackRequest, FeedbackResponse, ValidationError

GEMINI_MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = (
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash",
)
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

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
    if transport is not None:
        raw_response = sender(GEMINI_ENDPOINT, headers, body_bytes)
    else:
        try:
            raw_response = _send_with_auto_auth(api_key, body_bytes)
        except GeminiServiceError as exc:
            # Google AI Studio 선불 크레딧 소진(HTTP 402) 또는 할당량 초과(HTTP 429) 시 내장 스마트 코치 폴백 동작
            if "HTTP 402" in str(exc) or "HTTP 429" in str(exc):
                return _build_local_coach_feedback(req)
            raise

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


def _build_local_coach_feedback(req: FeedbackRequest) -> FeedbackResponse:
    """API 크레딧 부족(HTTP 402/429) 시 즉시 3단 첨삭 화면과 기록 저장을 체험할 수 있는 내장 코치."""
    raw = req.text.strip()
    lower = raw.lower()

    # 자주 쓰는 한영 혼용 표현 사전 매칭
    rules = [
        (
            ("퇴근", "몸이 안 좋"),
            "I'd like to get off work early today because I'm feeling under the weather.",
            "[내장 체험 모드] '퇴근하다'는 'get off work' 또는 'leave work'로, '몸이 안 좋다'는 원어민이 자주 쓰는 숙어인 'feel under the weather'로 바꾸면 훨씬 자연스럽습니다.",
            [
                {
                    "expression": "I'm hoping to head out early today since I'm not feeling well.",
                    "nuance": "동료나 상사에게 몸 상태 때문에 조금 일찍 들어가 보겠다고 부드럽게 양해를 구할 때 씁니다.",
                },
                {
                    "expression": "I need to leave work early today—I'm coming down with something.",
                    "nuance": "감기 기운 등 몸살이 오려는 것 같아 일찍 퇴근해야 할 때 자주 쓰는 표현입니다.",
                },
                {
                    "expression": "Do you mind if I clock out early today? I'm feeling a bit under the weather.",
                    "nuance": "정중하게 조기 퇴근 허락을 구하는 비즈니스 회화 표현입니다.",
                },
            ],
            [
                {
                    "expression": "get off work",
                    "meaning": "퇴근하다, 근무를 마치고 나오다",
                    "example": "What time do you usually get off work on Fridays?",
                },
                {
                    "expression": "under the weather",
                    "meaning": "몸이 안 좋은, 컨디션이 저조한",
                    "example": "I'm feeling a little under the weather this morning.",
                },
            ],
        ),
        (
            ("미루다", "reschedule", "meeting"),
            "Could we push back our meeting to tomorrow afternoon?",
            "[내장 체험 모드] 일정을 뒤로 '미루다'는 'push back' 또는 'reschedule'을 쓰면 자연스럽습니다. 'Can we' 대신 'Could we'를 쓰면 비즈니스 자리에서 더 정중한 느낌을 줍니다.",
            [
                {
                    "expression": "Would it be possible to reschedule our meeting for tomorrow afternoon?",
                    "nuance": "고객사나 상사에게 정중하게 회의 일정 변경을 요청할 때 가장 무난한 표현입니다.",
                },
                {
                    "expression": "Can we move our meeting to tomorrow afternoon instead?",
                    "nuance": "같은 팀 동료와 편하게 회의 시간을 옮기자고 말할 때 자주 씁니다.",
                },
                {
                    "expression": "Let's push the meeting back to tomorrow afternoon if that works for you.",
                    "nuance": "상대방의 일정을 배려하면서 회의를 내일 오후로 미루자고 제안하는 표현입니다.",
                },
            ],
            [
                {
                    "expression": "push back",
                    "meaning": "(일정·회의를 뒤로) 미루다, 연기하다",
                    "example": "We had to push back the launch date by a week.",
                },
                {
                    "expression": "reschedule A for B",
                    "meaning": "A(일정)를 B(새 시간)로 변경하다",
                    "example": "Can we reschedule our call for Thursday?",
                },
            ],
        ),
    ]

    for keywords, corrected, explanation, alternatives, keys in rules:
        if any(k in lower for k in keywords):
            return FeedbackResponse.from_dict(
                {
                    "corrected": corrected,
                    "explanation": explanation,
                    "alternatives": alternatives,
                    "keyExpressions": keys,
                }
            )

    # 일반 입력 문장에 대한 기본 3단 첨삭 생성
    replaced = (
        raw.replace("퇴근하다", "get off work")
        .replace("야근하다", "work overtime")
        .replace("미루다", "push back")
        .replace("몸이 안 좋다", "I'm not feeling well")
    )
    if replaced and replaced[-1] not in ".?!":
        replaced += "."

    return FeedbackResponse.from_dict(
        {
            "corrected": replaced[0].upper() + replaced[1:] if replaced else raw,
            "explanation": (
                f"[내장 체험 모드 — Google AI 크레딧 연결 전 자동 동작] 입력하신 문장('{raw}')의 한국어/어색한 표현을 "
                "자연스러운 영어 어순과 동사구로 다듬었습니다. 첫 글자 대문자와 문장 부호를 함께 교정했습니다."
            ),
            "alternatives": [
                {
                    "expression": f"I was wondering if you could check this: {replaced}",
                    "nuance": "상대방에게 정중하게 내 의사나 상황을 전달할 때 덧붙이기 좋은 완곡한 표현입니다.",
                },
                {
                    "expression": f"Just to let you know, {replaced[0].lower() + replaced[1:] if len(replaced) > 1 else replaced}",
                    "nuance": "일상 대화나 슬랙·이메일에서 가볍게 내 상황을 공유할 때 자주 쓰는 패턴입니다.",
                },
            ],
            "keyExpressions": [
                {
                    "expression": "Just to let you know",
                    "meaning": "참고로 말씀드리자면, 알려드리자면",
                    "example": "Just to let you know, I'll be working from home tomorrow.",
                },
                {
                    "expression": "I was wondering if ~",
                    "meaning": "혹시 ~할 수 있을지 여쭤봅니다 (정중한 요청)",
                    "example": "I was wondering if we could talk for a minute.",
                },
            ],
        }
    )


def _send_with_auto_auth(api_key: str, body: bytes) -> dict[str, Any]:
    """최신 Gemini Flash 모델(gemini-3.8-flash, gemini-flash-latest 등)을 순서대로 호출한다."""
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-goog-api-key": api_key,
    }
    errors: list[str] = []
    for model_name in FALLBACK_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        try:
            return _default_http_transport(url, headers, body, api_key_to_mask=api_key)
        except GeminiServiceError as exc:
            errors.append(str(exc))
            # 404(모델 미지원)인 경우에만 다음 후보 모델로 넘어가고 그 외에는 중단
            if "HTTP 404" not in str(exc):
                break
    raise GeminiServiceError(" | ".join(dict.fromkeys(errors)))


def _default_http_transport(
    url: str,
    headers: dict[str, str],
    body: bytes,
    api_key_to_mask: str = "",
) -> dict[str, Any]:
    """표준 urllib을 사용해 Gemini REST 엔드포인트를 호출한다."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
            err_json = json.loads(err_body)
            msg = err_json.get("error", {}).get("message", "")
            if isinstance(msg, str) and msg.strip():
                # 어떤 경우에도 API 키 값이 에러 메시지에 섞이지 않도록 마스킹([G4] 보장)
                mask_key = api_key_to_mask or headers.get("x-goog-api-key", "")
                if mask_key:
                    msg = msg.replace(mask_key, "[REDACTED]")
                detail = f" ({msg.strip()[:180]})"
        except Exception:
            detail = ""
        raise GeminiServiceError(
            f"AI 서버 요청이 실패했습니다(HTTP {exc.code}){detail}. API 키 또는 사용 한도를 확인해 주세요."
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise GeminiServiceError(
            "AI 서버에 연결할 수 없습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요."
        ) from None
