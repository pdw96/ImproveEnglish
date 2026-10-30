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
    localStorage: new FakeStorage(local),
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
    calls.push({ url });
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
  const attemptWrong = await call(w, "POST", "/api/quiz/attempt", { date: quiz.date, answers: oneWrong });
  const attemptRight = await call(w, "POST", "/api/quiz/attempt", { date: quiz.date, answers: right });
  const getScored = await call(w, "GET", "/api/quiz/today");
  const snapshot = w.ctx.localStorage.dump();

  // 거절 꼴 — 저장 내용이 거절 전과 같아야 한다([Q5])
  const badBodies = {
    notJson: "{bad",
    notObject: [1, 2],
    badDate: { date: "2026/10/30", answers: right },
    impossibleDate: { date: "2026-02-30", answers: right },
    noAnswers: { date: quiz.date, answers: [] },
    answersNotList: { date: quiz.date, answers: "0123" },
    tooFew: { date: quiz.date, answers: right.slice(0, 9) },
    tooMany: { date: quiz.date, answers: [...right, 0] },
    outOfRange: { date: quiz.date, answers: right.map(() => 4) },
    negative: { date: quiz.date, answers: right.map(() => -1) },
    notInt: { date: quiz.date, answers: right.map(() => 1.5) },
    boolean: { date: quiz.date, answers: right.map(() => true) },
    otherDate: { date: "2026-10-29", answers: right },
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

// 날짜 넘김 ① — 세트 A 를 만든 뒤 날짜를 넘겨 A 의 답안을 내면 A 의 날짜로 남는다
{
  const clock = makeClock("2026-10-30T23:55:00");
  const w = openWindow(device(11, true), clock);
  const a = (await call(w, "POST", "/api/quiz/today")).body.quiz;
  clock.set("2026-10-31T00:05:00");
  const res = await call(w, "POST", "/api/quiz/attempt", { date: a.date, answers: a.questions.map((q) => q.answerIndex) });
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
  const res = await call(w, "POST", "/api/quiz/attempt", { date: a.date, answers: a.questions.map((q) => q.answerIndex) });
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
  const attemptRes = await call(w, "POST", "/api/quiz/attempt", { date: quiz.date, answers: quiz.questions.map((q) => q.answerIndex) });
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

process.stdout.write(JSON.stringify(out));
