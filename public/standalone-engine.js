/**
 * ImproveEnglish 조각 5 (standalone-mobile-app): 서버 없이 동작하는 온디바이스 엔진.
 *
 * - 스마트폰 단독 앱(PWA / Android Capacitor / 오프라인) 실행 시 백엔드 서버 없이
 *   조각 1(ai-feedback) · 조각 2(vocab-review) · 조각 3(study-routine) · 조각 4(daily-mission)의
 *   모든 `/api/*` 요청을 브라우저 내부(`localStorage`)에서 동일 규약으로 즉시 처리한다.
 * - 개인 Gemini API 키는 코드에 하드코딩하지 않고, 사용자가 설정 탭에서 입력한 경우에만
 *   기기 내 `localStorage`에서 읽어 `x-goog-api-key` 헤더로 Gemini API를 직접 호출한다([S2] 보장).
 * - API 키가 없거나 오프라인일 때는 내장 스마트 코치가 즉시 3단 첨삭을 반환한다.
 */

(function () {
  const STORAGE_KEYS = {
    MODE: "ie_standalone_mode", // "standalone" (기본) | "server"
    API_KEY: "ie_gemini_api_key",
    HISTORY: "ie_feedback_history_v1",
    VOCAB: "ie_vocab_items_v1",
    ROUTINE: "ie_routine_state_v1",
  };

  const VALID_MISSION_CATEGORIES = ["all", "work", "daily", "travel", "opinion"];
  const CATEGORY_LABELS = {
    all: "전체 상황",
    work: "비즈니스 · 업무",
    daily: "일상 대화",
    travel: "여행 · 외출",
    opinion: "감정 · 의견 표현",
  };

  const MISSION_POOL = [
    {
      id: "work-reschedule-meeting",
      category: "work",
      categoryLabel: CATEGORY_LABELS.work,
      title: "일정 조율 · 회의 시간 미루기",
      situation:
        "급한 업무가 생겨 오늘 오후 회의를 내일로 미룰 수 있는지 동료에게 정중하게 물어보는 상황입니다.",
      guide:
        "회의를 미루고 싶은 이유와 대안 시간을 넣어 한 문장으로 적어 보세요(모르는 단어는 한국어로 섞어도 됩니다).",
      starterTemplate: "Could we push back our meeting to ",
      sampleSentence:
        "Could we push back our meeting to tomorrow afternoon because 급한 일이 생겼다?",
      hints: [
        { expression: "push back", meaning: "(일정을) 뒤로 미루다" },
        { expression: "reschedule", meaning: "일정을 다시 잡다" },
        { expression: "come up", meaning: "(예상치 못한 일이) 생기다" },
      ],
    },
    {
      id: "work-leave-early",
      category: "work",
      categoryLabel: CATEGORY_LABELS.work,
      title: "컨디션 난조 · 일찍 퇴근 양해 구하기",
      situation:
        "몸살 기운이 있어서 오늘만 조금 일찍 퇴근해도 될지 팀장님께 말씀드리는 상황입니다.",
      guide:
        "몸 상태와 일찍 퇴근하고 싶다는 뜻을 담아 자연스럽게 문장을 만들어 보세요.",
      starterTemplate: "I'd like to get off work a bit early today because ",
      sampleSentence:
        "I'd like to get off work early today because 몸살 기운이 있는 것 같다.",
      hints: [
        { expression: "get off work", meaning: "퇴근하다" },
        { expression: "under the weather", meaning: "몸 컨디션이 좋지 않은" },
        { expression: "call it a day", meaning: "오늘 업무를 마무리하다" },
      ],
    },
    {
      id: "work-follow-up",
      category: "work",
      categoryLabel: CATEGORY_LABELS.work,
      title: "업무 진행 상황 · 회신 확인하기",
      situation:
        "지난주에 보낸 제안서나 메일에 대해 상대방의 검토가 어떻게 진행되고 있는지 부담스럽지 않게 물어보는 상황입니다.",
      guide:
        "상대방을 재촉하지 않으면서 진행 상황을 확인하는 문장을 작성해 보세요.",
      starterTemplate: "I'm just following up on ",
      sampleSentence:
        "I'm just following up on 지난주에 보내드린 제안서 검토가 어떻게 되고 있는지 궁금합니다.",
      hints: [
        { expression: "follow up on", meaning: "~의 후속 진행을 확인하다" },
        { expression: "check in on", meaning: "~의 상태를 점검하다" },
        { expression: "keep me posted", meaning: "진행 상황을 계속 알려주다" },
      ],
    },
    {
      id: "daily-weekend-plan",
      category: "daily",
      categoryLabel: CATEGORY_LABELS.daily,
      title: "주말 계획 · 집에서 푹 쉬기",
      situation:
        "이번 주말에 뭐 할 거냐는 친구의 질문에, 밀린 잠을 자거나 집에서 푹 쉬며 재충전할 거라고 답하는 상황입니다.",
      guide: "이번 주말이나 오늘 저녁에 하고 싶은 나만의 휴식 계획을 적어 보세요.",
      starterTemplate: "This weekend, I'm planning to ",
      sampleSentence:
        "This weekend, I'm planning to 집에서 푹 쉬면서 밀린 잠을 자다.",
      hints: [
        { expression: "catch up on sleep", meaning: "밀린 잠을 자다" },
        { expression: "take it easy", meaning: "무리하지 않고 편히 쉬다" },
        { expression: "recharge my batteries", meaning: "재충전하다" },
      ],
    },
    {
      id: "daily-raincheck",
      category: "daily",
      categoryLabel: CATEGORY_LABELS.daily,
      title: "약속 다음에 하기 · 정중히 거절하기",
      situation:
        "친구가 오늘 저녁에 보자고 했지만 선약이나 피곤함 때문에 다음 기회로 미루자고 말하는 상황입니다.",
      guide: "아쉬운 마음과 함께 다음에 꼭 보자는 뉘앙스를 담아 적어 보세요.",
      starterTemplate: "Can I take a rain check on ",
      sampleSentence:
        "Can I take a rain check on 오늘 저녁 약속? 오늘 야근을 해야 해서 다음에 꼭 보자.",
      hints: [
        { expression: "take a rain check", meaning: "(약속을) 다음 기회로 미루다" },
        { expression: "make it up to you", meaning: "다음에 보답하다/만회하다" },
        { expression: "tied up with", meaning: "~로 바쁘다, 묶여 있다" },
      ],
    },
    {
      id: "daily-habit-routine",
      category: "daily",
      categoryLabel: CATEGORY_LABELS.daily,
      title: "요즘 새로 시작한 습관 소개하기",
      situation:
        "요즘 건강이나 영어 실력을 위해 매일 꾸준히 하려고 노력 중인 작은 습관을 소개하는 상황입니다.",
      guide: "내가 매일 지키려는 루틴이나 습관을 한 문장으로 표현해 보세요.",
      starterTemplate: "Lately, I've been trying to make a habit of ",
      sampleSentence:
        "Lately, I've been trying to make a habit of 매일 아침 15분씩 영어 문장 연습하기.",
      hints: [
        { expression: "make a habit of", meaning: "~하는 습관을 들이다" },
        { expression: "stick to", meaning: "(계획·루틴을) 꾸준히 지키다" },
        { expression: "day by day", meaning: "하루하루 조금씩" },
      ],
    },
    {
      id: "travel-restaurant-request",
      category: "travel",
      categoryLabel: CATEGORY_LABELS.travel,
      title: "식당 · 카페에서 메뉴 추천 및 요청하기",
      situation:
        "해외 식당이나 카페에서 직원이 가장 추천하는 메뉴가 무엇인지 묻거나, 조용한 창가 자리로 옮길 수 있는지 요청하는 상황입니다.",
      guide:
        "주문할 때나 자리를 요청할 때 자주 쓰는 표현을 넣어 문장을 만들어 보세요.",
      starterTemplate: "Could you recommend ",
      sampleSentence:
        "Could you recommend 이 식당에서 가장 인기 있는 메뉴 and 창가 자리로 앉을 수 있을까요?",
      hints: [
        { expression: "what do you recommend", meaning: "무엇을 추천하시나요" },
        { expression: "by the window", meaning: "창가 쪽에" },
        { expression: "on the side", meaning: "(소스 등을) 따로 담아 주는" },
      ],
    },
    {
      id: "travel-hotel-checkin",
      category: "travel",
      categoryLabel: CATEGORY_LABELS.travel,
      title: "호텔 체크인 · 짐 보관 요청하기",
      situation:
        "체크인 시간보다 일찍 호텔에 도착해서, 먼저 짐만 맡겨 두고 주변을 둘러보고 오겠다고 말하는 상황입니다.",
      guide: "일찍 도착한 상황과 짐 보관 요청을 한 문장으로 이어 보세요.",
      starterTemplate: "Would it be possible to ",
      sampleSentence:
        "Would it be possible to 체크인 전까지 짐을 맡겨 두다 while I look around the city?",
      hints: [
        { expression: "drop off my luggage", meaning: "짐을 맡겨 두다" },
        { expression: "check in early", meaning: "일찍 체크인하다" },
        { expression: "look around", meaning: "주변을 둘러보다" },
      ],
    },
    {
      id: "opinion-polite-disagree",
      category: "opinion",
      categoryLabel: CATEGORY_LABELS.opinion,
      title: "상대방 의견을 존중하며 내 생각 덧붙이기",
      situation:
        "상대방의 말에도 일리가 있지만, 다른 관점에서 보면 더 좋은 방법이 있을 것 같다고 부드럽게 의견을 내는 상황입니다.",
      guide: "상대방의 말을 먼저 인정한 뒤 내 생각을 자연스럽게 이어 보세요.",
      starterTemplate: "I see your point, but from my perspective ",
      sampleSentence:
        "I see your point, but from my perspective 지금 당장 시작하는 것보다 준비를 더 하는 게 좋겠다.",
      hints: [
        { expression: "I see your point", meaning: "무슨 말씀인지 이해합니다" },
        { expression: "from my perspective", meaning: "제 관점에서는" },
        { expression: "on the other hand", meaning: "다른 한편으로는" },
      ],
    },
    {
      id: "opinion-express-relief",
      category: "opinion",
      categoryLabel: CATEGORY_LABELS.opinion,
      title: "걱정했던 일이 잘 풀렸을 때 안도감 표현하기",
      situation:
        "오랫동안 걱정하던 발표나 시험, 중요한 일정이 무사히 끝나서 마음이 놓인다고 말하는 상황입니다.",
      guide: "걱정했던 일과 끝나서 후련한 기분을 담아 문장을 적어 보세요.",
      starterTemplate: "I'm so relieved that ",
      sampleSentence:
        "I'm so relieved that 큰 발표가 무사히 끝났다 and 이제 한시름 놓았다.",
      hints: [
        { expression: "be relieved that", meaning: "~해서 안심이 되다" },
        {
          expression: "a weight off my shoulders",
          meaning: "어깨의 무거운 짐을 덜다(한시름 놓다)",
        },
        { expression: "go smoothly", meaning: "순조롭게 진행되다" },
      ],
    },
  ];

  const MISSION_BY_ID = {};
  MISSION_POOL.forEach((m) => {
    MISSION_BY_ID[m.id] = m;
  });

  const SYSTEM_INSTRUCTION =
    "당신은 한국인 학습자를 돕는 친절하고 정확한 원어민 영어 첨삭 코치입니다. " +
    "사용자가 입력한 영어 문장(또는 한국어가 섞인 문장, 음성 인식으로 변환된 문장)의 의도를 파악하여 " +
    "반드시 지정된 JSON 스키마에 맞춰 다음 3가지를 작성하세요:\n" +
    "1. corrected / explanation: 문법 오류나 어색한 표현을 자연스러운 영어로 고친 문장(corrected)과, " +
    "왜 그렇게 고쳤는지 이해하기 쉬운 한국어 설명(explanation).\n" +
    "2. alternatives: 실제 원어민이 일상이나 비즈니스에서 자주 쓰는 자연스러운 대체 표현 2~3가지. " +
    "각 표현(expression)마다 어떤 상황·느낌(뉘앙스)으로 쓰는지 한국어 설명(nuance)을 포함하세요.\n" +
    "3. keyExpressions: 이번 문장에서 꼭 외워두면 좋은 핵심 단어나 숙어·패턴 요약(최소 1개 이상). " +
    "각 표현(expression), 한국어 뜻(meaning), 짧은 영어 예문(example)을 포함하세요.";

  const RESPONSE_SCHEMA = {
    type: "OBJECT",
    required: ["corrected", "explanation", "alternatives", "keyExpressions"],
    properties: {
      corrected: { type: "STRING" },
      explanation: { type: "STRING" },
      alternatives: {
        type: "ARRAY",
        minItems: 2,
        maxItems: 3,
        items: {
          type: "OBJECT",
          required: ["expression", "nuance"],
          properties: {
            expression: { type: "STRING" },
            nuance: { type: "STRING" },
          },
        },
      },
      keyExpressions: {
        type: "ARRAY",
        minItems: 1,
        items: {
          type: "OBJECT",
          required: ["expression", "meaning", "example"],
          properties: {
            expression: { type: "STRING" },
            meaning: { type: "STRING" },
            example: { type: "STRING" },
          },
        },
      },
    },
  };

  function getLocalTodayStr() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  function addDaysToDateStr(dateStr, days) {
    const parts = dateStr.split("-").map((n) => parseInt(n, 10));
    const dt = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
    dt.setUTCDate(dt.getUTCDate() + days);
    return dt.toISOString().slice(0, 10);
  }

  function isoToLocalDateStr(isoStr, fallbackToday) {
    if (!isoStr || typeof isoStr !== "string") {
      return fallbackToday || getLocalTodayStr();
    }
    const cleaned = isoStr.trim();
    if (/^\d{4}-\d{2}-\d{2}/.test(cleaned)) {
      return cleaned.slice(0, 10);
    }
    try {
      const dt = new Date(cleaned);
      if (!Number.isNaN(dt.getTime())) {
        return dt.toISOString().slice(0, 10);
      }
    } catch (_) {}
    return fallbackToday || getLocalTodayStr();
  }

  function normalizeExpr(str) {
    return (str || "").trim().toLowerCase();
  }

  function makeId(prefix) {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return `${prefix}-${crypto.randomUUID()}`;
    }
    return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  }

  function readJsonStorage(key, fallbackVal) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return fallbackVal;
      const parsed = JSON.parse(raw);
      return parsed !== null && parsed !== undefined ? parsed : fallbackVal;
    } catch (_) {
      return fallbackVal;
    }
  }

  function writeJsonStorage(key, val) {
    try {
      localStorage.setItem(key, JSON.stringify(val));
    } catch (_) {}
  }

  function getHistoryRecords() {
    const list = readJsonStorage(STORAGE_KEYS.HISTORY, []);
    return Array.isArray(list) ? list : [];
  }

  function saveHistoryRecords(list) {
    writeJsonStorage(STORAGE_KEYS.HISTORY, list);
  }

  function getVocabItems() {
    const list = readJsonStorage(STORAGE_KEYS.VOCAB, []);
    return Array.isArray(list) ? list : [];
  }

  function saveVocabItems(list) {
    writeJsonStorage(STORAGE_KEYS.VOCAB, list);
  }

  function getRoutineState() {
    const state = readJsonStorage(STORAGE_KEYS.ROUTINE, null);
    const defaultGoal = { dailyFeedbackGoal: 1, dailyReviewGoal: 3 };
    if (!state || typeof state !== "object") {
      return { goal: defaultGoal, reviewLogs: [] };
    }
    const g = state.goal || {};
    const fbGoal =
      typeof g.dailyFeedbackGoal === "number" &&
      g.dailyFeedbackGoal >= 1 &&
      g.dailyFeedbackGoal <= 20
        ? Math.floor(g.dailyFeedbackGoal)
        : 1;
    const rvGoal =
      typeof g.dailyReviewGoal === "number" &&
      g.dailyReviewGoal >= 1 &&
      g.dailyReviewGoal <= 50
        ? Math.floor(g.dailyReviewGoal)
        : 3;
    const logs = Array.isArray(state.reviewLogs) ? state.reviewLogs : [];
    return {
      goal: { dailyFeedbackGoal: fbGoal, dailyReviewGoal: rvGoal },
      reviewLogs: logs,
    };
  }

  function saveRoutineState(state) {
    writeJsonStorage(STORAGE_KEYS.ROUTINE, state);
  }

  function buildLocalCoachFeedback(text) {
    const raw = (text || "").trim();
    const lower = raw.toLowerCase();

    if (lower.includes("퇴근") || lower.includes("몸이 안 좋") || lower.includes("몸살")) {
      return {
        corrected:
          "I'd like to get off work early today because I'm feeling under the weather.",
        explanation:
          "[온디바이스 스마트 코치] '퇴근하다'는 'get off work' 또는 'leave work'로, '몸이 안 좋다/몸살 기운이 있다'는 원어민 숙어인 'feel under the weather'로 표현하면 매우 자연스럽습니다.",
        alternatives: [
          {
            expression:
              "I'm hoping to head out early today since I'm not feeling well.",
            nuance:
              "동료나 상사에게 몸 상태 때문에 조금 일찍 들어가 보겠다고 부드럽게 양해를 구할 때 씁니다.",
          },
          {
            expression:
              "I need to leave work early today—I'm coming down with something.",
            nuance:
              "감기 기운 등 몸살이 오려는 것 같아 일찍 퇴근해야 할 때 자주 쓰는 표현입니다.",
          },
          {
            expression:
              "Do you mind if I clock out early today? I'm feeling a bit under the weather.",
            nuance: "정중하게 조기 퇴근 허락을 구하는 비즈니스 회화 표현입니다.",
          },
        ],
        keyExpressions: [
          {
            expression: "get off work",
            meaning: "퇴근하다, 근무를 마치고 나오다",
            example: "What time do you usually get off work on Fridays?",
          },
          {
            expression: "under the weather",
            meaning: "몸이 안 좋은, 컨디션이 저조한",
            example: "I'm feeling a little under the weather this morning.",
          },
        ],
      };
    }

    if (lower.includes("미루다") || lower.includes("reschedule") || lower.includes("meeting")) {
      return {
        corrected: "Could we push back our meeting to tomorrow afternoon?",
        explanation:
          "[온디바이스 스마트 코치] 일정을 뒤로 '미루다'는 'push back' 또는 'reschedule'을 쓰면 자연스럽습니다. 'Can we' 대신 'Could we'를 쓰면 비즈니스 자리에서 더 정중한 느낌을 줍니다.",
        alternatives: [
          {
            expression:
              "Would it be possible to reschedule our meeting for tomorrow afternoon?",
            nuance:
              "고객사나 상사에게 정중하게 회의 일정 변경을 요청할 때 가장 무난한 표현입니다.",
          },
          {
            expression: "Can we move our meeting to tomorrow afternoon instead?",
            nuance:
              "같은 팀 동료와 편하게 회의 시간을 옮기자고 말할 때 자주 씁니다.",
          },
          {
            expression:
              "Let's push the meeting back to tomorrow afternoon if that works for you.",
            nuance:
              "상대방의 일정을 배려하면서 회의를 내일 오후로 미루자고 제안하는 표현입니다.",
          },
        ],
        keyExpressions: [
          {
            expression: "push back",
            meaning: "(일정·회의를 뒤로) 미루다, 연기하다",
            example: "We had to push back the launch date by a week.",
          },
          {
            expression: "reschedule A for B",
            meaning: "A(일정)를 B(새 시간)로 변경하다",
            example: "Can we reschedule our call for Thursday?",
          },
        ],
      };
    }

    let replaced = raw
      .replace(/퇴근하다/g, "get off work")
      .replace(/야근하다/g, "work overtime")
      .replace(/미루다/g, "push back")
      .replace(/몸이 안 좋다/g, "I'm not feeling well")
      .replace(/급한 일이 생겼다/g, "something urgent came up")
      .replace(/집에서 푹 쉬면서 밀린 잠을 자다/g, "relax at home and catch up on sleep");

    if (replaced && !/[.?!]$/.test(replaced)) {
      replaced += ".";
    }
    const capitalized = replaced
      ? replaced.charAt(0).toUpperCase() + replaced.slice(1)
      : raw;

    return {
      corrected: capitalized,
      explanation:
        `[온디바이스 스마트 코치] 입력하신 문장('${raw}')의 한국어/어색한 표현을 자연스러운 영어 어순과 동사구로 다듬었습니다. ` +
        `([앱 설정 · 백업] 탭에서 개인 Gemini API 키를 등록하면 실시간 Gemini AI 모델 첨삭으로도 전환됩니다.)`,
      alternatives: [
        {
          expression: `I was wondering if you could check this: ${capitalized}`,
          nuance:
            "상대방에게 정중하게 내 의사나 상황을 전달할 때 덧붙이기 좋은 완곡한 표현입니다.",
        },
        {
          expression: `Just to let you know, ${
            capitalized.length > 1
              ? capitalized.charAt(0).toLowerCase() + capitalized.slice(1)
              : capitalized
          }`,
          nuance:
            "일상 대화나 메신저·이메일에서 가볍게 내 상황을 공유할 때 자주 쓰는 패턴입니다.",
        },
      ],
      keyExpressions: [
        {
          expression: "Just to let you know",
          meaning: "참고로 말씀드리자면, 알려드리자면",
          example: "Just to let you know, I'll be working from home tomorrow.",
        },
        {
          expression: "I was wondering if ~",
          meaning: "혹시 ~할 수 있을지 여쭤봅니다 (정중한 요청)",
          example: "I was wondering if we could talk for a minute.",
        },
      ],
    };
  }

  async function callDirectGeminiOrCoach(text, inputMode, rawFetch) {
    const savedKey = (localStorage.getItem(STORAGE_KEYS.API_KEY) || "").trim();
    if (!savedKey) {
      return buildLocalCoachFeedback(text);
    }

    const modeLabel =
      inputMode === "voice" ? "음성(마이크) 입력 문장" : "키보드 입력 문장";
    const bodyObj = {
      systemInstruction: { parts: [{ text: SYSTEM_INSTRUCTION }] },
      contents: [
        {
          role: "user",
          parts: [{ text: `[${modeLabel}]\n${text}` }],
        },
      ],
      generationConfig: {
        responseMimeType: "application/json",
        responseSchema: RESPONSE_SCHEMA,
        temperature: 0.3,
      },
    };

    const models = ["gemini-2.5-flash", "gemini-flash-latest"];
    for (const modelName of models) {
      const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent`;
      try {
        // URL 쿼리 파라미터 대신 x-goog-api-key 헤더로만 전송([S2] 보장)
        const res = await rawFetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "x-goog-api-key": savedKey,
          },
          body: JSON.stringify(bodyObj),
        });
        if (!res.ok) {
          continue;
        }
        const rawJson = await res.json();
        const firstText =
          rawJson &&
          rawJson.candidates &&
          rawJson.candidates[0] &&
          rawJson.candidates[0].content &&
          rawJson.candidates[0].content.parts &&
          rawJson.candidates[0].content.parts[0] &&
          rawJson.candidates[0].content.parts[0].text;
        if (!firstText) continue;
        const parsed = JSON.parse(firstText);
        if (
          parsed &&
          typeof parsed.corrected === "string" &&
          typeof parsed.explanation === "string" &&
          Array.isArray(parsed.alternatives) &&
          parsed.alternatives.length >= 2 &&
          Array.isArray(parsed.keyExpressions) &&
          parsed.keyExpressions.length >= 1
        ) {
          return parsed;
        }
      } catch (_) {
        // 오프라인이거나 네트워크 오류 시 내장 스마트 코치로 안전하게 폴백
      }
    }

    return buildLocalCoachFeedback(text);
  }

  function calculateStreaksJs(studiedDatesSet, todayStr) {
    const validDates = Array.from(studiedDatesSet)
      .filter((d) => typeof d === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d) && d <= todayStr)
      .sort();

    if (!validDates.length) {
      return { currentStreak: 0, longestStreak: 0, totalStudyDays: 0 };
    }

    let longest = 1;
    let currentRun = 1;
    for (let i = 1; i < validDates.length; i++) {
      if (addDaysToDateStr(validDates[i - 1], 1) === validDates[i]) {
        currentRun += 1;
        if (currentRun > longest) longest = currentRun;
      } else {
        currentRun = 1;
      }
    }

    const yesterdayStr = addDaysToDateStr(todayStr, -1);
    const validLookup = new Set(validDates);
    let cursor = null;
    if (validLookup.has(todayStr)) {
      cursor = todayStr;
    } else if (validLookup.has(yesterdayStr)) {
      cursor = yesterdayStr;
    } else {
      return {
        currentStreak: 0,
        longestStreak: longest,
        totalStudyDays: validDates.length,
      };
    }

    let currentStreak = 0;
    while (validLookup.has(cursor)) {
      currentStreak += 1;
      cursor = addDaysToDateStr(cursor, -1);
    }

    return {
      currentStreak,
      longestStreak: longest,
      totalStudyDays: validDates.length,
    };
  }

  function buildRoutineSummaryJs() {
    const todayStr = getLocalTodayStr();
    const historyRecords = getHistoryRecords();
    const vocabItems = getVocabItems();
    const routineState = getRoutineState();
    const goal = routineState.goal;
    const reviewLogs = routineState.reviewLogs;

    const feedbacksByDate = {};
    historyRecords.forEach((rec) => {
      const dStr = isoToLocalDateStr(rec.createdAt, todayStr);
      if (!feedbacksByDate[dStr]) feedbacksByDate[dStr] = [];
      feedbacksByDate[dStr].push({
        id: rec.id,
        text: rec.text,
        corrected: rec.feedback ? rec.feedback.corrected : "",
        inputMode: rec.inputMode || "text",
        createdAt: rec.createdAt,
      });
    });

    const reviewsByDate = {};
    const loggedKeys = new Set();
    reviewLogs.forEach((entry) => {
      if (!entry || !entry.date) return;
      if (!reviewsByDate[entry.date]) reviewsByDate[entry.date] = [];
      reviewsByDate[entry.date].push(entry);
      loggedKeys.add(`${entry.date}:${entry.vocabId}`);
    });

    vocabItems.forEach((item) => {
      if ((item.reviewCount || 0) > 0 && item.lastReviewedAt) {
        const dStr = isoToLocalDateStr(item.lastReviewedAt, todayStr);
        const key = `${dStr}:${item.id}`;
        if (!loggedKeys.has(key)) {
          if (!reviewsByDate[dStr]) reviewsByDate[dStr] = [];
          reviewsByDate[dStr].push({
            date: dStr,
            vocabId: item.id,
            expression: item.expression,
            meaning: item.meaning,
            rating: (item.box || 0) >= 1 ? "easy" : "again",
            reviewedAt: item.lastReviewedAt,
          });
        }
      }
    });

    const allDates = new Set([
      ...Object.keys(feedbacksByDate),
      ...Object.keys(reviewsByDate),
    ]);
    const studiedDates = new Set();
    allDates.forEach((dStr) => {
      const fbLen = (feedbacksByDate[dStr] || []).length;
      const rvLen = (reviewsByDate[dStr] || []).length;
      if (fbLen >= 1 || rvLen >= 1) {
        studiedDates.add(dStr);
      }
    });

    const streaks = calculateStreaksJs(studiedDates, todayStr);

    function makeDaySummary(dStr) {
      const fbList = feedbacksByDate[dStr] || [];
      const rvList = reviewsByDate[dStr] || [];
      const fbCount = fbList.length;
      const rvCount = rvList.length;
      const studied = fbCount >= 1 || rvCount >= 1;
      const goalMet =
        fbCount >= goal.dailyFeedbackGoal && rvCount >= goal.dailyReviewGoal;
      const fbRatio = Math.min(1, fbCount / Math.max(1, goal.dailyFeedbackGoal));
      const rvRatio = Math.min(1, rvCount / Math.max(1, goal.dailyReviewGoal));
      const progressPercent = Math.round((fbRatio * 0.5 + rvRatio * 0.5) * 100);
      return {
        date: dStr,
        feedbackCount: fbCount,
        reviewCount: rvCount,
        studied,
        goalMet,
        progressPercent,
        feedbacks: fbList,
        reviews: rvList,
      };
    }

    const recentDays = [];
    for (let offset = 13; offset >= 0; offset--) {
      const dStr = addDaysToDateStr(todayStr, -offset);
      recentDays.push(makeDaySummary(dStr));
    }

    const historyDays = Array.from(studiedDates)
      .filter((d) => d <= todayStr)
      .sort()
      .reverse()
      .map((dStr) => makeDaySummary(dStr));

    return {
      today: todayStr,
      goal,
      currentStreak: streaks.currentStreak,
      longestStreak: streaks.longestStreak,
      totalStudyDays: streaks.totalStudyDays,
      todaySummary: makeDaySummary(todayStr),
      recentDays,
      historyDays,
    };
  }

  function makeJsonResponse(status, payload) {
    return new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  async function handleLocalApiRequest(urlObj, options, rawFetch) {
    const apiIdx = urlObj.pathname.indexOf("/api/");
    const path = apiIdx >= 0 ? urlObj.pathname.slice(apiIdx) : urlObj.pathname;
    const method = ((options && options.method) || "GET").toUpperCase();
    const todayStr = getLocalTodayStr();

    let bodyObj = {};
    if (method === "POST" && options && options.body) {
      try {
        bodyObj =
          typeof options.body === "string"
            ? JSON.parse(options.body)
            : options.body;
      } catch (_) {
        return makeJsonResponse(400, {
          error: "올바른 JSON 형식의 요청이 아닙니다.",
        });
      }
    }

    // 1) GET /api/history
    if (method === "GET" && path === "/api/history") {
      return makeJsonResponse(200, { items: getHistoryRecords() });
    }

    // 2) POST /api/feedback
    if (method === "POST" && path === "/api/feedback") {
      const text = typeof bodyObj.text === "string" ? bodyObj.text.trim() : "";
      const inputMode = bodyObj.inputMode === "voice" ? "voice" : "text";
      if (!text) {
        return makeJsonResponse(400, {
          error: "첨삭받을 문장을 입력해 주세요.",
        });
      }
      if (text.length > 1000) {
        return makeJsonResponse(400, {
          error: "문장은 최대 1,000자까지 입력할 수 있습니다.",
        });
      }
      const feedback = await callDirectGeminiOrCoach(text, inputMode, rawFetch);
      const record = {
        id: makeId("fb"),
        createdAt: new Date().toISOString(),
        text,
        inputMode,
        feedback,
      };
      const existing = getHistoryRecords();
      saveHistoryRecords([record, ...existing]);
      return makeJsonResponse(200, record);
    }

    // 3) GET /api/vocab
    if (method === "GET" && path === "/api/vocab") {
      const items = getVocabItems();
      const dueItems = items.filter((it) => (it.nextReviewDate || "") <= todayStr);
      return makeJsonResponse(200, {
        items,
        dueItems,
        totalCount: items.length,
        dueCount: dueItems.length,
        today: todayStr,
      });
    }

    // 4) POST /api/vocab
    if (method === "POST" && path === "/api/vocab") {
      const expression =
        typeof bodyObj.expression === "string" ? bodyObj.expression.trim() : "";
      const meaning =
        typeof bodyObj.meaning === "string" ? bodyObj.meaning.trim() : "";
      const example =
        typeof bodyObj.example === "string" ? bodyObj.example.trim() : "";

      if (!expression) {
        return makeJsonResponse(400, {
          error: "단어장에 담을 영어 표현을 입력해 주세요.",
        });
      }
      if (expression.length > 200) {
        return makeJsonResponse(400, {
          error: "영어 표현은 200자 이하로 입력해 주세요.",
        });
      }
      if (!meaning) {
        return makeJsonResponse(400, {
          error: "한국어 뜻을 입력해 주세요.",
        });
      }
      if (meaning.length > 300) {
        return makeJsonResponse(400, {
          error: "한국어 뜻은 300자 이하로 입력해 주세요.",
        });
      }
      if (example.length > 500) {
        return makeJsonResponse(400, {
          error: "영어 예문은 500자 이하로 입력해 주세요.",
        });
      }

      const items = getVocabItems();
      const targetNorm = normalizeExpr(expression);
      const found = items.find(
        (it) => normalizeExpr(it.expression) === targetNorm
      );
      if (found) {
        return makeJsonResponse(200, {
          ...found,
          item: found,
          duplicated: true,
          message: "이미 단어장에 담긴 표현입니다. 기존 항목을 안내합니다.",
        });
      }

      const newItem = {
        id: makeId("vocab"),
        expression,
        meaning,
        example,
        box: 0,
        nextReviewDate: todayStr,
        reviewCount: 0,
        createdAt: new Date().toISOString(),
        lastReviewedAt: null,
      };
      saveVocabItems([newItem, ...items]);
      return makeJsonResponse(200, {
        ...newItem,
        item: newItem,
        duplicated: false,
        message: "단어장에 새로운 표현을 담았습니다.",
      });
    }

    // 5) POST /api/vocab/review
    if (method === "POST" && path === "/api/vocab/review") {
      const id = typeof bodyObj.id === "string" ? bodyObj.id.trim() : "";
      const rating = bodyObj.rating;
      if (!id || !["again", "hard", "easy"].includes(rating)) {
        return makeJsonResponse(400, {
          error: "유효한 단어 ID와 복습 난이도(again/hard/easy)를 입력해 주세요.",
        });
      }

      const items = getVocabItems();
      let updatedItem = null;
      const nextList = items.map((it) => {
        if (it.id !== id || updatedItem !== null) return it;
        let nextBox = it.box || 0;
        let intervalDays = 1;
        if (rating === "again") {
          nextBox = 0;
          intervalDays = 1;
        } else if (rating === "hard") {
          nextBox = Math.max(0, nextBox);
          intervalDays = 3;
        } else {
          nextBox = Math.min(3, Math.max(0, nextBox) + 1);
          intervalDays = nextBox === 1 ? 7 : nextBox === 2 ? 14 : 30;
        }
        updatedItem = {
          ...it,
          box: nextBox,
          nextReviewDate: addDaysToDateStr(todayStr, intervalDays),
          reviewCount: (it.reviewCount || 0) + 1,
          lastReviewedAt: new Date().toISOString(),
        };
        return updatedItem;
      });

      if (!updatedItem) {
        return makeJsonResponse(404, {
          error: "해당 단어장 항목을 찾을 수 없습니다.",
        });
      }

      saveVocabItems(nextList);

      const routineState = getRoutineState();
      const newLog = {
        date: todayStr,
        vocabId: updatedItem.id,
        expression: updatedItem.expression,
        meaning: updatedItem.meaning,
        rating,
        reviewedAt: updatedItem.lastReviewedAt,
      };
      saveRoutineState({
        goal: routineState.goal,
        reviewLogs: [newLog, ...routineState.reviewLogs],
      });

      return makeJsonResponse(200, {
        ...updatedItem,
        item: updatedItem,
        message: `복습 결과가 반영되었습니다(다음 복습일: ${updatedItem.nextReviewDate}).`,
      });
    }

    // 6) DELETE /api/vocab/<id>
    if (method === "DELETE" && path.startsWith("/api/vocab/")) {
      const itemId = decodeURIComponent(path.slice("/api/vocab/".length)).trim();
      const items = getVocabItems();
      const remaining = items.filter((it) => it.id !== itemId);
      if (remaining.length === items.length) {
        return makeJsonResponse(404, {
          error: "해당 단어장 항목을 찾을 수 없습니다.",
        });
      }
      saveVocabItems(remaining);
      return makeJsonResponse(200, {
        deletedId: itemId,
        message: "단어장 항목이 삭제되었습니다.",
      });
    }

    // 7) GET /api/routine
    if (method === "GET" && path === "/api/routine") {
      return makeJsonResponse(200, buildRoutineSummaryJs());
    }

    // 8) POST /api/routine/goal
    if (method === "POST" && path === "/api/routine/goal") {
      const fbGoal = bodyObj.dailyFeedbackGoal;
      const rvGoal = bodyObj.dailyReviewGoal;
      if (
        typeof fbGoal !== "number" ||
        !Number.isInteger(fbGoal) ||
        fbGoal < 1 ||
        fbGoal > 20
      ) {
        return makeJsonResponse(400, {
          error: "일일 첨삭 목표(dailyFeedbackGoal)는 1~20 사이의 정수여야 합니다.",
        });
      }
      if (
        typeof rvGoal !== "number" ||
        !Number.isInteger(rvGoal) ||
        rvGoal < 1 ||
        rvGoal > 50
      ) {
        return makeJsonResponse(400, {
          error: "일일 복습 목표(dailyReviewGoal)는 1~50 사이의 정수여야 합니다.",
        });
      }
      const routineState = getRoutineState();
      saveRoutineState({
        goal: { dailyFeedbackGoal: fbGoal, dailyReviewGoal: rvGoal },
        reviewLogs: routineState.reviewLogs,
      });
      const summary = buildRoutineSummaryJs();
      return makeJsonResponse(200, {
        ...summary,
        message: "하루 학습 목표가 저장되었습니다.",
      });
    }

    // 9) GET /api/mission/today
    if (method === "GET" && path === "/api/mission/today") {
      const catParam = (urlObj.searchParams.get("category") || "all").trim();
      const missionIdParam = (urlObj.searchParams.get("missionId") || "").trim();
      const excludeIdParam = (urlObj.searchParams.get("excludeId") || "").trim();

      if (!VALID_MISSION_CATEGORIES.includes(catParam)) {
        return makeJsonResponse(400, {
          error: "허용되지 않는 미션 카테고리입니다.",
        });
      }
      if (missionIdParam && !MISSION_BY_ID[missionIdParam]) {
        return makeJsonResponse(400, {
          error: "존재하지 않는 미션 ID(missionId)입니다.",
        });
      }
      if (excludeIdParam && !MISSION_BY_ID[excludeIdParam]) {
        return makeJsonResponse(400, {
          error: "존재하지 않는 제외 미션 ID(excludeId)입니다.",
        });
      }

      let chosen = null;
      if (missionIdParam) {
        chosen = MISSION_BY_ID[missionIdParam];
      } else {
        const candidates = MISSION_POOL.filter(
          (m) => catParam === "all" || m.category === catParam
        );
        if (excludeIdParam && candidates.length > 1) {
          const idx = candidates.findIndex((m) => m.id === excludeIdParam);
          if (idx >= 0) {
            chosen = candidates[(idx + 1) % candidates.length];
          }
        }
        if (!chosen) {
          const dayNum = Math.floor(Date.now() / 86400000);
          chosen = candidates[dayNum % candidates.length] || MISSION_POOL[0];
        }
      }

      const vocabItems = getVocabItems();
      const dueSuggestions = [];
      const otherSuggestions = [];
      vocabItems.forEach((it) => {
        const isDue = (it.nextReviewDate || "") <= todayStr;
        const entry = {
          id: it.id,
          expression: it.expression,
          meaning: it.meaning,
          example: it.example || "",
          isDue,
        };
        if (isDue) dueSuggestions.push(entry);
        else otherSuggestions.push(entry);
      });
      const vocabSuggestions = [...dueSuggestions, ...otherSuggestions].slice(0, 2);

      const historyRecords = getHistoryRecords();
      const todayFeedbackCount = historyRecords.filter(
        (rec) => isoToLocalDateStr(rec.createdAt, todayStr) === todayStr
      ).length;

      return makeJsonResponse(200, {
        today: todayStr,
        selectedCategory: catParam,
        categories: VALID_MISSION_CATEGORIES.map((id) => ({
          id,
          label: CATEGORY_LABELS[id],
        })),
        mission: chosen,
        vocabSuggestions,
        completedToday: todayFeedbackCount >= 1,
        todayFeedbackCount,
      });
    }

    return makeJsonResponse(404, {
      error: "요청하신 API 경로를 찾을 수 없습니다.",
    });
  }

  // 백업 데이터 내보내기 & 검증 후 복원하기([S3] 보장)
  function exportBackupPayload() {
    return {
      version: 1,
      exportedAt: new Date().toISOString(),
      history: getHistoryRecords(),
      vocab: getVocabItems(),
      routine: getRoutineState(),
    };
  }

  function importBackupPayload(rawObj) {
    if (!rawObj || typeof rawObj !== "object") {
      throw new Error("올바른 백업 파일 형식이 아닙니다(JSON 객체 필요).");
    }
    if (!Array.isArray(rawObj.history)) {
      throw new Error("백업 파일에 첨삭 기록(history) 배열이 없습니다.");
    }
    if (!Array.isArray(rawObj.vocab)) {
      throw new Error("백업 파일에 단어장(vocab) 배열이 없습니다.");
    }
    if (!rawObj.routine || typeof rawObj.routine !== "object") {
      throw new Error("백업 파일에 학습 루틴(routine) 정보가 없습니다.");
    }
    const goal = rawObj.routine.goal || {};
    const fbGoal = goal.dailyFeedbackGoal;
    const rvGoal = goal.dailyReviewGoal;
    if (
      typeof fbGoal !== "number" ||
      !Number.isInteger(fbGoal) ||
      fbGoal < 1 ||
      fbGoal > 20 ||
      typeof rvGoal !== "number" ||
      !Number.isInteger(rvGoal) ||
      rvGoal < 1 ||
      rvGoal > 50
    ) {
      throw new Error(
        "백업 파일의 하루 목표 설정값(첨삭 1~20, 복습 1~50)이 올바르지 않습니다."
      );
    }

    saveHistoryRecords(rawObj.history);
    saveVocabItems(rawObj.vocab);
    saveRoutineState({
      goal: { dailyFeedbackGoal: fbGoal, dailyReviewGoal: rvGoal },
      reviewLogs: Array.isArray(rawObj.routine.reviewLogs)
        ? rawObj.routine.reviewLogs
        : [],
    });

    return {
      historyCount: rawObj.history.length,
      vocabCount: rawObj.vocab.length,
    };
  }

  // 전역 fetch 인터셉터: 모바일 단독 모드이거나 서버 연결 실패 시 온디바이스 엔진으로 즉시 응답
  const originalFetch = window.fetch.bind(window);

  window.fetch = async function (input, init) {
    const reqUrlStr = typeof input === "string" ? input : input.url || "";
    let urlObj = null;
    try {
      urlObj = new URL(reqUrlStr, window.location.origin);
    } catch (_) {
      return originalFetch(input, init);
    }

    if (
      urlObj.origin === window.location.origin &&
      urlObj.pathname.includes("/api/")
    ) {
      const mode = localStorage.getItem(STORAGE_KEYS.MODE) || "standalone";
      if (mode === "standalone") {
        return handleLocalApiRequest(urlObj, init, originalFetch);
      }
      try {
        const serverRes = await originalFetch(input, init);
        return serverRes;
      } catch (_) {
        // 서버가 꺼져 있으면 자동으로 온디바이스 엔진으로 처리
        return handleLocalApiRequest(urlObj, init, originalFetch);
      }
    }

    return originalFetch(input, init);
  };

  window.ImproveEnglishStandalone = {
    getMode() {
      return localStorage.getItem(STORAGE_KEYS.MODE) || "standalone";
    },
    setMode(mode) {
      const next = mode === "server" ? "server" : "standalone";
      localStorage.setItem(STORAGE_KEYS.MODE, next);
      return next;
    },
    hasApiKey() {
      return Boolean((localStorage.getItem(STORAGE_KEYS.API_KEY) || "").trim());
    },
    getMaskedApiKey() {
      const k = (localStorage.getItem(STORAGE_KEYS.API_KEY) || "").trim();
      if (!k) return "";
      if (k.length <= 8) return "********";
      return `${k.slice(0, 4)}••••••••${k.slice(-4)}`;
    },
    saveApiKey(rawKey) {
      const cleaned = (rawKey || "").trim();
      if (!cleaned) {
        localStorage.removeItem(STORAGE_KEYS.API_KEY);
        return false;
      }
      localStorage.setItem(STORAGE_KEYS.API_KEY, cleaned);
      return true;
    },
    clearApiKey() {
      localStorage.removeItem(STORAGE_KEYS.API_KEY);
    },
    exportBackupPayload,
    importBackupPayload,
    getLocalStats() {
      return {
        historyCount: getHistoryRecords().length,
        vocabCount: getVocabItems().length,
      };
    },
  };
})();
