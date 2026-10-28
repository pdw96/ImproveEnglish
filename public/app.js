/**
 * ImproveEnglish 조각 1(ai-feedback) & 조각 2(vocab-review) 브라우저 화면 제어 스크립트.
 * - 상단 탭 전환 (AI 영작·말하기 첨삭 / 내 단어장 · 오늘의 복습)
 * - 글자 입력 및 마이크(Web Speech API) 음성 입력 전환
 * - POST /api/feedback 호출 및 3단 첨삭 카드 렌더링 + [+ 단어장에 담기] 원클릭 저장
 * - GET/POST /api/vocab, POST /api/vocab/review, DELETE /api/vocab/<id> 연동
 */

(function () {
  // 탭 요소
  const tabFeedbackBtn = document.getElementById("tab-feedback-btn");
  const tabVocabBtn = document.getElementById("tab-vocab-btn");
  const panelFeedback = document.getElementById("panel-feedback");
  const panelVocab = document.getElementById("panel-vocab");
  const dueBadge = document.getElementById("due-badge");

  // 조각 1: 첨삭 입력·결과·기록 요소
  const sentenceInput = document.getElementById("sentence-input");
  const charCounter = document.getElementById("char-counter");
  const modeBadge = document.getElementById("input-mode-badge");
  const voiceBtn = document.getElementById("voice-btn");
  const submitBtn = document.getElementById("submit-btn");
  const statusMsg = document.getElementById("status-msg");

  const resultSection = document.getElementById("result-section");
  const resultMeta = document.getElementById("result-meta");
  const vocabToast = document.getElementById("vocab-toast");
  const vocabToastText = document.getElementById("vocab-toast-text");
  const vocabToastGoBtn = document.getElementById("vocab-toast-go-btn");
  const resCorrectedSaveWrap = document.getElementById("res-corrected-save-wrap");
  const resOriginal = document.getElementById("res-original");
  const resCorrected = document.getElementById("res-corrected");
  const resExplanation = document.getElementById("res-explanation");
  const resAlternatives = document.getElementById("res-alternatives");
  const resKeys = document.getElementById("res-keys");

  const historyList = document.getElementById("history-list");
  const historyEmpty = document.getElementById("history-empty");
  const historyCount = document.getElementById("history-count");

  // 조각 2: 오늘의 복습 카드·직접 추가·단어장 목록 요소
  const reviewProgress = document.getElementById("review-progress");
  const quizBox = document.getElementById("quiz-box");
  const quizEmpty = document.getElementById("quiz-empty");
  const quizEmptyText = document.getElementById("quiz-empty-text");
  const quizEmptyActions = document.getElementById("quiz-empty-actions");
  const goFeedbackFromEmptyBtn = document.getElementById("go-feedback-from-empty-btn");
  const quickSampleVocabBtn = document.getElementById("quick-sample-vocab-btn");
  const quizMeaning = document.getElementById("quiz-meaning");
  const quizHint = document.getElementById("quiz-hint");
  const quizRevealBtn = document.getElementById("quiz-reveal-btn");
  const quizAnswerArea = document.getElementById("quiz-answer-area");
  const quizAnswerExpr = document.getElementById("quiz-answer-expr");
  const quizAnswerExample = document.getElementById("quiz-answer-example");
  const ratingEasyBtn = document.getElementById("rating-easy-btn");

  const vocabExprInput = document.getElementById("vocab-expr-input");
  const vocabMeaningInput = document.getElementById("vocab-meaning-input");
  const vocabExampleInput = document.getElementById("vocab-example-input");
  const vocabAddBtn = document.getElementById("vocab-add-btn");
  const vocabStatusMsg = document.getElementById("vocab-status-msg");

  const vocabTotalCount = document.getElementById("vocab-total-count");
  const vocabList = document.getElementById("vocab-list");
  const vocabEmpty = document.getElementById("vocab-empty");

  let currentInputMode = "text";
  let recognition = null;
  let isRecording = false;
  let lastRenderedRecord = null;

  let vocabItems = [];
  let dueItems = [];
  let todayStr = "";
  let savedExprKeys = new Set();

  function normalizeExpr(str) {
    return (str || "").trim().toLowerCase();
  }

  function switchTab(target) {
    const isVocab = target === "vocab";
    panelFeedback.hidden = isVocab;
    panelVocab.hidden = !isVocab;
    tabFeedbackBtn.classList.toggle("active", !isVocab);
    tabVocabBtn.classList.toggle("active", isVocab);
    tabFeedbackBtn.setAttribute("aria-selected", String(!isVocab));
    tabVocabBtn.setAttribute("aria-selected", String(isVocab));
  }

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

  function showVocabToast(text, kind) {
    vocabToast.hidden = false;
    if (vocabToastText) {
      vocabToastText.textContent = text;
    } else {
      vocabToast.textContent = text;
    }
    vocabToast.className = `status-msg ${kind || "info"} toast-bar`;
  }

  function showVocabFormStatus(text, kind) {
    vocabStatusMsg.hidden = false;
    vocabStatusMsg.textContent = text;
    vocabStatusMsg.className = `status-msg ${kind || "info"}`;
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

  function createSaveToVocabButton(expression, meaning, example) {
    const wrap = document.createElement("div");
    wrap.className = "save-btn-group";

    const btn = document.createElement("button");
    btn.type = "button";
    const alreadySaved = savedExprKeys.has(normalizeExpr(expression));
    btn.className = alreadySaved
      ? "btn-save-vocab saved"
      : "btn-save-vocab";
    btn.textContent = alreadySaved ? "✓ 단어장에 담김" : "+ 단어장에 담기";

    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        const res = await fetch("/api/vocab", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            expression: expression,
            meaning: meaning,
            example: example || "",
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          showVocabToast(data.error || "단어장 저장에 실패했습니다.", "error");
          return;
        }
        if (data.duplicated) {
          showVocabToast(
            `"${expression}" 표현은 이미 단어장에 담겨 있습니다(다음 복습일: ${data.nextReviewDate}).`,
            "info"
          );
        } else {
          showVocabToast(
            `"${expression}" 표현을 내 단어장에 담았습니다!`,
            "info"
          );
        }
        await fetchVocab();
      } catch (_) {
        showVocabToast("서버와 통신할 수 없습니다.", "error");
      } finally {
        btn.disabled = false;
      }
    });

    wrap.appendChild(btn);

    if (alreadySaved) {
      const goReviewBtn = document.createElement("button");
      goReviewBtn.type = "button";
      goReviewBtn.className = "btn-go-review-mini";
      goReviewBtn.textContent = "복습하기 →";
      goReviewBtn.addEventListener("click", () => {
        switchTab("vocab");
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
      wrap.appendChild(goReviewBtn);
    }

    return wrap;
  }

  function renderRecord(record) {
    if (!record || !record.feedback) return;
    lastRenderedRecord = record;
    const fb = record.feedback;
    resultSection.hidden = false;
    const modeLabel = record.inputMode === "voice" ? "🎤 마이크 입력" : "⌨️ 글자 입력";
    resultMeta.textContent = `${modeLabel} · ${formatDate(record.createdAt)}`;
    resOriginal.textContent = record.text;
    resCorrected.textContent = fb.corrected;
    resExplanation.textContent = fb.explanation;

    if (resCorrectedSaveWrap) {
      resCorrectedSaveWrap.innerHTML = "";
      resCorrectedSaveWrap.appendChild(
        createSaveToVocabButton(fb.corrected, record.text, "")
      );
    }

    resAlternatives.innerHTML = "";
    (fb.alternatives || []).forEach((item) => {
      const li = document.createElement("li");
      li.className = "alt-item";

      const topRow = document.createElement("div");
      topRow.className = "item-action-row";

      const expr = document.createElement("div");
      expr.className = "alt-expr";
      expr.textContent = item.expression;

      const saveBtn = createSaveToVocabButton(
        item.expression,
        item.nuance,
        ""
      );

      topRow.appendChild(expr);
      topRow.appendChild(saveBtn);

      const nuance = document.createElement("div");
      nuance.className = "alt-nuance";
      nuance.textContent = `💡 ${item.nuance}`;

      li.appendChild(topRow);
      li.appendChild(nuance);
      resAlternatives.appendChild(li);
    });

    resKeys.innerHTML = "";
    (fb.keyExpressions || []).forEach((item) => {
      const li = document.createElement("li");
      li.className = "key-item";

      const topRow = document.createElement("div");
      topRow.className = "item-action-row";

      const expr = document.createElement("div");
      expr.className = "key-expr";
      expr.textContent = `${item.expression} — ${item.meaning}`;

      const saveBtn = createSaveToVocabButton(
        item.expression,
        item.meaning,
        item.example
      );

      topRow.appendChild(expr);
      topRow.appendChild(saveBtn);

      const ex = document.createElement("div");
      ex.className = "key-example";
      ex.textContent = `예문: "${item.example}"`;

      li.appendChild(topRow);
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

    // 페이지 첫 로드 시 아직 표시된 첨삭 결과가 없으면 가장 최근 첨삭 결과를 자동으로 펼쳐 보여줌
    if (!lastRenderedRecord && items[0]) {
      renderRecord(items[0]);
    }

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
        vocabToast.hidden = true;
        renderRecord(item);
        resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
      });

      historyList.appendChild(li);
    });
  }

  function maskExpressionInExample(example, expression) {
    if (!example) return "";
    const trimmed = (expression || "").trim();
    if (!trimmed) return example;
    const escaped = trimmed.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(escaped, "gi");
    if (regex.test(example)) {
      return example.replace(regex, "_____");
    }
    return example;
  }

  function getEasyNextDays(box) {
    const nextBox = Math.min(3, Math.max(0, box || 0) + 1);
    if (nextBox === 1) return 7;
    if (nextBox === 2) return 14;
    return 30;
  }

  function renderQuizCard() {
    reviewProgress.textContent = `오늘 복습 남은 표현 ${dueItems.length}개`;
    dueBadge.textContent = `오늘 복습 ${dueItems.length}`;
    dueBadge.className = dueItems.length > 0 ? "tab-badge has-due" : "tab-badge";

    if (!dueItems.length) {
      quizBox.hidden = true;
      quizEmpty.hidden = false;
      if (vocabItems.length > 0) {
        if (quizEmptyText) {
          quizEmptyText.textContent =
            "🎉 오늘 복습할 표현을 모두 마쳤습니다! 아래 전체 단어장에서 다음 복습 예정일을 확인해 보세요.";
        }
        if (quizEmptyActions) {
          quizEmptyActions.hidden = true;
        }
      } else {
        if (quizEmptyText) {
          quizEmptyText.textContent =
            "아직 오늘 복습할 표현이 없습니다. 첨삭 결과에서 담거나 아래 버튼으로 바로 체험해 보세요!";
        }
        if (quizEmptyActions) {
          quizEmptyActions.hidden = false;
        }
      }
      return;
    }

    const current = dueItems[0];
    quizEmpty.hidden = true;
    quizBox.hidden = false;

    quizMeaning.textContent = current.meaning;
    const hasDistinctExample =
      current.example &&
      normalizeExpr(current.example) !== normalizeExpr(current.expression);
    if (hasDistinctExample) {
      const masked = maskExpressionInExample(current.example, current.expression);
      quizHint.hidden = false;
      quizHint.textContent = `예문 힌트: "${masked}"`;
    } else {
      quizHint.hidden = true;
      quizHint.textContent = "";
    }

    quizAnswerArea.hidden = true;
    quizRevealBtn.hidden = false;
    quizAnswerExpr.textContent = current.expression;
    quizAnswerExample.textContent = hasDistinctExample
      ? `예문: "${current.example}"`
      : "";

    const easyDays = getEasyNextDays(current.box);
    ratingEasyBtn.textContent = `😊 쉬웠음 (${easyDays}일 뒤 · 7→14→30일)`;
  }

  function formatBoxLabel(box) {
    if (box >= 3) return "단계 3 (30일 주기)";
    if (box === 2) return "단계 2 (14일 주기)";
    if (box === 1) return "단계 1 (7일 주기)";
    return "새 표현 (당일·1일 주기)";
  }

  function renderVocabList() {
    vocabList.innerHTML = "";
    vocabTotalCount.textContent = `총 ${vocabItems.length}개`;
    if (!vocabItems.length) {
      vocabEmpty.hidden = false;
      return;
    }
    vocabEmpty.hidden = true;

    vocabItems.forEach((item) => {
      const li = document.createElement("li");
      li.className = "vocab-item";

      const topRow = document.createElement("div");
      topRow.className = "item-action-row";

      const titleWrap = document.createElement("div");
      const exprSpan = document.createElement("span");
      exprSpan.className = "vocab-expr";
      exprSpan.textContent = item.expression;

      const meaningSpan = document.createElement("span");
      meaningSpan.className = "vocab-meaning";
      meaningSpan.textContent = ` — ${item.meaning}`;

      titleWrap.appendChild(exprSpan);
      titleWrap.appendChild(meaningSpan);

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn-delete-vocab";
      delBtn.textContent = "삭제";
      delBtn.addEventListener("click", async () => {
        delBtn.disabled = true;
        try {
          const res = await fetch(`/api/vocab/${encodeURIComponent(item.id)}`, {
            method: "DELETE",
          });
          if (res.ok) {
            await fetchVocab();
          }
        } finally {
          delBtn.disabled = false;
        }
      });

      topRow.appendChild(titleWrap);
      topRow.appendChild(delBtn);
      li.appendChild(topRow);

      if (item.example) {
        const exDiv = document.createElement("div");
        exDiv.className = "key-example";
        exDiv.textContent = `예문: "${item.example}"`;
        li.appendChild(exDiv);
      }

      const metaRow = document.createElement("div");
      metaRow.className = "vocab-meta-row";

      const isDue = todayStr ? item.nextReviewDate <= todayStr : true;
      const dueSpan = document.createElement("span");
      dueSpan.className = isDue ? "due-tag due-now" : "due-tag";
      dueSpan.textContent = isDue
        ? `🔥 오늘 복습 대상 (예정일: ${item.nextReviewDate})`
        : `📅 다음 복습 예정일: ${item.nextReviewDate}`;

      const statsSpan = document.createElement("span");
      statsSpan.className = "vocab-stats";
      statsSpan.textContent = `${formatBoxLabel(item.box)} · 누적 복습 ${item.reviewCount}회`;

      metaRow.appendChild(dueSpan);
      metaRow.appendChild(statsSpan);
      li.appendChild(metaRow);

      vocabList.appendChild(li);
    });
  }

  async function fetchVocab() {
    try {
      const res = await fetch("/api/vocab");
      if (!res.ok) return;
      const data = await res.json();
      vocabItems = data.items || [];
      dueItems = data.dueItems || [];
      todayStr = data.today || "";
      savedExprKeys = new Set(vocabItems.map((it) => normalizeExpr(it.expression)));

      renderQuizCard();
      renderVocabList();
      if (lastRenderedRecord) {
        renderRecord(lastRenderedRecord);
      }
    } catch (_) {
      // 초기 로드 실패 시 무시
    }
  }

  async function submitDirectVocab() {
    const expression = vocabExprInput.value.trim();
    const meaning = vocabMeaningInput.value.trim();
    const example = vocabExampleInput.value.trim();

    if (!expression) {
      showVocabFormStatus("단어장에 추가할 영어 표현을 입력해 주세요.", "error");
      return;
    }
    if (!meaning) {
      showVocabFormStatus("영어 표현의 한국어 뜻을 입력해 주세요.", "error");
      return;
    }

    vocabAddBtn.disabled = true;
    try {
      const res = await fetch("/api/vocab", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expression: expression,
          meaning: meaning,
          example: example,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        showVocabFormStatus(data.error || "단어 추가에 실패했습니다.", "error");
        return;
      }

      if (data.duplicated) {
        showVocabFormStatus(
          `"${data.expression}" 표현은 이미 단어장에 등록되어 있습니다(다음 복습 예정일: ${data.nextReviewDate}).`,
          "info"
        );
      } else {
        vocabExprInput.value = "";
        vocabMeaningInput.value = "";
        vocabExampleInput.value = "";
        showVocabFormStatus(
          `"${data.expression}" 표현이 단어장에 추가되었습니다! 위 복습 카드에서 바로 학습할 수 있습니다.`,
          "info"
        );
      }
      await fetchVocab();
    } catch (_) {
      showVocabFormStatus("서버와 통신할 수 없습니다.", "error");
    } finally {
      vocabAddBtn.disabled = false;
    }
  }

  async function submitReviewRating(rating) {
    if (!dueItems.length) return;
    const current = dueItems[0];
    const ratingBtns = document.querySelectorAll(".rating-btn");
    ratingBtns.forEach((b) => {
      b.disabled = true;
    });

    try {
      const res = await fetch("/api/vocab/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: current.id,
          rating: rating,
        }),
      });
      if (res.ok) {
        await fetchVocab();
      }
    } finally {
      ratingBtns.forEach((b) => {
        b.disabled = false;
      });
    }
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
    let text = sentenceInput.value.trim();
    if (!text) {
      // 입력창이 비어 있을 때 바로 누르면 첫 번째 예시 문장을 자동으로 채워 진행
      const firstSample = document.querySelector(".chip-btn");
      const sampleText = firstSample ? firstSample.getAttribute("data-sample") : "";
      if (sampleText) {
        sentenceInput.value = sampleText;
        updateCounter();
        text = sampleText.trim();
      } else {
        showStatus("첨삭받을 영어 문장을 입력해 주세요.", "error");
        return;
      }
    }
    if (text.length > 1000) {
      showStatus("문장은 최대 1,000자까지 입력할 수 있습니다.", "error");
      return;
    }

    submitBtn.disabled = true;
    vocabToast.hidden = true;
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

  // 이벤트 리스너 연결
  tabFeedbackBtn.addEventListener("click", () => switchTab("feedback"));
  tabVocabBtn.addEventListener("click", () => switchTab("vocab"));

  if (vocabToastGoBtn) {
    vocabToastGoBtn.addEventListener("click", () => {
      switchTab("vocab");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  if (goFeedbackFromEmptyBtn) {
    goFeedbackFromEmptyBtn.addEventListener("click", () => {
      switchTab("feedback");
      if (resultSection && !resultSection.hidden) {
        resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }

  if (quickSampleVocabBtn) {
    quickSampleVocabBtn.addEventListener("click", async () => {
      quickSampleVocabBtn.disabled = true;
      try {
        await fetch("/api/vocab", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            expression: "get off work",
            meaning: "퇴근하다, 근무를 마치고 나오다",
            example: "What time do you usually get off work on Fridays?",
          }),
        });
        await fetchVocab();
      } finally {
        quickSampleVocabBtn.disabled = false;
      }
    });
  }

  sentenceInput.addEventListener("input", updateCounter);

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
  vocabAddBtn.addEventListener("click", submitDirectVocab);

  quizRevealBtn.addEventListener("click", () => {
    quizRevealBtn.hidden = true;
    quizAnswerArea.hidden = false;
  });

  document.querySelectorAll(".rating-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const rating = btn.getAttribute("data-rating");
      if (rating) {
        submitReviewRating(rating);
      }
    });
  });

  setupSpeechRecognition();
  updateCounter();
  fetchHistory();
  fetchVocab();
})();
