// 조각 6(api-key-vault) 시험 도우미 — `public/standalone-engine.js` 를 Node 에서 가짜 브라우저 저장소로 실제로 돌리고,
// 장면마다 본 것을 JSON 한 줄로 내보낸다. 판정은 `tests/test_api_key_vault.py` 가 한다.
import { readFileSync } from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const ENGINE_SRC = readFileSync(path.join(here, "..", "public", "standalone-engine.js"), "utf8");

const KEY = "TEST-ONLY-fake-gemini-key-0000000000";
const PIN = "2580";
const VAULT_NAMES = [
  "ie_gemini_api_key",
  "ie_gemini_api_key_salt",
  "ie_gemini_api_key_iv",
  "ie_gemini_api_key_encrypted",
];
const SESSION_NAME = "ie_gemini_api_key_session";

class FakeStorage {
  constructor(init = {}) {
    this.data = new Map(Object.entries(init));
  }
  getItem(k) {
    return this.data.has(k) ? this.data.get(k) : null;
  }
  setItem(k, v) {
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
function openWindow(local = {}, session = {}) {
  const calls = [];
  const ctx = {
    localStorage: new FakeStorage(local),
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
  ctx.fetch = async (input, init) => {
    const url = typeof input === "string" ? input : input.url;
    const headers = (init && init.headers) || {};
    calls.push({ url, apiKeyHeader: headers["x-goog-api-key"] || null });
    return new Response("{}", { status: 500 });
  };
  vm.createContext(ctx);
  vm.runInContext(ENGINE_SRC, ctx);
  return { ctx, engine: ctx.ImproveEnglishStandalone, calls };
}

async function askFeedback(win) {
  const res = await win.ctx.window.fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: "I go to school yesterday.", inputMode: "text" }),
  });
  const body = await res.json();
  return {
    status: res.status,
    hasCorrected: Boolean(body && body.feedback && body.feedback.corrected),
    geminiCalls: win.calls.filter((c) => c.url.includes("generativelanguage")),
  };
}

function state(win) {
  return {
    local: win.ctx.localStorage.dump(),
    session: win.ctx.sessionStorage.dump(),
    isEncrypted: win.engine.isEncrypted(),
    isUnlocked: win.engine.isUnlocked(),
    hasApiKey: win.engine.hasApiKey(),
  };
}

const out = { KEY, PIN, VAULT_NAMES, SESSION_NAME, MIN_PIN_LENGTH: null };

// 평문 보관 — 빈 비밀번호
{
  const w = openWindow();
  out.MIN_PIN_LENGTH = w.engine.MIN_PIN_LENGTH;
  const ok = await w.engine.saveApiKeyWithPin(KEY, "");
  out.plain = { ok, ...state(w) };
}

// 암호화 보관 — 두 번 저장해 소금 · 초기값이 매번 새로 뽑히는지
let deviceLocal;
let openSession;
{
  const w = openWindow();
  const ok = await w.engine.saveApiKeyWithPin(KEY, PIN);
  out.encrypted = { ok, ...state(w) };
  deviceLocal = w.ctx.localStorage.dump();
  openSession = w.ctx.sessionStorage.dump();
  const w2 = openWindow();
  await w2.engine.saveApiKeyWithPin(KEY, PIN);
  out.encryptedAgain = state(w2);
}

// 같은 창 새로고침 — 해제 유지
{
  const w = openWindow(deviceLocal, openSession);
  out.reload = state(w);
}

// 창을 닫았다 다시 열기 — 잠김, 첨삭은 내장 코치
{
  const w = openWindow(deviceLocal, {});
  out.reopened = state(w);
  out.lockedFeedback = await askFeedback(w);
}

// 틀린 비밀번호
{
  const w = openWindow(deviceLocal, {});
  const ok = await w.engine.unlockWithPin("0000");
  out.wrongPin = { ok, ...state(w) };
}

// 망가진 저장 값
{
  const broken = { ...deviceLocal, ie_gemini_api_key_encrypted: "not-json" };
  const w = openWindow(broken, {});
  const ok = await w.engine.unlockWithPin(PIN);
  out.corrupt = { ok, before: broken, ...state(w) };
}

// 맞는 비밀번호 — 해제 뒤 Gemini 를 부르는지
{
  const w = openWindow(deviceLocal, {});
  const ok = await w.engine.unlockWithPin(PIN);
  out.rightPin = { ok, ...state(w) };
  out.unlockedFeedback = await askFeedback(w);
}

// 1 ~ 3자 비밀번호 — 빈 기기와 금고가 있는 기기 둘 다
{
  const w = openWindow();
  const ok = await w.engine.saveApiKeyWithPin(KEY, "123");
  out.shortPinEmpty = { ok, ...state(w) };
  const w2 = openWindow(deviceLocal, {});
  const ok2 = await w2.engine.saveApiKeyWithPin("TEST-ONLY-other-fake-key-1111111111", "12");
  out.shortPinVault = { ok: ok2, before: deviceLocal, ...state(w2) };
}

// 키 삭제
{
  const w = openWindow(deviceLocal, openSession);
  w.engine.clearApiKey();
  out.cleared = state(w);
}

// 백업 파일
{
  const w = openWindow(deviceLocal, openSession);
  out.backupText = JSON.stringify(w.engine.exportBackupPayload());
}

process.stdout.write(JSON.stringify(out));
