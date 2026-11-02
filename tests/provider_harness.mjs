// 조각 9(ai-provider-choice) 시험 도우미 — `public/standalone-engine.js` 를 Node 에서 가짜 브라우저 저장소로 실제로 돌리고,
// 장면마다 본 것을 JSON 한 줄로 내보낸다. 판정은 `tests/test_ai_provider.py` 가 한다(조각 api-key-vault 의 vault_harness.mjs 와 같은 방식).
import { readFileSync } from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const ENGINE_SRC = readFileSync(path.join(here, "..", "public", "standalone-engine.js"), "utf8");

const KEYS = {
  gemini: "TEST-ONLY-fake-gemini-key-1111111111",
  openai: "TEST-ONLY-fake-openai-key-2222222222",
  anthropic: "TEST-ONLY-fake-anthropic-key-3333333333",
};
const PIN = "2580";
const OTHER_PIN = "9999";

class FakeStorage {
  // failOn: 이 글로 시작하는 이름을 쓰면 저장 공간이 찬 것처럼 예외를 낸다
  constructor(init = {}, failOn = null) {
    this.data = new Map(Object.entries(init));
    this.failOn = failOn;
  }
  getItem(k) {
    return this.data.has(k) ? this.data.get(k) : null;
  }
  setItem(k, v) {
    if (this.failOn && k.startsWith(this.failOn)) {
      const err = new Error("QuotaExceededError");
      err.name = "QuotaExceededError";
      throw err;
    }
    this.data.set(k, String(v));
  }
  removeItem(k) {
    this.data.delete(k);
  }
  dump() {
    return Object.fromEntries(this.data);
  }
}

// 창 하나를 연다 — 같은 local 을 넘기면 같은 기기, 같은 session 을 넘기면 같은 창(새로고침)이다.
function openWindow(local = {}, session = {}, failOn = null) {
  const ctx = {
    // 같은 FakeStorage 를 넘기면 같은 기기의 두 창(탭)이 저장소를 함께 쓴다
    localStorage: local instanceof FakeStorage ? local : new FakeStorage(local, failOn),
    sessionStorage: new FakeStorage(session),
    crypto: globalThis.crypto,
    TextEncoder,
    TextDecoder,
    URL,
    Response,
    console,
    setTimeout,
    clearTimeout,
  };
  ctx.window = ctx;
  ctx.location = { origin: "http://localhost" };
  // 엔진이 밖으로 내보내는 요청(AI 회사)을 남긴다 — PR 3 시험이 「어디로 무엇을 보냈나」를 본다
  const calls = [];
  ctx.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url;
    calls.push({ url, method: init.method || "GET", headers: { ...(init.headers || {}) }, body: init.body || "" });
    if (ctx.aiResponder) return ctx.aiResponder(url, init);
    return new Response("{}", { status: 500 });
  };
  vm.createContext(ctx);
  vm.runInContext(ENGINE_SRC, ctx);
  return { ctx, engine: ctx.ImproveEnglishStandalone, calls };
}

function state(win) {
  const e = win.engine;
  return {
    local: win.ctx.localStorage.dump(),
    session: win.ctx.sessionStorage.dump(),
    provider: e.getProvider(),
    keyStates: Object.fromEntries(["gemini", "openai", "anthropic"].map((p) => [p, e.keyState(p)])),
    isEncrypted: e.isEncrypted(),
    isVaultLocked: e.isVaultLocked(),
    masked: Object.fromEntries(["gemini", "openai", "anthropic"].map((p) => [p, e.getMaskedApiKey(p)])),
  };
}

async function attempt(fn) {
  try {
    return { ok: await fn(), threw: false };
  } catch (_) {
    return { ok: false, threw: true };
  }
}

// 조각 api-key-vault 때 엔진이 만들던 Gemini 금고 값을 따로 만든다(PBKDF2 SHA-256 100000회 → AES-GCM 256) — 새 엔진과 독립된 손으로
async function legacyGeminiVault(rawKey, pin) {
  const enc = new TextEncoder();
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const material = await crypto.subtle.importKey("raw", enc.encode(pin), { name: "PBKDF2" }, false, ["deriveKey"]);
  const key = await crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: 100000, hash: "SHA-256" },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt"]
  );
  const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(rawKey)));
  return {
    ie_gemini_api_key_salt: JSON.stringify(Array.from(salt)),
    ie_gemini_api_key_iv: JSON.stringify(Array.from(iv)),
    ie_gemini_api_key_encrypted: JSON.stringify(Array.from(cipher)),
  };
}

const out = { KEYS, PIN };

// ── P1 고르기 ──
{
  const w = openWindow();
  out.p1Default = state(w);
  const okSet = w.engine.setProvider("anthropic");
  const badSet = w.engine.setProvider("claude");
  const reopened = openWindow(w.ctx.localStorage.dump(), {});
  out.p1Set = { okSet, badSet, after: state(w), reopened: state(reopened) };
  const odd = {};
  for (const raw of ["claude", "", " OpenAI ", "ANTHROPIC", "gpt"]) {
    odd[raw] = openWindow({ ie_ai_provider: raw }).engine.getProvider();
  }
  out.p1Stored = odd;
}

// ── P5 금고 하나 ──
let twoLocked; // gemini · openai 를 PIN 으로 잠근 기기
{
  const w = openWindow();
  const r = await attempt(() => w.engine.saveApiKeyWithPin({ gemini: KEYS.gemini, openai: KEYS.openai, anthropic: "  " }, PIN));
  out.p5SaveTwo = { ...r, ...state(w) };
  twoLocked = w.ctx.localStorage.dump();
}
{
  const w = openWindow(twoLocked, {});
  out.p5Reopened = state(w);
  const wrong = await attempt(() => w.engine.unlockWithPin(OTHER_PIN));
  out.p5WrongUnlock = { ...wrong, ...state(w) };
  const right = await attempt(() => w.engine.unlockWithPin(PIN));
  out.p5RightUnlock = { ...right, ...state(w) };
}
{
  const w = openWindow(twoLocked, {});
  const r = await attempt(() => w.engine.saveApiKeyWithPin({ anthropic: KEYS.anthropic }, ""));
  out.p5NoPinWithLocked = { ...r, before: twoLocked, ...state(w) };
}
{
  const w = openWindow(twoLocked, {});
  const r = await attempt(() => w.engine.saveApiKeyWithPin({ anthropic: KEYS.anthropic }, OTHER_PIN));
  out.p5WrongPinSave = { ...r, before: twoLocked, ...state(w) };
}
{
  const w = openWindow(twoLocked, {});
  const r = await attempt(() => w.engine.saveApiKeyWithPin({ gemini: "TEST-ONLY-new-gemini-4444444444" }, ""));
  out.p5ReplaceOneOfTwoWithoutPin = { ...r, before: twoLocked, ...state(w) };
}
{
  const w = openWindow(twoLocked, {});
  const r = await attempt(() => w.engine.saveApiKeyWithPin({ anthropic: KEYS.anthropic }, PIN));
  out.p5RightPinSave = { ...r, ...state(w) };
  const reopened = openWindow(w.ctx.localStorage.dump(), {});
  const unlock = await attempt(() => reopened.engine.unlockWithPin(PIN));
  out.p5ThreeReopenUnlock = { ...unlock, ...state(reopened) };
}
{
  // 평문 기기에 비밀번호와 함께 저장 → 평문으로 두었던 키도 함께 잠긴다
  const w = openWindow({ ie_gemini_api_key: KEYS.gemini });
  const r = await attempt(() => w.engine.saveApiKeyWithPin({ openai: KEYS.openai }, PIN));
  out.p5LockAlsoPlain = { ...r, ...state(w) };
  // 평문 기기에 비밀번호 없이 저장 → 둘 다 평문
  const w2 = openWindow({ ie_gemini_api_key: KEYS.gemini });
  const r2 = await attempt(() => w2.engine.saveApiKeyWithPin({ openai: KEYS.openai }, ""));
  out.p5PlainPlusPlain = { ...r2, ...state(w2) };
}
{
  const w = openWindow(twoLocked, {});
  const r = await attempt(() => w.engine.saveApiKeyWithPin({ anthropic: KEYS.anthropic }, "12"));
  out.p5ShortPin = { ...r, before: twoLocked, ...state(w) };
  const r2 = await attempt(() => w.engine.saveApiKeyWithPin({ anthropic: "   " }, PIN));
  out.p5NothingFilled = { ...r2, before: twoLocked, ...state(w) };
}
{
  // 저장 공간이 차서 Anthropic 칸 쓰기에서 실패 → 앞서 쓴 Gemini 칸도 되돌린다
  const w = openWindow({}, {}, "ie_anthropic");
  const r = await attempt(() => w.engine.saveApiKeyWithPin({ gemini: KEYS.gemini, anthropic: KEYS.anthropic }, PIN));
  out.p5QuotaRollback = { ...r, ...state(w) };
  const w2 = openWindow({ ...twoLocked }, {}, "ie_anthropic");
  await w2.engine.unlockWithPin(PIN);
  const before = w2.ctx.localStorage.dump();
  const r2 = await attempt(() => w2.engine.saveApiKeyWithPin({ anthropic: KEYS.anthropic }, PIN));
  out.p5QuotaRollbackVault = { ...r2, before, ...state(w2) };
}
{
  // 한 회사 키만 지우기
  const w = openWindow(twoLocked, {});
  await w.engine.unlockWithPin(PIN);
  w.engine.clearApiKey("openai");
  out.p5ClearOne = state(w);
}

// ── P5 겹친 저장(PR 2 리뷰 1회차) ──
{
  // 같은 기기의 두 창이 빈 금고에 서로 다른 비밀번호로 동시에 저장 — 하나만 들어가고, 금고는 그 비밀번호 하나로 열린다
  const shared = new FakeStorage();
  const tabA = openWindow(shared);
  const tabB = openWindow(shared);
  const results = await Promise.all([
    attempt(() => tabA.engine.saveApiKeyWithPin({ gemini: KEYS.gemini }, PIN)),
    attempt(() => tabB.engine.saveApiKeyWithPin({ openai: KEYS.openai }, OTHER_PIN)),
  ]);
  const unlockPin = await attempt(() => openWindow(shared.dump(), {}).engine.unlockWithPin(PIN));
  const unlockOther = await attempt(() => openWindow(shared.dump(), {}).engine.unlockWithPin(OTHER_PIN));
  out.p5RaceTwoTabs = { results, unlockPin, unlockOther, local: shared.dump() };
}
{
  // 한 창에서 저장을 겹쳐 누름 — 다른 비밀번호면 뒤의 것이 거절되고, 같은 비밀번호면 둘 다 한 금고에 들어간다
  const w = openWindow();
  const diff = await Promise.all([
    attempt(() => w.engine.saveApiKeyWithPin({ gemini: KEYS.gemini }, PIN)),
    attempt(() => w.engine.saveApiKeyWithPin({ openai: KEYS.openai }, OTHER_PIN)),
  ]);
  const diffUnlock = await attempt(() => openWindow(w.ctx.localStorage.dump(), {}).engine.unlockWithPin(PIN));
  out.p5RaceSameTabDiffPin = { results: diff, unlock: diffUnlock, local: w.ctx.localStorage.dump() };
  const w2 = openWindow();
  const same = await Promise.all([
    attempt(() => w2.engine.saveApiKeyWithPin({ gemini: KEYS.gemini }, PIN)),
    attempt(() => w2.engine.saveApiKeyWithPin({ openai: KEYS.openai }, PIN)),
  ]);
  const reopened = openWindow(w2.ctx.localStorage.dump(), {});
  const sameUnlock = await attempt(() => reopened.engine.unlockWithPin(PIN));
  out.p5RaceSameTabSamePin = { results: same, unlock: sameUnlock, ...state(reopened) };
}

// ── P6 옛 Gemini 키 그대로 ──
{
  const legacy = await legacyGeminiVault(KEYS.gemini, PIN);
  const w = openWindow({ ...legacy }, {});
  const lockedState = state(w);
  const unlock = await attempt(() => w.engine.unlockWithPin(PIN));
  out.p6Legacy = { before: legacy, lockedState, ...unlock, ...state(w) };
  const plain = openWindow({ ie_gemini_api_key: KEYS.gemini });
  out.p6LegacyPlain = state(plain);
  // 옛 Gemini 금고에 새 회사 키를 같은 비밀번호로 더하기
  const w2 = openWindow({ ...legacy }, {});
  const add = await attempt(() => w2.engine.saveApiKeyWithPin({ openai: KEYS.openai }, PIN));
  out.p6LegacyAdd = { ...add, before: legacy, ...state(w2) };
}

// ── P7 백업 · 화면에 가린 키 ──
{
  const w = openWindow(twoLocked, {});
  await w.engine.unlockWithPin(PIN);
  await w.engine.saveApiKeyWithPin({ anthropic: KEYS.anthropic }, PIN);
  w.engine.setProvider("openai");
  out.p7 = { backupText: JSON.stringify(w.engine.exportBackupPayload()), ...state(w) };
}


// ── PR 3 폰 앱 호출 — 첨삭 · 퀴즈 AI 를 고른 회사로(P2 · P3 · P4 · P7 · P9) ──
const PROVIDER_IDS = ["gemini", "openai", "anthropic"];
const FEEDBACK = {
  corrected: "I'd like to get off work early today.",
  explanation: "'퇴근하다'는 'get off work' 로 씁니다.",
  alternatives: [
    { expression: "I'm hoping to head out early today.", nuance: "부드럽게 양해를 구할 때" },
    { expression: "Could I leave a bit early today?", nuance: "허락을 구할 때" },
  ],
  keyExpressions: [{ expression: "get off work", meaning: "퇴근하다", example: "I get off work at six." }],
};
const QUIZ_WORDS = [
  "give up", "look forward to", "run into", "figure out", "put off", "come up with",
  "get along", "hang out", "catch up", "turn down", "bring up",
];
const VOCAB = QUIZ_WORDS.map((expression, i) => ({
  id: `v-${i}`,
  expression,
  meaning: `뜻 ${i}`,
  example: "",
  box: 0,
  reviewCount: 0,
  nextReviewDate: "2026-10-01",
  createdAt: "2026-10-01T00:00:00Z",
  lastReviewedAt: null,
}));
const quizItem = (expression) => ({
  question: "I really want to ____ this habit.",
  choices: [expression, "take after", "look into", "run out of"],
  answerIndex: 0,
  explanation: "정답 표현이 문장의 뜻에 맞는다.",
  expression,
  meaning: "뜻",
  example: `I really want to ${expression} this habit.`,
});
const QUIZ_REPLY = { questions: [quizItem("give up"), quizItem("figure out"), quizItem("put off")] };

// 회사마다의 응답 꼴로 JSON 글을 싼다(③ 의 꺼내는 자리)
function wrap(provider, text, overrides = {}) {
  if (provider === "openai") {
    return { choices: [{ message: { role: "assistant", content: text, refusal: null, ...overrides } }] };
  }
  if (provider === "anthropic") {
    return {
      content: [
        { type: "thinking", thinking: "짧게 생각한다", signature: "sig" },
        { type: "text", text },
      ],
      stop_reason: "end_turn",
      ...overrides,
    };
  }
  return { candidates: [{ content: { parts: [{ text }] } }] };
}
const okReply = (provider, payload) => new Response(JSON.stringify(wrap(provider, JSON.stringify(payload))), { status: 200 });
const isQuizCall = (init) => String(init.body || "").includes("퀴즈 출제자");

// 세 회사 키를 모두 평문으로 넣은 기기에서 provider 를 고른 창
function aiWindow(provider, { keys = KEYS, extra = {} } = {}) {
  const local = { ie_ai_provider: provider, ie_vocab_items_v1: JSON.stringify(VOCAB), ...extra };
  for (const p of PROVIDER_IDS) if (keys[p]) local[`ie_${p}_api_key`] = keys[p];
  return openWindow(local, {});
}
async function api(win, method, url, body) {
  const init = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) init.body = JSON.stringify(body);
  const res = await win.ctx.window.fetch(url, init);
  return { status: res.status, body: await res.json() };
}
const feedbackOf = (win) => api(win, "POST", "/api/feedback", { text: "오늘 일찍 퇴근하다 하고 싶어요", inputMode: "text" });
const quizOf = (win) => api(win, "POST", "/api/quiz/today");
const quizSummary = (res) => ({
  status: res.status,
  aiCount: res.body.aiCount,
  aiNotice: res.body.aiNotice || null,
  sources: res.body.quiz ? res.body.quiz.questions.map((q) => q.source) : null,
  aiExpressions: res.body.quiz ? res.body.quiz.questions.filter((q) => q.source === "ai").map((q) => q.expression) : [],
});

// P2 · P3 · P7 — 회사마다 성공: 첨삭과 퀴즈가 고른 회사 하나로만 간다
out.pr3Success = {};
for (const provider of PROVIDER_IDS) {
  const w = aiWindow(provider);
  w.ctx.aiResponder = async (url, init) => okReply(provider, isQuizCall(init) ? QUIZ_REPLY : FEEDBACK);
  const fb = await feedbackOf(w);
  const qz = await quizOf(w);
  out.pr3Success[provider] = {
    feedback: fb,
    quiz: quizSummary(qz),
    calls: w.calls,
    history: w.ctx.localStorage.getItem("ie_feedback_history_v1"),
    quizStored: w.ctx.localStorage.getItem("ie_quiz_v1"),
    backupText: JSON.stringify(w.engine.exportBackupPayload()),
  };
}

// P2 — 모델 후보: 그 회사 안에서만 다음 후보로 넘어간다(OpenAI 첫 모델 404 → 둘째)
{
  const w = aiWindow("openai");
  w.ctx.aiResponder = async (url, init) =>
    JSON.parse(init.body).model === "gpt-5.4-mini"
      ? new Response('{"error":{"message":"model not found"}}', { status: 404 })
      : okReply("openai", FEEDBACK);
  const fb = await feedbackOf(w);
  out.pr3OpenAiFallback = { feedback: fb, calls: w.calls };
}

// P4 — 실패하면 지금처럼(첨삭 = 내장 코치, 퀴즈 = 내 기록 + 지금의 안내). 다른 회사를 부르지 않는다
const FAILURES = {
  http429: () => new Response('{"error":{"message":"rate limited"}}', { status: 429 }),
  http402: () => new Response('{"error":{"message":"billing"}}', { status: 402 }),
  http500: () => new Response("{}", { status: 500 }),
  network: () => {
    throw new TypeError("Failed to fetch"); // 오프라인 · 브라우저 직접 호출 막힘(CORS)
  },
  notJson: (provider) => new Response(JSON.stringify(wrap(provider, "not json")), { status: 200 }),
  badShape: (provider, init) =>
    new Response(
      JSON.stringify(
        wrap(provider, JSON.stringify(isQuizCall(init) ? { questions: [] } : { ...FEEDBACK, alternatives: [FEEDBACK.alternatives[0]] }))
      ),
      { status: 200 }
    ),
  wrongForm: () => new Response(JSON.stringify({ unexpected: true }), { status: 200 }),
  // 닫기 전 감사 NC-15 — 대체 표현 4개 · 핵심 표현 칸이 빈 글이면 서버처럼 거절한다
  tooManyAlternatives: (provider, init) =>
    new Response(
      JSON.stringify(
        wrap(
          provider,
          JSON.stringify(
            isQuizCall(init)
              ? { questions: [] }
              : {
                  ...FEEDBACK,
                  alternatives: [...FEEDBACK.alternatives, ...FEEDBACK.alternatives].map((a, i) => ({ ...a, expression: `${a.expression} ${i}` })),
                }
          )
        )
      ),
      { status: 200 }
    ),
  emptyKeyField: (provider, init) =>
    new Response(
      JSON.stringify(
        wrap(
          provider,
          JSON.stringify(
            isQuizCall(init)
              ? { questions: [] }
              : { ...FEEDBACK, keyExpressions: [{ expression: "get off work", meaning: "  ", example: "I get off work at six." }] }
          )
        )
      ),
      { status: 200 }
    ),
};
const PROVIDER_FAILURES = {
  openaiRefusal: ["openai", (p, init) => new Response(JSON.stringify(wrap("openai", JSON.stringify(isQuizCall(init) ? QUIZ_REPLY : FEEDBACK), { refusal: "I can't help with that." })), { status: 200 })],
  anthropicMaxTokens: ["anthropic", (p, init) => new Response(JSON.stringify(wrap("anthropic", JSON.stringify(isQuizCall(init) ? QUIZ_REPLY : FEEDBACK), { stop_reason: "max_tokens" })), { status: 200 })],
  anthropicRefusal: ["anthropic", (p, init) => new Response(JSON.stringify(wrap("anthropic", JSON.stringify(isQuizCall(init) ? QUIZ_REPLY : FEEDBACK), { stop_reason: "refusal" })), { status: 200 })],
  anthropicNoText: ["anthropic", () => new Response(JSON.stringify({ content: [{ type: "thinking", thinking: "..." }], stop_reason: "end_turn" }), { status: 200 })],
};
async function failScene(provider, responder) {
  const w = aiWindow(provider);
  w.ctx.aiResponder = async (url, init) => responder(provider, init);
  const fb = await feedbackOf(w);
  const qz = await quizOf(w);
  return { feedback: fb, quiz: quizSummary(qz), calls: w.calls.map((c) => c.url) };
}
out.pr3Failures = {};
for (const provider of PROVIDER_IDS) {
  for (const [name, responder] of Object.entries(FAILURES)) {
    out.pr3Failures[`${provider}:${name}`] = await failScene(provider, responder);
  }
}
for (const [name, [provider, responder]] of Object.entries(PROVIDER_FAILURES)) {
  out.pr3Failures[`${provider}:${name}`] = await failScene(provider, responder);
}

// P3 — 검사를 지난 응답은 서버처럼 앞뒤 공백을 지우고 정해진 칸만 남겨 기록한다(닫기 전 감사 NC-15)
{
  const messy = {
    corrected: `  ${FEEDBACK.corrected}  `,
    explanation: FEEDBACK.explanation,
    alternatives: FEEDBACK.alternatives.map((a) => ({ ...a, nuance: ` ${a.nuance} `, extra: "버릴 칸" })),
    keyExpressions: FEEDBACK.keyExpressions,
    provider: "openai",
  };
  const w = aiWindow("openai");
  w.ctx.aiResponder = async () => okReply("openai", messy);
  const fb = await feedbackOf(w);
  out.pr3Normalized = { feedback: fb, expected: FEEDBACK, history: w.ctx.localStorage.getItem("ie_feedback_history_v1") };
}

// P4 — 고른 회사의 키가 없거나 잠겨 있으면 아무 데도 부르지 않는다(다른 두 회사 키는 있다)
out.pr3NoKey = {};
for (const provider of PROVIDER_IDS) {
  const others = { ...KEYS, [provider]: "" };
  const w = aiWindow(provider, { keys: others });
  w.ctx.aiResponder = async (url, init) => okReply(provider, isQuizCall(init) ? QUIZ_REPLY : FEEDBACK);
  const fb = await feedbackOf(w);
  const qz = await quizOf(w);
  out.pr3NoKey[provider] = { feedback: fb, quiz: quizSummary(qz), calls: w.calls.map((c) => c.url) };
}
{
  // 잠긴 금고(gemini · openai) — openai 를 고르고 풀지 않은 창은 부르지 않고, 푼 창은 openai 로 간다
  const w = openWindow({ ...twoLocked, ie_ai_provider: "openai", ie_vocab_items_v1: JSON.stringify(VOCAB) }, {});
  w.ctx.aiResponder = async (url, init) => okReply("openai", isQuizCall(init) ? QUIZ_REPLY : FEEDBACK);
  const lockedFb = await feedbackOf(w);
  const lockedCalls = w.calls.length;
  await w.engine.unlockWithPin(PIN);
  const unlockedFb = await feedbackOf(w);
  out.pr3Locked = { lockedFb, lockedCalls, unlockedFb, calls: w.calls };
}

process.stdout.write(JSON.stringify(out));
