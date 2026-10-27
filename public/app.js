/**
 * ImproveEnglish 조각 1(ai-feedback) 브라우저 화면 제어 스크립트.
 * - 글자 입력 및 마이크(Web Speech API) 음성 입력 전환
 * - POST /api/feedback 호출 및 3단 첨삭 카드 렌더링
 * - GET /api/history 호출 및 내 PC 자동 저장 기록 조회·재열람
 */

(function () {
  const sentenceInput = document.getElementById("sentence-input");
  const charCounter = document.getElementById("char-counter");
  const modeBadge = document.getElementById("input-mode-badge");
  const voiceBtn = document.getElementById("voice-btn");
  const submitBtn = document.getElementById("submit-btn");
  const statusMsg = document.getElementById("status-msg");

  const resultSection = document.getElementById("result-section");
  const resultMeta = document.getElementById("result-meta");
  const resOriginal = document.getElementById("res-original");
  const resCorrected = document.getElementById("res-corrected");
  const resExplanation = document.getElementById("res-explanation");
  const resAlternatives = document.getElementById("res-alternatives");
  const resKeys = document.getElementById("res-keys");

  const historyList = document.getElementById("history-list");
  const historyEmpty = document.getElementById("history-empty");
  const historyCount = document.getElementById("history-count");

  let currentInputMode = "text";
  let recognition = null;
  let isRecording = false;

  function setInputMode(mode) {
    currentInputMode = mode === "voice" ? "voice" : "text";
    if (currentInputMode === "voice") {
      modeBadge.textContent = "🎤 음성 입력 모드";
      modeBadge.className = "mode-badge mode-voice";
    } else {
      modeBadge.textContent = "글자 입력 모드";
      modeBadge.className = "mode-badge mode-text";
    }
  }

  function updateCounter() {
    const len = sentenceInput.value.length;
    charCounter.textContent = `${len.toLocaleString()} / 1,000자`;
  }

  function showStatus(text, kind) {
    statusMsg.hidden = false;
    statusMsg.textContent = text;
    statusMsg.className = `status-msg ${kind}`;
  }

  function hideStatus() {
    statusMsg.hidden = true;
    statusMsg.textContent = "";
  }

  function formatDate(isoStr) {
    try {
      const d = new Date(isoStr);
      return d.toLocaleString("ko-KR", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (_) {
      return isoStr;
    }
  }

  function renderRecord(record) {
    if (!record || !record.feedback) return;
    const fb = record.feedback;
    resultSection.hidden = false;
    const modeLabel = record.inputMode === "voice" ? "🎤 마이크 입력" : "⌨️ 글자 입력";
    resultMeta.textContent = `${modeLabel} · ${formatDate(record.createdAt)}`;
    resOriginal.textContent = record.text;
    resCorrected.textContent = fb.corrected;
    resExplanation.textContent = fb.explanation;

    resAlternatives.innerHTML = "";
    (fb.alternatives || []).forEach((item) => {
      const li = document.createElement("li");
      li.className = "alt-item";
      const expr = document.createElement("div");
      expr.className = "alt-expr";
      expr.textContent = item.expression;
      const nuance = document.createElement("div");
      nuance.className = "alt-nuance";
      nuance.textContent = `💡 ${item.nuance}`;
      li.appendChild(expr);
      li.appendChild(nuance);
      resAlternatives.appendChild(li);
    });

    resKeys.innerHTML = "";
    (fb.keyExpressions || []).forEach((item) => {
      const li = document.createElement("li");
      li.className = "key-item";
      const expr = document.createElement("div");
      expr.className = "key-expr";
      expr.textContent = `${item.expression} — ${item.meaning}`;
      const ex = document.createElement("div");
      ex.className = "key-example";
      ex.textContent = `예문: "${item.example}"`;
      li.appendChild(expr);
      li.appendChild(ex);
      resKeys.appendChild(li);
    });
  }

  function renderHistoryList(items) {
    historyList.innerHTML = "";
    historyCount.textContent = `${items.length}건`;
    if (!items.length) {
      historyEmpty.hidden = false;
      return;
    }
    historyEmpty.hidden = true;
    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "history-item";

      const top = document.createElement("div");
      top.className = "history-top";
      const modeText = item.inputMode === "voice" ? "🎤 음성 입력" : "⌨️ 글자 입력";
      top.textContent = `${modeText} · ${formatDate(item.createdAt)}`;

      const orig = document.createElement("div");
      orig.className = "history-original";
      orig.textContent = `내가 쓴 문장: ${item.text}`;

      const corr = document.createElement("div");
      corr.className = "history-corrected";
      corr.textContent = `→ ${item.feedback ? item.feedback.corrected : ""}`;

      li.appendChild(top);
      li.appendChild(orig);
      li.appendChild(corr);

      li.addEventListener("click", () => {
        renderRecord(item);
        resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
      });

      historyList.appendChild(li);
    });
  }

  async function fetchHistory() {
    try {
      const res = await fetch("/api/history");
      if (!res.ok) return;
      const data = await res.json();
      renderHistoryList(data.items || []);
    } catch (_) {
      // 초기 로드 실패 시 무시
    }
  }

  async function submitSentence() {
    const text = sentenceInput.value.trim();
    if (!text) {
      showStatus("첨삭받을 영어 문장을 입력해 주세요.", "error");
      return;
    }
    if (text.length > 1000) {
      showStatus("문장은 최대 1,000자까지 입력할 수 있습니다.", "error");
      return;
    }

    submitBtn.disabled = true;
    showStatus("AI 코치가 문장을 분석하고 자연스러운 표현을 정리하고 있습니다...", "info");

    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text,
          inputMode: currentInputMode,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        showStatus(data.error || "첨삭 요청 처리 중 오류가 발생했습니다.", "error");
        return;
      }
      hideStatus();
      renderRecord(data);
      await fetchHistory();
    } catch (_) {
      showStatus("서버와 통신할 수 없습니다. 서버가 실행 중인지 확인해 주세요.", "error");
    } finally {
      submitBtn.disabled = false;
    }
  }

  function setupSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      voiceBtn.addEventListener("click", () => {
        showStatus(
          "이 브라우저는 음성 인식을 지원하지 않습니다. Chrome 또는 Edge 브라우저를 이용해 주세요.",
          "error"
        );
      });
      return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.addEventListener("start", () => {
      isRecording = true;
      voiceBtn.textContent = "⏹️ 말하기 종료";
      voiceBtn.classList.add("recording");
      showStatus("영어로 말씀해 주세요. 말씀을 마치면 자동으로 입력창에 들어갑니다...", "info");
    });

    recognition.addEventListener("result", (event) => {
      const transcript = event.results[0][0].transcript;
      sentenceInput.value = sentenceInput.value
        ? `${sentenceInput.value.trim()} ${transcript}`
        : transcript;
      setInputMode("voice");
      updateCounter();
      showStatus("음성이 글자로 입력되었습니다. 내용을 확인한 뒤 [AI 첨삭받기]를 눌러주세요.", "info");
    });

    recognition.addEventListener("error", () => {
      showStatus("음성을 인식하지 못했습니다. 마이크 권한을 확인하거나 다시 시도해 주세요.", "error");
    });

    recognition.addEventListener("end", () => {
      isRecording = false;
      voiceBtn.textContent = "🎤 마이크로 말하기";
      voiceBtn.classList.remove("recording");
    });

    voiceBtn.addEventListener("click", () => {
      if (isRecording) {
        recognition.stop();
      } else {
        recognition.start();
      }
    });
  }

  sentenceInput.addEventListener("input", () => {
    updateCounter();
  });

  document.querySelectorAll(".chip-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      sentenceInput.value = btn.getAttribute("data-sample") || "";
      setInputMode("text");
      updateCounter();
      hideStatus();
      sentenceInput.focus();
    });
  });

  submitBtn.addEventListener("click", submitSentence);
  setupSpeechRecognition();
  updateCounter();
  fetchHistory();
})();
