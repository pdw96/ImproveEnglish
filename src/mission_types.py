"""조각 4(daily-mission): 상황별 영작·말하기 미션 데이터 구조, 카테고리·ID 검증 및 내장 상황별 미션 풀 모듈."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.feedback_types import ValidationError

VALID_MISSION_CATEGORIES: tuple[str, ...] = (
    "all",
    "work",
    "daily",
    "travel",
    "opinion",
)

CATEGORY_LABELS: dict[str, str] = {
    "all": "전체 상황",
    "work": "비즈니스 · 업무",
    "daily": "일상 대화",
    "travel": "여행 · 외출",
    "opinion": "감정 · 의견 표현",
}


@dataclass(frozen=True)
class MissionHint:
    """미션 카드에서 함께 제공하는 상황별 기본 힌트 표현."""

    expression: str
    meaning: str

    def to_dict(self) -> dict[str, str]:
        return {
            "expression": self.expression,
            "meaning": self.meaning,
        }


@dataclass(frozen=True)
class MissionPrompt:
    """내장 상황별 영작·말하기 미션 항목."""

    id: str
    category: str
    category_label: str
    title: str
    situation: str
    guide: str
    starter_template: str
    sample_sentence: str
    hints: tuple[MissionHint, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "categoryLabel": self.category_label,
            "title": self.title,
            "situation": self.situation,
            "guide": self.guide,
            "starterTemplate": self.starter_template,
            "sampleSentence": self.sample_sentence,
            "hints": [hint.to_dict() for hint in self.hints],
        }


@dataclass(frozen=True)
class VocabSuggestion:
    """내 단어장에서 뽑은 '오늘 문장에 써볼 추천 표현' 항목."""

    id: str
    expression: str
    meaning: str
    example: str
    is_due: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "expression": self.expression,
            "meaning": self.meaning,
            "example": self.example,
            "isDue": self.is_due,
        }


MISSION_POOL: tuple[MissionPrompt, ...] = (
    # 1. 비즈니스 · 업무 (work)
    MissionPrompt(
        id="work-reschedule-meeting",
        category="work",
        category_label=CATEGORY_LABELS["work"],
        title="일정 조율 · 회의 시간 미루기",
        situation="급한 업무가 생겨 오늘 오후 회의를 내일로 미룰 수 있는지 동료에게 정중하게 물어보는 상황입니다.",
        guide="회의를 미루고 싶은 이유와 대안 시간을 넣어 한 문장으로 적어 보세요(모르는 단어는 한국어로 섞어도 됩니다).",
        starter_template="Could we push back our meeting to ",
        sample_sentence="Could we push back our meeting to tomorrow afternoon because 급한 일이 생겼다?",
        hints=(
            MissionHint("push back", "(일정을) 뒤로 미루다"),
            MissionHint("reschedule", "일정을 다시 잡다"),
            MissionHint("come up", "(예상치 못한 일이) 생기다"),
        ),
    ),
    MissionPrompt(
        id="work-leave-early",
        category="work",
        category_label=CATEGORY_LABELS["work"],
        title="컨디션 난조 · 일찍 퇴근 양해 구하기",
        situation="몸살 기운이 있어서 오늘만 조금 일찍 퇴근해도 될지 팀장님께 말씀드리는 상황입니다.",
        guide="몸 상태와 일찍 퇴근하고 싶다는 뜻을 담아 자연스럽게 문장을 만들어 보세요.",
        starter_template="I'd like to get off work a bit early today because ",
        sample_sentence="I'd like to get off work early today because 몸살 기운이 있는 것 같다.",
        hints=(
            MissionHint("get off work", "퇴근하다"),
            MissionHint("under the weather", "몸 컨디션이 좋지 않은"),
            MissionHint("call it a day", "오늘 업무를 마무리하다"),
        ),
    ),
    MissionPrompt(
        id="work-follow-up",
        category="work",
        category_label=CATEGORY_LABELS["work"],
        title="업무 진행 상황 · 회신 확인하기",
        situation="지난주에 보낸 제안서나 메일에 대해 상대방의 검토가 어떻게 진행되고 있는지 부담스럽지 않게 물어보는 상황입니다.",
        guide="상대방을 재촉하지 않으면서 진행 상황을 확인하는 문장을 작성해 보세요.",
        starter_template="I'm just following up on ",
        sample_sentence="I'm just following up on 지난주에 보내드린 제안서 검토가 어떻게 되고 있는지 궁금합니다.",
        hints=(
            MissionHint("follow up on", "~의 후속 진행을 확인하다"),
            MissionHint("check in on", "~의 상태를 점검하다"),
            MissionHint("keep me posted", "진행 상황을 계속 알려주다"),
        ),
    ),
    # 2. 일상 대화 (daily)
    MissionPrompt(
        id="daily-weekend-plan",
        category="daily",
        category_label=CATEGORY_LABELS["daily"],
        title="주말 계획 · 집에서 푹 쉬기",
        situation="이번 주말에 뭐 할 거냐는 친구의 질문에, 밀린 잠을 자거나 집에서 푹 쉬며 재충전할 거라고 답하는 상황입니다.",
        guide="이번 주말이나 오늘 저녁에 하고 싶은 나만의 휴식 계획을 적어 보세요.",
        starter_template="This weekend, I'm planning to ",
        sample_sentence="This weekend, I'm planning to 집에서 푹 쉬면서 밀린 잠을 자다.",
        hints=(
            MissionHint("catch up on sleep", "밀린 잠을 자다"),
            MissionHint("take it easy", "무리하지 않고 편히 쉬다"),
            MissionHint("recharge my batteries", "재충전하다"),
        ),
    ),
    MissionPrompt(
        id="daily-raincheck",
        category="daily",
        category_label=CATEGORY_LABELS["daily"],
        title="약속 다음에 하기 · 정중히 거절하기",
        situation="친구가 오늘 저녁에 보자고 했지만 선약이나 피곤함 때문에 다음 기회로 미루자고 말하는 상황입니다.",
        guide="아쉬운 마음과 함께 다음에 꼭 보자는 뉘앙스를 담아 적어 보세요.",
        starter_template="Can I take a rain check on ",
        sample_sentence="Can I take a rain check on 오늘 저녁 약속? 오늘 야근을 해야 해서 다음에 꼭 보자.",
        hints=(
            MissionHint("take a rain check", "(약속을) 다음 기회로 미루다"),
            MissionHint("make it up to you", "다음에 보답하다/만회하다"),
            MissionHint("tied up with", "~로 바쁘다, 묶여 있다"),
        ),
    ),
    MissionPrompt(
        id="daily-habit-routine",
        category="daily",
        category_label=CATEGORY_LABELS["daily"],
        title="요즘 새로 시작한 습관 소개하기",
        situation="요즘 건강이나 영어 실력을 위해 매일 꾸준히 하려고 노력 중인 작은 습관을 소개하는 상황입니다.",
        guide="내가 매일 지키려는 루틴이나 습관을 한 문장으로 표현해 보세요.",
        starter_template="Lately, I've been trying to make a habit of ",
        sample_sentence="Lately, I've been trying to make a habit of 매일 아침 15분씩 영어 문장 연습하기.",
        hints=(
            MissionHint("make a habit of", "~하는 습관을 들이다"),
            MissionHint("stick to", "(계획·루틴을) 꾸준히 지키다"),
            MissionHint("day by day", "하루하루 조금씩"),
        ),
    ),
    # 3. 여행 · 외출 (travel)
    MissionPrompt(
        id="travel-restaurant-request",
        category="travel",
        category_label=CATEGORY_LABELS["travel"],
        title="식당 · 카페에서 메뉴 추천 및 요청하기",
        situation="해외 식당이나 카페에서 직원이 가장 추천하는 메뉴가 무엇인지 묻거나, 조용한 창가 자리로 옮길 수 있는지 요청하는 상황입니다.",
        guide="주문할 때나 자리를 요청할 때 자주 쓰는 표현을 넣어 문장을 만들어 보세요.",
        starter_template="Could you recommend ",
        sample_sentence="Could you recommend 이 식당에서 가장 인기 있는 메뉴 and 창가 자리로 앉을 수 있을까요?",
        hints=(
            MissionHint("what do you recommend", "무엇을 추천하시나요"),
            MissionHint("by the window", "창가 쪽에"),
            MissionHint("on the side", "(소스 등을) 따로 담아 주는"),
        ),
    ),
    MissionPrompt(
        id="travel-hotel-checkin",
        category="travel",
        category_label=CATEGORY_LABELS["travel"],
        title="호텔 체크인 · 짐 보관 요청하기",
        situation="체크인 시간보다 일찍 호텔에 도착해서, 먼저 짐만 맡겨 두고 주변을 둘러보고 오겠다고 말하는 상황입니다.",
        guide="일찍 도착한 상황과 짐 보관 요청을 한 문장으로 이어 보세요.",
        starter_template="Would it be possible to ",
        sample_sentence="Would it be possible to 체크인 전까지 짐을 맡겨 두다 while I look around the city?",
        hints=(
            MissionHint("drop off my luggage", "짐을 맡겨 두다"),
            MissionHint("check in early", "일찍 체크인하다"),
            MissionHint("look around", "주변을 둘러보다"),
        ),
    ),
    # 4. 감정 · 의견 표현 (opinion)
    MissionPrompt(
        id="opinion-polite-disagree",
        category="opinion",
        category_label=CATEGORY_LABELS["opinion"],
        title="상대방 의견을 존중하며 내 생각 덧붙이기",
        situation="상대방의 말에도 일리가 있지만, 다른 관점에서 보면 더 좋은 방법이 있을 것 같다고 부드럽게 의견을 내는 상황입니다.",
        guide="상대방의 말을 먼저 인정한 뒤 내 생각을 자연스럽게 이어 보세요.",
        starter_template="I see your point, but from my perspective ",
        sample_sentence="I see your point, but from my perspective 지금 당장 시작하는 것보다 준비를 더 하는 게 좋겠다.",
        hints=(
            MissionHint("I see your point", "무슨 말씀인지 이해합니다"),
            MissionHint("from my perspective", "제 관점에서는"),
            MissionHint("on the other hand", "다른 한편으로는"),
        ),
    ),
    MissionPrompt(
        id="opinion-express-relief",
        category="opinion",
        category_label=CATEGORY_LABELS["opinion"],
        title="걱정했던 일이 잘 풀렸을 때 안도감 표현하기",
        situation="오랫동안 걱정하던 발표나 시험, 중요한 일정이 무사히 끝나서 마음이 놓인다고 말하는 상황입니다.",
        guide="걱정했던 일과 끝나서 후련한 기분을 담아 문장을 적어 보세요.",
        starter_template="I'm so relieved that ",
        sample_sentence="I'm so relieved that 큰 발표가 무사히 끝났다 and 이제 한시름 놓았다.",
        hints=(
            MissionHint("be relieved that", "~해서 안심이 되다"),
            MissionHint("a weight off my shoulders", "어깨의 무거운 짐을 덜다(한시름 놓다)"),
            MissionHint("go smoothly", "순조롭게 진행되다"),
        ),
    ),
)

MISSION_BY_ID: dict[str, MissionPrompt] = {m.id: m for m in MISSION_POOL}


def validate_mission_query(
    category: str | None = None,
    mission_id: str | None = None,
    exclude_id: str | None = None,
) -> tuple[str, str | None, str | None]:
    """미션 조회 쿼리 파라미터(category, missionId, excludeId)를 검증한다([M1] 보장)."""
    cleaned_cat = "all" if category is None or category == "" else str(category).strip()
    if cleaned_cat not in VALID_MISSION_CATEGORIES:
        allowed_str = ", ".join(VALID_MISSION_CATEGORIES)
        raise ValidationError(
            f"허용되지 않는 미션 카테고리입니다(허용 값: {allowed_str})."
        )

    cleaned_mission_id: str | None = None
    if mission_id is not None and str(mission_id).strip() != "":
        candidate_id = str(mission_id).strip()
        if candidate_id not in MISSION_BY_ID:
            raise ValidationError("존재하지 않는 미션 ID(missionId)입니다.")
        cleaned_mission_id = candidate_id

    cleaned_exclude_id: str | None = None
    if exclude_id is not None and str(exclude_id).strip() != "":
        candidate_ex = str(exclude_id).strip()
        if candidate_ex not in MISSION_BY_ID:
            raise ValidationError("존재하지 않는 제외 미션 ID(excludeId)입니다.")
        cleaned_exclude_id = candidate_ex

    return cleaned_cat, cleaned_mission_id, cleaned_exclude_id
