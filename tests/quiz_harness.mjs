// 조각 8(review-quiz) 시험 도우미 — `public/standalone-engine.js` 를 Node 에서 가짜 브라우저 저장소 · 가짜 시계로 실제로 돌리고,
// 장면마다 본 것을 JSON 한 줄로 내보낸다. 판정은 `tests/test_quiz.py` 가 한다.
import { readFileSync } from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const ENGINE_SRC = readFileSync(path.join(here, "..", "public", "standalone-engine.js"), "utf8");
const QUIZ_KEY = "ie_quiz_v1";

class FakeStorage {
  constructor(init = {}) {
    this.data = new Map(Object.entries(init));
  }
  getItem(k) {
    return this.data.has(k) ? this.data.get(k) : null;
  }
  setItem(k, v) {
    if (this.failKey && k === this.failKey) throw new Error("QuotaExceededError");
    this.data.set(k, String(v));
  }
  removeItem(k) {
    this.data.delete(k);
  }
  dump() {
    return Object.fromEntries(this.data);
  }
}

// 지역 날짜를 바꿀 수 있는 시계 — 인자 없는 new Date() 만 가짜 시각을 쓴다.
function makeClock(isoLocal) {
  const clock = { now: new Date(isoLocal).getTime() };
  const RealDate = Date;
  class FakeDate extends RealDate {
    constructor(...args) {
      if (args.length === 0) super(clock.now);
      else super(...args);
    }
    static now() {
      return clock.now;
    }
  }
  clock.Date = FakeDate;
  clock.set = (iso) => {
    clock.now = new RealDate(iso).getTime();
  };
  return clock;
}

function openWindow(local, clock) {
  const calls = [];
  const ctx = {
    // FakeStorage 를 그대로 넘기면 같은 기기의 다른 탭이다(저장소를 나눠 씀)
    localStorage: local instanceof FakeStorage ? local : new FakeStorage(local),
    sessionStorage: new FakeStorage({}),
    crypto: globalThis.crypto,
    TextEncoder,
    TextDecoder,
    URL,
    Response,
    console,
    setTimeout,
    clearTimeout,
    Date: clock.Date,
  };
  ctx.window = ctx;
  ctx.location = { origin: "http://localhost" };
  ctx.fetch = async (input, init) => {
    const url = typeof input === "string" ? input : input.url;
    const headers = (init && init.headers) || {};
    calls.push({ url, apiKeyHeader: headers["x-goog-api-key"] || null, body: (init && init.body) || "" });
    if (ctx.serverDown) throw new TypeError("Failed to fetch");
    if (url.includes("generativelanguage") && ctx.aiResponder) return ctx.aiResponder(url, init);
    return new Response("{}", { status: 500 });
  };
  vm.createContext(ctx);
  vm.runInContext(ENGINE_SRC, ctx);
  return { ctx, calls };
}

async function call(win, method, url, body) {
  const init = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) init.body = typeof body === "string" ? body : JSON.stringify(body);
  const res = await win.ctx.window.fetch(url, init);
  return { status: res.status, body: await res.json() };
}

const WORDS = [
  ["give up", "포기하다", "Don't give up."],
  ["look forward to", "~을 고대하다", ""],
  ["run into", "우연히 만나다", ""],
  ["figure out", "알아내다", ""],
  ["put off", "미루다", ""],
  ["come up with", "생각해 내다", ""],
  ["get along", "잘 지내다", ""],
  ["hang out", "어울려 놀다", ""],
  ["catch up", "따라잡다", ""],
  ["turn down", "거절하다", ""],
  ["bring up", "꺼내다", ""],
];

function vocab(n, nextReviewDate = "2026-10-01") {
  return WORDS.slice(0, n).map(([expression, meaning, example], i) => ({
    id: `v-${i}`,
    expression,
    meaning,
    example,
    box: 0,
    reviewCount: 0,
    nextReviewDate,
    createdAt: "2026-10-01T00:00:00Z",
    lastReviewedAt: null,
  }));
}

const HISTORY = [
  {
    id: "fb-1",
    createdAt: "2026-10-29T01:00:00Z",
    text: "I am looking forward to meet you.",
    inputMode: "text",
    feedback: {
      corrected: "I am looking forward to meeting you.",
      explanation: "look forward to 뒤에는 동명사(-ing)가 온다.",
      alternatives: [
        { expression: "I can't wait to meet you.", nuance: "더 가벼운 말" },
        { expression: "I'm excited to meet you.", nuance: "설렘" },
      ],
      keyExpressions: [
        { expression: "looking forward to", meaning: "~을 기대하는 중이다", example: "I'm looking forward to it." },
      ],
    },
  },
];

function device(nVocab, withHistory, nextReviewDate) {
  const local = { ie_vocab_items_v1: JSON.stringify(vocab(nVocab, nextReviewDate)) };
  if (withHistory) local.ie_feedback_history_v1 = JSON.stringify(HISTORY);
  return local;
}

const out = {};

// 표현 4개 · 첨삭 없음 — 열지 않고 저장하지 않는다([Q2])
{
  const clock = makeClock("2026-10-30T09:00:00");
  const before = device(4, false);
  const w = openWindow(before, clock);
  const res = await call(w, "POST", "/api/quiz/today");
  out.notEnough = { res, before, after: w.ctx.localStorage.dump() };
}

// 표현 5개 — 딱 5문제로 열린다([Q2] 경계)
{
  const clock = makeClock("2026-10-30T09:00:00");
  const w = openWindow(device(5, false), clock);
  out.five = await call(w, "POST", "/api/quiz/today");
}

// 단어장 11개 + 첨삭 1건 — 10문제, 같은 날 같은 세트, GET 은 만들지 않는다([Q1] · [Q3] · [Q4])
{
  const clock = makeClock("2026-10-30T09:00:00");
  const w = openWindow(device(11, true), clock);
  const getBefore = await call(w, "GET", "/api/quiz/today");
  const storedAfterGet = w.ctx.localStorage.getItem(QUIZ_KEY);
  const first = await call(w, "POST", "/api/quiz/today");
  const second = await call(w, "POST", "/api/quiz/today");
  const getAfter = await call(w, "GET", "/api/quiz/today");
  const quiz = first.body.quiz;
  const right = quiz.questions.map((q) => q.answerIndex);
  const oneWrong = right.slice();
  oneWrong[0] = (oneWrong[0] + 1) % 4;
  const attemptWrong = await call(w, "POST", "/api/quiz/attempt", { date: quiz.date, quizId: quiz.id, answers: oneWrong });
  const attemptRight = await call(w, "POST", "/api/quiz/attempt", { date: quiz.date, quizId: quiz.id, answers: right });
  const getScored = await call(w, "GET", "/api/quiz/today");
  const snapshot = w.ctx.localStorage.dump();

  // 거절 꼴 — 저장 내용이 거절 전과 같아야 한다([Q5])
  const badBodies = {
    notJson: "{bad",
    notObject: [1, 2],
    badDate: { date: "2026/10/30", quizId: quiz.id, answers: right },
    impossibleDate: { date: "2026-02-30", quizId: quiz.id, answers: right },
    noAnswers: { date: quiz.date, quizId: quiz.id, answers: [] },
    answersNotList: { date: quiz.date, quizId: quiz.id, answers: "0123" },
    tooFew: { date: quiz.date, quizId: quiz.id, answers: right.slice(0, 9) },
    tooMany: { date: quiz.date, quizId: quiz.id, answers: [...right, 0] },
    outOfRange: { date: quiz.date, quizId: quiz.id, answers: right.map(() => 4) },
    negative: { date: quiz.date, quizId: quiz.id, answers: right.map(() => -1) },
    notInt: { date: quiz.date, quizId: quiz.id, answers: right.map(() => 1.5) },
    boolean: { date: quiz.date, quizId: quiz.id, answers: right.map(() => true) },
    otherDate: { date: "2026-10-29", quizId: quiz.id, answers: right },
    noQuizId: { date: quiz.date, answers: right },
    blankQuizId: { date: quiz.date, quizId: "  ", answers: right },
    otherQuiz: { date: quiz.date, quizId: "quiz-from-another-store", answers: right },
  };
  const rejects = {};
  for (const [name, body] of Object.entries(badBodies)) {
    const res = await call(w, "POST", "/api/quiz/attempt", body);
    rejects[name] = { status: res.status, body: res.body, unchanged: JSON.stringify(w.ctx.localStorage.dump()) === JSON.stringify(snapshot) };
  }
  out.full = { getBefore, storedAfterGet, first, second, getAfter, attemptWrong, attemptRight, getScored, rejects, geminiCalls: w.calls.length };
}

// 복습 예정 단어가 없으면 첨삭 핵심 표현이 앞에 오고, 교정 문장으로 빈칸 문제가 나온다(설계 ③ 순서 · blank)
{
  const clock = makeClock("2026-10-30T09:00:00");
  const w = openWindow(device(11, true, "2026-12-01"), clock);
  out.blank = await call(w, "POST", "/api/quiz/today");
}

// 같은 표현이 첨삭 기록과 (복습 예정이 아닌) 단어장에 다 있으면 자리는 첨삭 쪽이어도 뜻 · 예문은 단어장 것(설계 ③)
{
  const clock = makeClock("2026-10-30T09:00:00");
  const local = device(10, true, "2026-12-01");
  const items = JSON.parse(local.ie_vocab_items_v1);
  items.push({ ...items[0], id: "v-dup", expression: "Looking forward to", meaning: "단어장에 적은 뜻", example: "단어장 예문" });
  local.ie_vocab_items_v1 = JSON.stringify(items);
  const w = openWindow(local, clock);
  out.vocabWins = await call(w, "POST", "/api/quiz/today");
}

// 서버 모드에서 서버 세트를 풀다 서버가 끊겨 제출이 엔진으로 넘어옴 — 기기에도 같은 날짜 · 같은 문제 수의 다른 세트가 있다
{
  const clock = makeClock("2026-10-30T09:00:00");
  const w = openWindow(device(11, true), clock);
  const local = (await call(w, "POST", "/api/quiz/today")).body.quiz;
  const serverQuiz = { ...local, id: "quiz-server-side", questions: local.questions.map((q) => ({ ...q, answerIndex: (q.answerIndex + 1) % 4 })) };
  w.ctx.localStorage.setItem("ie_standalone_mode", "server");
  w.ctx.serverDown = true; // 서버 연결이 끊김 — 엔진의 fetch 가로채기가 온디바이스 엔진으로 넘긴다
  const before = w.ctx.localStorage.dump();
  const res = await call(w, "POST", "/api/quiz/attempt", { date: serverQuiz.date, quizId: serverQuiz.id, answers: serverQuiz.questions.map((q) => q.answerIndex) });
  out.fallback = { res, unchanged: JSON.stringify(w.ctx.localStorage.dump()) === JSON.stringify(before) };
}

// 날짜 넘김 ① — 세트 A 를 만든 뒤 날짜를 넘겨 A 의 답안을 내면 A 의 날짜로 남는다
{
  const clock = makeClock("2026-10-30T23:55:00");
  const w = openWindow(device(11, true), clock);
  const a = (await call(w, "POST", "/api/quiz/today")).body.quiz;
  clock.set("2026-10-31T00:05:00");
  const res = await call(w, "POST", "/api/quiz/attempt", { date: a.date, quizId: a.id, answers: a.questions.map((q) => q.answerIndex) });
  const getNext = await call(w, "GET", "/api/quiz/today");
  out.rolloverKeep = { aDate: a.date, res, getNext };
}

// 날짜 넘김 ② — 세트 A, 날짜를 넘겨 새 세트 B 를 만든 뒤 A 의 답안을 내면 거절되고 저장 내용이 그대로다
{
  const clock = makeClock("2026-10-30T23:55:00");
  const w = openWindow(device(11, true), clock);
  const a = (await call(w, "POST", "/api/quiz/today")).body.quiz;
  clock.set("2026-10-31T00:05:00");
  const b = (await call(w, "POST", "/api/quiz/today")).body;
  const before = w.ctx.localStorage.dump();
  const res = await call(w, "POST", "/api/quiz/attempt", { date: a.date, quizId: a.id, answers: a.questions.map((q) => q.answerIndex) });
  out.rolloverReplaced = {
    aDate: a.date,
    bDate: b.quiz.date,
    bCreated: b.created,
    aIdsInB: a.questions.filter((q) => b.quiz.questions.some((x) => x.id === q.id)).length,
    res,
    unchanged: JSON.stringify(w.ctx.localStorage.dump()) === JSON.stringify(before),
  };
}

// 망가진 저장 값 — 퀴즈 칸이 깨져 있으면 세트 없음으로 보고 새로 만든다
{
  const clock = makeClock("2026-10-30T09:00:00");
  const local = device(11, true);
  local[QUIZ_KEY] = JSON.stringify({ today: { date: "2026-10-30", createdAt: "x", questions: [{ id: "bad" }] }, scores: [{ date: "nope" }] });
  const w = openWindow(local, clock);
  const getRes = await call(w, "GET", "/api/quiz/today");
  const postRes = await call(w, "POST", "/api/quiz/today");
  out.corrupt = { getRes, postRes };
}

// 저장 공간이 꽉 찬 기기 — 세트를 저장하지 못하면 열지 않고, 점수를 저장하지 못하면 기록했다고 하지 않는다([Q4] · [Q6])
{
  const clock = makeClock("2026-10-30T09:00:00");
  const w = openWindow(device(11, true), clock);
  w.ctx.localStorage.failKey = QUIZ_KEY;
  const createRes = await call(w, "POST", "/api/quiz/today");
  const afterCreate = w.ctx.localStorage.dump();
  w.ctx.localStorage.failKey = null;
  const quiz = (await call(w, "POST", "/api/quiz/today")).body.quiz;
  const beforeAttempt = w.ctx.localStorage.dump();
  w.ctx.localStorage.failKey = QUIZ_KEY;
  const attemptRes = await call(w, "POST", "/api/quiz/attempt", { date: quiz.date, quizId: quiz.id, answers: quiz.questions.map((q) => q.answerIndex) });
  w.ctx.localStorage.failKey = null;
  const getAfter = await call(w, "GET", "/api/quiz/today");
  out.storageFull = {
    createRes,
    createStored: QUIZ_KEY in afterCreate,
    attemptRes,
    attemptUnchanged: JSON.stringify(w.ctx.localStorage.dump()) === JSON.stringify(beforeAttempt),
    scoreAfter: getAfter.body.score,
  };
}

// ── PR 2: AI 새 문제 ─────────────────────────────────────────────
const KEY = "TEST-ONLY-fake-gemini-key-quiz-0000";
const aiItem = (expression, overrides = {}) => ({
  question: `I really want to ____ this habit.`,
  choices: [expression, "take after", "look into", "run out of"],
  answerIndex: 0,
  explanation: "정답 표현이 문장의 뜻에 맞는다.",
  expression,
  meaning: "뜻",
  example: `I really want to ${expression} this habit.`,
  ...overrides,
});
const geminiReply = (items) =>
  new Response(JSON.stringify({ candidates: [{ content: { parts: [{ text: JSON.stringify({ questions: items }) }] } }] }), { status: 200 });

async function aiScene({ items, key = KEY, status = 200, local: extra = {}, responder = null }) {
  const clock = makeClock("2026-10-30T09:00:00");
  const local = { ...device(11, true), ...extra };
  if (key) local.ie_gemini_api_key = key;
  const w = openWindow(local, clock);
  w.ctx.aiResponder = responder || (async () => (status === 200 ? geminiReply(items) : new Response("{}", { status })));
  const first = await call(w, "POST", "/api/quiz/today");
  const second = await call(w, "POST", "/api/quiz/today");
  const aiCalls = w.calls.filter((c) => c.url.includes("generativelanguage"));
  return { w, first, second, aiCalls };
}

// AI 3개 — 하나는 내 기록에도 있는 표현(give up): 내 기록 쪽에서 빠져야 한다
{
  const { w, first, second, aiCalls } = await aiScene({ items: [aiItem("give up"), aiItem("put up with"), aiItem("cut down on")] });
  const q = first.body.quiz.questions.find((x) => x.source === "ai" && x.expression === "put up with");
  const save1 = await call(w, "POST", "/api/vocab", { expression: q.expression, meaning: q.meaning, example: q.example });
  const save2 = await call(w, "POST", "/api/vocab", { expression: q.expression, meaning: q.meaning, example: q.example });
  out.aiOk = {
    first,
    second,
    aiCalls: aiCalls.map((c) => ({ url: c.url, apiKeyHeader: c.apiKeyHeader, body: c.body })),
    KEY,
    save1,
    save2,
  };
}

// AI 0 ~ 3개마다 내 기록으로 채워 10문제(Q1 AI 부분)
{
  const pool = ["put up with", "cut down on", "get rid of"];
  out.aiCounts = {};
  for (let n = 0; n <= 3; n += 1) {
    const { first } = await aiScene({ items: pool.slice(0, n).map((e) => aiItem(e)) });
    out.aiCounts[n] = {
      total: first.body.quiz.questions.length,
      ai: first.body.quiz.questions.filter((x) => x.source === "ai").length,
      aiCount: first.body.aiCount,
      aiNotice: first.body.aiNotice || null,
    };
  }
}

// 실패 · 키 없음 · 금고 잠김 — 내 기록으로 10문제와 안내(Q9)
{
  const failed = await aiScene({ items: [], status: 500 });
  const noKey = await aiScene({ items: [aiItem("put up with")], key: null });
  const locked = await aiScene({
    items: [aiItem("put up with")],
    key: null,
    local: { ie_gemini_api_key_encrypted: "[1,2,3]", ie_gemini_api_key_salt: "[1]", ie_gemini_api_key_iv: "[1]" },
  });
  const pick = (r) => ({ total: r.first.body.quiz.questions.length, aiNotice: r.first.body.aiNotice || null, aiCalls: r.aiCalls.length, bodyText: JSON.stringify(r.first.body) });
  out.aiFailed = { ...pick(failed), KEY };
  out.aiNoKey = pick(noKey);
  out.aiLocked = pick(locked);
}

// ③ AI 응답 — 꼴마다 그 문제만 버린다(좋은 문제 하나와 함께 보내 1개만 남는지)
{
  const bad = {
    choicesThree: aiItem("cut down on", { choices: ["cut down on", "a", "b"] }),
    choicesFive: aiItem("cut down on", { choices: ["cut down on", "a", "b", "c", "d"] }),
    choicesDuplicate: aiItem("cut down on", { choices: ["cut down on", "Cut  down on", "b", "c"] }),
    choiceTooLong: aiItem("cut down on", { choices: ["cut down on", "x".repeat(201), "b", "c"] }),
    answerOutOfRange: aiItem("cut down on", { answerIndex: 4 }),
    answerBoolean: aiItem("cut down on", { answerIndex: true }),
    answerString: aiItem("cut down on", { answerIndex: "0" }),
    answerNotExpression: aiItem("cut down on", { answerIndex: 1 }),
    noBlank: aiItem("cut down on", { question: "I really want to cut down on this habit." }),
    questionTooLong: aiItem("cut down on", { question: "____ " + "x".repeat(300) }),
    questionEmpty: aiItem("cut down on", { question: "" }),
    explanationEmpty: aiItem("cut down on", { explanation: " " }),
    explanationTooLong: aiItem("cut down on", { explanation: "가".repeat(501) }),
    expressionTooLong: aiItem("x".repeat(201)),
    meaningEmpty: aiItem("cut down on", { meaning: "" }),
    meaningTooLong: aiItem("cut down on", { meaning: "가".repeat(301) }),
    exampleTooLong: aiItem("cut down on", { example: "x".repeat(501) }),
    missingField: (() => { const it = aiItem("cut down on"); delete it.explanation; return it; })(),
    duplicateTarget: aiItem("Put Up With"),
    notObject: "question",
  };
  out.aiBad = {};
  for (const [name, item] of Object.entries(bad)) {
    const { first } = await aiScene({ items: [aiItem("put up with"), item] });
    out.aiBad[name] = first.body.quiz.questions.filter((x) => x.source === "ai").length;
  }
  const four = await aiScene({ items: ["put up with", "cut down on", "get rid of", "make up for"].map((e) => aiItem(e)) });
  out.aiBad.moreThanThree = four.first.body.quiz.questions.filter((x) => x.source === "ai").length;
  const garbled = await aiScene({
    items: [],
    responder: async () => new Response(JSON.stringify({ candidates: [{ content: { parts: [{ text: "not json" }] } }] }), { status: 200 }),
  });
  out.aiBad.unparsable = {
    ai: garbled.first.body.quiz.questions.filter((x) => x.source === "ai").length,
    total: garbled.first.body.quiz.questions.length,
    aiNotice: garbled.first.body.aiNotice || null,
  };
}

// 겹친 [퀴즈 시작] — 같은 화면이면 만들기 하나를 함께 기다려 AI 한 번 · 세트 하나([Q4] · [Q9])
{
  const clock = makeClock("2026-10-30T09:00:00");
  const local = device(11, true);
  local.ie_gemini_api_key = KEY;
  const w = openWindow(local, clock);
  w.ctx.aiResponder = async () => {
    await new Promise((r) => setTimeout(r, 50));
    return geminiReply([aiItem("put up with")]);
  };
  const [a, b] = await Promise.all([call(w, "POST", "/api/quiz/today"), call(w, "POST", "/api/quiz/today")]);
  const stored = JSON.parse(w.ctx.localStorage.getItem(QUIZ_KEY)).today.id;
  out.concurrentSameTab = {
    sameSet: a.body.quiz.id === b.body.quiz.id,
    storedIsThatSet: stored === a.body.quiz.id,
    aiCalls: w.calls.filter((c) => c.url.includes("generativelanguage")).length,
  };
}

// 두 탭 — 탭 A 가 AI 를 기다리는 사이 탭 B 가 세트를 만들고 점수까지 냈다. A 는 B 의 세트를 돌려받고 점수를 덮지 않는다([Q4] · [Q6])
{
  const clock = makeClock("2026-10-30T09:00:00");
  const local = device(11, true);
  local.ie_gemini_api_key = KEY;
  const shared = new FakeStorage(local);
  const tabA = openWindow(shared, clock);
  const tabB = openWindow(shared, clock);
  let release;
  const gate = new Promise((r) => {
    release = r;
  });
  tabA.ctx.aiResponder = async () => {
    await gate;
    return geminiReply([aiItem("put up with")]);
  };
  tabB.ctx.aiResponder = async () => new Response("{}", { status: 500 });
  const pendingA = call(tabA, "POST", "/api/quiz/today");
  await new Promise((r) => setTimeout(r, 20));
  const bQuiz = (await call(tabB, "POST", "/api/quiz/today")).body.quiz;
  const bAttempt = await call(tabB, "POST", "/api/quiz/attempt", { date: bQuiz.date, quizId: bQuiz.id, answers: bQuiz.questions.map((q) => q.answerIndex) });
  release();
  const aRes = await pendingA;
  const after = JSON.parse(shared.getItem(QUIZ_KEY));
  out.concurrentTwoTabs = {
    bAttemptStatus: bAttempt.status,
    aCreated: aRes.body.created,
    aGotBSet: aRes.body.quiz.id === bQuiz.id,
    storedIsBSet: after.today.id === bQuiz.id,
    scoresKept: after.scores.length === 1 && after.scores[0].firstScore === 100,
  };
}

// 자정을 넘긴 늦은 시작 — 탭 A 가 10/30 23:59 에 시작해 AI 를 기다리는 사이 날짜가 넘어가고 탭 B 가 10/31 세트를 만들었다.
// A 는 10/30 세트로 덮지 않고 10/31 세트를 돌려받으며, B 의 10/31 답안은 그대로 받아진다(PR 2 2회차 경계)
{
  const clock = makeClock("2026-10-30T23:59:50");
  const local = device(11, true);
  local.ie_gemini_api_key = KEY;
  const shared = new FakeStorage(local);
  const tabA = openWindow(shared, clock);
  const tabB = openWindow(shared, clock);
  let release;
  const gate = new Promise((r) => {
    release = r;
  });
  tabA.ctx.aiResponder = async () => {
    await gate;
    return geminiReply([aiItem("put up with")]);
  };
  tabB.ctx.aiResponder = async () => new Response("{}", { status: 500 });
  const pendingA = call(tabA, "POST", "/api/quiz/today");
  await new Promise((r) => setTimeout(r, 20));
  clock.set("2026-10-31T00:00:10");
  const bQuiz = (await call(tabB, "POST", "/api/quiz/today")).body.quiz;
  release();
  const aRes = await pendingA;
  const stored = JSON.parse(shared.getItem(QUIZ_KEY)).today;
  const bAttempt = await call(tabB, "POST", "/api/quiz/attempt", { date: bQuiz.date, quizId: bQuiz.id, answers: bQuiz.questions.map((q) => q.answerIndex) });
  // 기기 시계가 하루 늦은 탭이 [퀴즈 시작] 을 눌러도 새 세트를 덮지 않는다
  clock.set("2026-10-30T12:00:00");
  const tabC = openWindow(shared, clock);
  const cRes = await call(tabC, "POST", "/api/quiz/today");
  out.midnight = {
    bDate: bQuiz.date,
    storedDate: stored.date,
    storedIsBSet: stored.id === bQuiz.id,
    aCreated: aRes.body.created,
    aGotBSet: aRes.body.quiz.id === bQuiz.id,
    bAttemptStatus: bAttempt.status,
    olderClockCreated: cRes.body.created,
    olderClockGotBSet: cRes.body.quiz.id === bQuiz.id,
    olderClockAiCalls: tabC.calls.filter((c) => c.url.includes("generativelanguage")).length,
    storedAfterOlderClock: JSON.parse(shared.getItem(QUIZ_KEY)).today.id === bQuiz.id,
  };
}

// ── PR 3: 점수 표 · 7일 평균 · 루틴과 분리 · 백업 ─────────────────
// 날마다 퀴즈 — 10/16(14일 밖) 50 · 10/22(7일 밖, 14일 안) 60 · 10/28 70 · 10/30 80 · 10/31 90 → 다시 풀어 100
async function playDay(w, clock, iso, wrong) {
  clock.set(iso);
  const quiz = (await call(w, "POST", "/api/quiz/today")).body.quiz;
  const answers = quiz.questions.map((q, i) => (i < wrong ? (q.answerIndex + 1) % 4 : q.answerIndex));
  return call(w, "POST", "/api/quiz/attempt", { date: quiz.date, quizId: quiz.id, answers });
}
{
  const clock = makeClock("2026-10-31T09:00:00");
  const w = openWindow(device(11, true), clock);
  const routineBefore = await call(w, "GET", "/api/routine");
  await playDay(w, clock, "2026-10-16T09:00:00", 5);
  await playDay(w, clock, "2026-10-22T09:00:00", 4);
  await playDay(w, clock, "2026-10-28T09:00:00", 3);
  await playDay(w, clock, "2026-10-30T09:00:00", 2);
  await playDay(w, clock, "2026-10-31T09:00:00", 1);
  clock.set("2026-10-31T10:00:00");
  const q = (await call(w, "POST", "/api/quiz/today")).body.quiz;
  await call(w, "POST", "/api/quiz/attempt", { date: q.date, quizId: q.id, answers: q.questions.map((x) => x.answerIndex) });
  const scores = await call(w, "GET", "/api/quiz/scores");
  const routineAfter = await call(w, "GET", "/api/routine");
  const engine = w.ctx.ImproveEnglishStandalone;
  const backup = JSON.parse(JSON.stringify(engine.exportBackupPayload()));
  out.scores = {
    scores,
    routineSame: JSON.stringify(routineBefore.body) === JSON.stringify(routineAfter.body),
    backupHasQuiz: Boolean(backup.quiz) && Array.isArray(backup.quiz.scores),
    backupScoreCount: backup.quiz ? backup.quiz.scores.length : null,
  };

  // 새 기기에 복원 — 같은 점수 표
  const fresh = openWindow(device(11, true), clock);
  const restored = fresh.ctx.ImproveEnglishStandalone.importBackupPayload(backup);
  out.restore = { restored, scores: await call(fresh, "GET", "/api/quiz/scores") };

  // 옛 백업(quiz 칸 없음) — 기기의 퀴즈 기록은 그대로
  const old = JSON.parse(JSON.stringify(backup));
  delete old.quiz;
  const keep = openWindow(w.ctx.localStorage.dump(), clock);
  const quizBefore = keep.ctx.localStorage.getItem(QUIZ_KEY);
  keep.ctx.ImproveEnglishStandalone.importBackupPayload(old);
  out.oldBackup = { quizKept: keep.ctx.localStorage.getItem(QUIZ_KEY) === quizBefore };

  // 틀린 quiz 칸 — 백업 전체를 거절하고 기기 저장소를 하나도 바꾸지 않는다
  const goodToday = backup.quiz.today;
  const line = backup.quiz.scores[0];
  const badForms = {
    notObject: "quiz",
    scoresMissing: { today: null },
    scoresNotList: { today: null, scores: "x" },
    scoreOver100: { today: null, scores: [{ ...line, firstScore: 101, bestScore: 101 }] },
    scoreNotInt: { today: null, scores: [{ ...line, firstScore: 50.5 }] },
    bestBelowFirst: { today: null, scores: [{ ...line, firstScore: 90, bestScore: 80 }] },
    attemptZero: { today: null, scores: [{ ...line, attemptCount: 0 }] },
    totalFour: { today: null, scores: [{ ...line, total: 4 }] },
    totalEleven: { today: null, scores: [{ ...line, total: 11 }] },
    badDate: { today: null, scores: [{ ...line, date: "2026-13-01" }] },
    duplicateDate: { today: null, scores: [line, { ...line }] },
    todayNoId: { today: { ...goodToday, id: undefined }, scores: [] },
    todayBadQuestion: { today: { ...goodToday, questions: goodToday.questions.map((x, i) => (i === 0 ? { ...x, answerIndex: 4 } : x)) }, scores: [] },
    todayTooFew: { today: { ...goodToday, questions: goodToday.questions.slice(0, 4) }, scores: [] },
  };
  // 퀴즈 기록 저장이 실패하는 기기 — 복원을 멈추고 알리며, 첨삭 · 단어장 · 루틴 · 퀴즈 어느 것도 바꾸지 않는다
  {
    const target = openWindow(w.ctx.localStorage.dump(), clock);
    const before = JSON.stringify(target.ctx.localStorage.dump());
    target.ctx.localStorage.failKey = QUIZ_KEY;
    let error = null;
    let result = null;
    try {
      result = target.ctx.ImproveEnglishStandalone.importBackupPayload({ ...backup, history: [], vocab: [] });
    } catch (e) {
      error = String(e.message || e);
    }
    target.ctx.localStorage.failKey = null;
    out.backupSaveFail = { error, result, unchanged: JSON.stringify(target.ctx.localStorage.dump()) === before };
  }

  out.badBackup = {};
  for (const [name, quiz] of Object.entries(badForms)) {
    const target = openWindow(w.ctx.localStorage.dump(), clock);
    const before = JSON.stringify(target.ctx.localStorage.dump());
    let error = null;
    try {
      target.ctx.ImproveEnglishStandalone.importBackupPayload({ ...backup, history: [], vocab: [], quiz });
    } catch (e) {
      error = String(e.message || e);
    }
    out.badBackup[name] = { error, unchanged: JSON.stringify(target.ctx.localStorage.dump()) === before };
  }
}

process.stdout.write(JSON.stringify(out));
