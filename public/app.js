/**
 * ImproveEnglish 조각 1(ai-feedback) · 조각 2(vocab-review) · 조각 3(study-routine) 브라우저 화면 제어 스크립트.
 * - 상단 연속 학습 루틴 배너 및 3단 탭 전환 (첨삭 / 단어장·복습 / 학습 루틴·기록)
 * - POST /api/feedback, GET /api/history 연동
 * - GET/POST /api/vocab, POST /api/vocab/review, DELETE /api/vocab/<id> 연동
 * - GET /api/routine, POST /api/routine/goal 연동 및 최근 14일 달력·날짜별 내역 표시
 */

(function () {
  // 탭 및 상단 배너 요소
  const tabFeedbackBtn = document.getElementById("tab-feedback-btn");
  const tabVocabBtn = document.getElementById("tab-vocab-btn");
  const tabRoutineBtn = document.getElementById("tab-routine-btn");
  const tabSettingsBtn = document.getElementById("tab-settings-btn");
  const panelFeedback = document.getElementById("panel-feedback");
  const panelVocab = document.getElementById("panel-vocab");
  const panelRoutine = document.getElementById("panel-routine");
  const panelSettings = document.getElementById("panel-settings");
  const dueBadge = document.getElementById("due-badge");
  const routineTabBadge = document.getElementById("routine-tab-badge");
  const settingsModeBadge = document.getElementById("settings-mode-badge");

  const bannerStreakPill = document.getElementById("banner-streak-pill");
  const bannerProgressText = document.getElementById("banner-progress-text");
  const bannerStatusBadge = document.getElementById("banner-status-badge");
  const bannerProgressBar = document.getElementById("banner-progress-bar");
  const bannerGoRoutineBtn = document.getElementById("banner-go-routine-btn");

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

  // 조각 3: 학습 루틴·달력·목표 설정 요소
  const routineTodayBadge = document.getElementById("routine-today-badge");
  const statCurrentStreak = document.getElementById("stat-current-streak");
  const statLongestStreak = document.getElementById("stat-longest-streak");
  const statTotalDays = document.getElementById("stat-total-days");
  const routineCalendarGrid = document.getElementById("routine-calendar-grid");
  const selectedDayTitle = document.getElementById("selected-day-title");
  const selectedDaySummaryBadge = document.getElementById("selected-day-summary-badge");
  const selectedDayContent = document.getElementById("selected-day-content");
  const goalFeedbackInput = document.getElementById("goal-feedback-input");
  const goalReviewInput = document.getElementById("goal-review-input");
  const goalSaveBtn = document.getElementById("goal-save-btn");
  const goalStatusMsg = document.getElementById("goal-status-msg");

  // 조각 4: 오늘의 상황별 영작·말하기 미션 요소
  const missionCategoryBadge = document.getElementById("mission-category-badge");
  const missionStatusBadge = document.getElementById("mission-status-badge");
  const missionNextBtn = document.getElementById("mission-next-btn");
  const missionCategoryBar = document.getElementById("mission-category-bar");
  const missionTitle = document.getElementById("mission-title");
  const missionUseSampleBtn = document.getElementById("mission-use-sample-btn");
  const missionSituation = document.getElementById("mission-situation");
  const missionGuide = document.getElementById("mission-guide");
  const missionHintsList = document.getElementById("mission-hints-list");
  const missionVocabList = document.getElementById("mission-vocab-list");

  // 조각 5: 서버 없는 모바일 앱 · 설정 · 백업 요소
  const engineStatusPill = document.getElementById("engine-status-pill");
  const modeStandaloneBtn = document.getElementById("mode-standalone-btn");
  const modeServerBtn = document.getElementById("mode-server-btn");
  const pwaInstallBox = document.getElementById("pwa-install-box");
  const pwaInstallBtn = document.getElementById("pwa-install-btn");
  const apikeyStatusBadge = document.getElementById("apikey-status-badge");
  const settingsApikeyInput = document.getElementById("settings-apikey-input");
  const apikeyMaskedHint = document.getElementById("apikey-masked-hint");
  const apikeySaveBtn = document.getElementById("apikey-save-btn");
  const apikeyClearBtn = document.getElementById("apikey-clear-btn");
  const apikeyStatusMsg = document.getElementById("apikey-status-msg");
  const backupStatsBadge = document.getElementById("backup-stats-badge");
  const backupExportBtn = document.getElementById("backup-export-btn");
  const backupImportInput = document.getElementById("backup-import-input");
  const backupStatusMsg = document.getElementById("backup-status-msg");

  let deferredInstallPrompt = null;

  let currentInputMode = "text";
  let recognition = null;
  let isRecording = false;
  let lastRenderedRecord = null;

  let vocabItems = [];
  let dueItems = [];
  let todayStr = "";
  let savedExprKeys = new Set();

  let routineData = null;
  let selectedDateStr = "";

  let currentMissionCategory = "all";
  let currentMissionObj = null;

  function normalizeExpr(str) {
    return (str || "").trim().toLowerCase();
  }

  function applyTabDomState(target) {
    const isFeedback = target === "feedback";
    const isVocab = target === "vocab";
    const isRoutine = target === "routine";
    const isSettings = target === "settings";

    panelFeedback.hidden = !isFeedback;
    panelVocab.hidden = !isVocab;
    if (panelRoutine) panelRoutine.hidden = !isRoutine;
    if (panelSettings) panelSettings.hidden = !isSettings;

    tabFeedbackBtn.classList.toggle("active", isFeedback);
    tabVocabBtn.classList.toggle("active", isVocab);
    if (tabRoutineBtn) tabRoutineBtn.classList.toggle("active", isRoutine);
    if (tabSettingsBtn) tabSettingsBtn.classList.toggle("active", isSettings);

    tabFeedbackBtn.setAttribute("aria-selected", String(isFeedback));
    tabVocabBtn.setAttribute("aria-selected", String(isVocab));
    if (tabRoutineBtn) tabRoutineBtn.setAttribute("aria-selected", String(isRoutine));
    if (tabSettingsBtn) tabSettingsBtn.setAttribute("aria-selected", String(isSettings));
  }

  function focusActivePanelHeading(target) {
    const headingId =
      target === "vocab"
        ? "review-heading"
        : target === "routine"
        ? "routine-summary-heading"
        : target === "settings"
        ? "settings-mode-heading"
        : "input-heading";
    const headingEl = document.getElementById(headingId);
    if (headingEl && typeof headingEl.focus === "function") {
      headingEl.focus({ preventScroll: true });
    }
  }

  function switchTab(target) {
    const prefersReducedMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (
      typeof document.startViewTransition === "function" &&
      !prefersReducedMotion &&
      !navigator.webdriver
    ) {
      const transition = document.startViewTransition(() => {
        applyTabDomState(target);
      });
      if (transition && transition.finished) {
        transition.finished.finally(() => {
          focusActivePanelHeading(target);
        });
      }
    } else {
      applyTabDomState(target);
      focusActivePanelHeading(target);
    }
  }

  function setInputMode(mode) {
    currentInputMode = mode === "voice" ? "voice" : "text";
    if (currentInputMode === "voice") {
      modeBadge.textContent = "음성 입력 모드";
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

  function showGoalStatus(text, kind) {
    if (!goalStatusMsg) return;
    goalStatusMsg.hidden = false;
    goalStatusMsg.textContent = text;
    goalStatusMsg.className = `status-msg ${kind || "info"}`;
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
    btn.textContent = alreadySaved ? "단어장에 보관됨" : "+ 단어장에 담기";

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
            `"${expression}" 표현은 이미 단어장에 담겨 있습니다 (다음 복습일: ${data.nextReviewDate}).`,
            "info"
          );
        } else {
          showVocabToast(
            `"${expression}" 표현을 내 단어장에 담았습니다.`,
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
    const modeLabel = record.inputMode === "voice" ? "음성 입력" : "글자 입력";
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
      nuance.textContent = item.nuance;

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
      const enSpan = document.createElement("span");
      enSpan.className = "en-term";
      enSpan.textContent = item.expression;
      const koSpan = document.createElement("span");
      koSpan.className = "ko-meaning";
      koSpan.textContent = ` — ${item.meaning}`;
      expr.appendChild(enSpan);
      expr.appendChild(koSpan);

      const saveBtn = createSaveToVocabButton(
        item.expression,
        item.meaning,
        item.example
      );

      topRow.appendChild(expr);
      topRow.appendChild(saveBtn);

      const ex = document.createElement("div");
      ex.className = "key-example";
      ex.textContent = `"${item.example}"`;

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

    if (!lastRenderedRecord && items[0]) {
      renderRecord(items[0]);
    }

    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "history-item";

      const top = document.createElement("div");
      top.className = "history-top";
      const modeText = item.inputMode === "voice" ? "음성 입력" : "글자 입력";
      top.textContent = `${modeText} · ${formatDate(item.createdAt)}`;

      const orig = document.createElement("div");
      orig.className = "history-original";
      orig.textContent = `원문: ${item.text}`;

      const corr = document.createElement("div");
      corr.className = "history-corrected";
      corr.textContent = item.feedback ? item.feedback.corrected : "";

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
    reviewProgress.textContent = `오늘 복습 대상 ${dueItems.length}개`;
    dueBadge.textContent = `오늘 복습 ${dueItems.length}`;
    dueBadge.className = dueItems.length > 0 ? "tab-badge has-due" : "tab-badge";

    if (!dueItems.length) {
      quizBox.hidden = true;
      quizEmpty.hidden = false;
      if (vocabItems.length > 0) {
        if (quizEmptyText) {
          quizEmptyText.textContent =
            "오늘 예정된 표현 복습을 모두 마쳤습니다. 아래 단어장 보관함에서 다음 복습 예정일을 확인해 보세요.";
        }
        if (quizEmptyActions) {
          quizEmptyActions.hidden = true;
        }
      } else {
        if (quizEmptyText) {
          quizEmptyText.textContent =
            "아직 오늘 복습할 표현이 없습니다. 첨삭 노트에서 담거나 아래 버튼으로 바로 체험해 보세요.";
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
      quizHint.textContent = `"${masked}"`;
    } else {
      quizHint.hidden = true;
      quizHint.textContent = "";
    }

    quizAnswerArea.hidden = true;
    quizRevealBtn.hidden = false;
    quizAnswerExpr.textContent = current.expression;
    quizAnswerExample.textContent = hasDistinctExample
      ? `"${current.example}"`
      : "";

    const easyDays = getEasyNextDays(current.box);
    ratingEasyBtn.textContent = `쉬웠음 (${easyDays}일 뒤 · 7→14→30일)`;
  }

  function formatBoxLabel(box) {
    if (box >= 3) return "단계 3 · 30일 주기";
    if (box === 2) return "단계 2 · 14일 주기";
    if (box === 1) return "단계 1 · 7일 주기";
    return "새 표현 · 당일/1일 주기";
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

      if (item.example && normalizeExpr(item.example) !== normalizeExpr(item.expression)) {
        const exDiv = document.createElement("div");
        exDiv.className = "key-example";
        exDiv.textContent = `"${item.example}"`;
        li.appendChild(exDiv);
      }

      const metaRow = document.createElement("div");
      metaRow.className = "vocab-meta-row";

      const isDue = todayStr ? item.nextReviewDate <= todayStr : true;
      const dueSpan = document.createElement("span");
      dueSpan.className = isDue ? "due-tag due-now" : "due-tag";
      dueSpan.textContent = isDue
        ? `오늘 복습 대상 (예정일: ${item.nextReviewDate})`
        : `다음 복습 예정일: ${item.nextReviewDate}`;

      const statsSpan = document.createElement("span");
      statsSpan.className = "vocab-stats";
      statsSpan.textContent = `${formatBoxLabel(item.box)} · 누적 복습 ${item.reviewCount}회`;

      metaRow.appendChild(dueSpan);
      metaRow.appendChild(statsSpan);
      li.appendChild(metaRow);

      vocabList.appendChild(li);
    });
  }

  function renderSelectedDayDetail(dayObj) {
    if (!dayObj || !selectedDayContent) return;
    selectedDateStr = dayObj.date;

    const isToday = routineData && dayObj.date === routineData.today;
    selectedDayTitle.textContent = isToday
      ? `${dayObj.date} (오늘) 학습 기록`
      : `${dayObj.date} 학습 기록`;

    selectedDaySummaryBadge.textContent = `첨삭 ${dayObj.feedbackCount}문장 · 복습 ${dayObj.reviewCount}단어`;

    selectedDayContent.innerHTML = "";
    const feedbacks = dayObj.feedbacks || [];
    const reviews = dayObj.reviews || [];

    if (!feedbacks.length && !reviews.length) {
      const emptyP = document.createElement("p");
      emptyP.className = "empty-state";
      emptyP.textContent = "이 날짜에는 기록된 첨삭이나 단어 복습 내역이 없습니다.";
      selectedDayContent.appendChild(emptyP);
      return;
    }

    if (feedbacks.length > 0) {
      const fbHeader = document.createElement("div");
      fbHeader.className = "day-sub-header";
      fbHeader.textContent = `다듬은 문장 (${feedbacks.length}건)`;
      selectedDayContent.appendChild(fbHeader);

      const fbUl = document.createElement("ul");
      fbUl.className = "day-detail-list";
      feedbacks.forEach((fb) => {
        const li = document.createElement("li");
        li.className = "day-detail-item";
        li.innerHTML = `<div class="history-original"></div><div class="history-corrected"></div>`;
        li.querySelector(".history-original").textContent = `원문: ${fb.text}`;
        li.querySelector(".history-corrected").textContent = fb.corrected;
        fbUl.appendChild(li);
      });
      selectedDayContent.appendChild(fbUl);
    }

    if (reviews.length > 0) {
      const rvHeader = document.createElement("div");
      rvHeader.className = "day-sub-header";
      rvHeader.textContent = `복습한 표현 (${reviews.length}건)`;
      selectedDayContent.appendChild(rvHeader);

      const rvUl = document.createElement("ul");
      rvUl.className = "day-detail-list";
      const ratingLabelMap = {
        again: "몰랐음 · 1일 뒤",
        hard: "헷갈림 · 3일 뒤",
        easy: "쉬웠음",
      };
      reviews.forEach((rv) => {
        const li = document.createElement("li");
        li.className = "day-detail-item";
        const exprRow = document.createElement("div");
        exprRow.className = "item-action-row";

        const left = document.createElement("span");
        left.className = "vocab-expr-wrap";
        const en = document.createElement("span");
        en.className = "vocab-expr";
        en.textContent = rv.expression;
        const ko = document.createElement("span");
        ko.className = "vocab-meaning";
        ko.textContent = ` — ${rv.meaning}`;
        left.appendChild(en);
        left.appendChild(ko);

        const right = document.createElement("span");
        right.className = "mode-badge mode-text";
        right.textContent = ratingLabelMap[rv.rating] || rv.rating;

        exprRow.appendChild(left);
        exprRow.appendChild(right);
        li.appendChild(exprRow);
        rvUl.appendChild(li);
      });
      selectedDayContent.appendChild(rvUl);
    }
  }

  function renderRoutine(data) {
    if (!data) return;
    routineData = data;
    const goal = data.goal || { dailyFeedbackGoal: 1, dailyReviewGoal: 3 };
    const todayInfo = data.todaySummary || {
      date: data.today,
      feedbackCount: 0,
      reviewCount: 0,
      studied: false,
      goalMet: false,
      progressPercent: 0,
      feedbacks: [],
      reviews: [],
    };

    // 1) 상단 루틴 배너 업데이트
    if (bannerStreakPill) {
      bannerStreakPill.textContent = `연속 ${data.currentStreak}일째`;
      bannerStreakPill.className =
        data.currentStreak > 0 ? "streak-pill active" : "streak-pill";
    }
    if (routineTabBadge) {
      routineTabBadge.textContent = `${data.currentStreak}일 연속`;
      routineTabBadge.className =
        data.currentStreak > 0 ? "tab-badge has-due" : "tab-badge";
    }
    if (bannerProgressText) {
      bannerProgressText.textContent = `오늘의 목표 · 첨삭 ${todayInfo.feedbackCount}/${goal.dailyFeedbackGoal}문장 · 단어 복습 ${todayInfo.reviewCount}/${goal.dailyReviewGoal}개 (${todayInfo.progressPercent}%)`;
    }
    if (bannerProgressBar) {
      bannerProgressBar.style.width = `${Math.min(100, todayInfo.progressPercent || 0)}%`;
    }
    if (bannerStatusBadge) {
      if (todayInfo.goalMet) {
        bannerStatusBadge.textContent = "오늘 목표 100% 달성";
        bannerStatusBadge.className = "routine-state-badge goal-met";
      } else if (todayInfo.studied) {
        bannerStatusBadge.textContent = "오늘 출석 완료 · 연속 학습 유지";
        bannerStatusBadge.className = "routine-state-badge studied";
      } else {
        bannerStatusBadge.textContent = "오늘 첫 학습을 시작해 보세요";
        bannerStatusBadge.className = "routine-state-badge";
      }
    }

    // 2) 루틴 탭 요약 통계 업데이트
    if (routineTodayBadge) {
      routineTodayBadge.textContent = `기준일: ${data.today}`;
    }
    if (statCurrentStreak) {
      statCurrentStreak.textContent = `${data.currentStreak}일째`;
    }
    if (statLongestStreak) {
      statLongestStreak.textContent = `${data.longestStreak}일`;
    }
    if (statTotalDays) {
      statTotalDays.textContent = `총 ${data.totalStudyDays}일`;
    }

    // 3) 목표 설정 입력창 동기화
    if (goalFeedbackInput && document.activeElement !== goalFeedbackInput) {
      goalFeedbackInput.value = String(goal.dailyFeedbackGoal);
    }
    if (goalReviewInput && document.activeElement !== goalReviewInput) {
      goalReviewInput.value = String(goal.dailyReviewGoal);
    }

    // 4) 최근 14일 달력 렌더링
    if (routineCalendarGrid) {
      routineCalendarGrid.innerHTML = "";
      const recentDays = data.recentDays || [];
      const targetDate = selectedDateStr || data.today;
      let selectedObj =
        recentDays.find((d) => d.date === targetDate) ||
        recentDays[recentDays.length - 1] ||
        todayInfo;

      recentDays.forEach((dayItem) => {
        const cell = document.createElement("button");
        cell.type = "button";
        let stateClass = "cal-day-empty";
        let statusIcon = "—";
        if (dayItem.goalMet) {
          stateClass = "cal-day-goal";
          statusIcon = "★ 목표 달성";
        } else if (dayItem.studied) {
          stateClass = "cal-day-studied";
          statusIcon = "✓ 학습 완료";
        }
        const isSelected = selectedObj && dayItem.date === selectedObj.date;
        cell.className = `cal-day-cell ${stateClass}${isSelected ? " selected" : ""}`;

        const shortDate = dayItem.date.slice(5).replace("-", ".");
        cell.innerHTML = `
          <span class="cal-date-label">${shortDate}</span>
          <span class="cal-status-icon">${statusIcon}</span>
          <span class="cal-counts">첨삭 ${dayItem.feedbackCount} · 복습 ${dayItem.reviewCount}</span>
        `;
        cell.addEventListener("click", () => {
          selectedDateStr = dayItem.date;
          renderRoutine(routineData);
        });
        routineCalendarGrid.appendChild(cell);
      });

      renderSelectedDayDetail(selectedObj);
    }
  }

  async function fetchRoutine() {
    try {
      const res = await fetch("/api/routine");
      if (!res.ok) return;
      const data = await res.json();
      renderRoutine(data);
    } catch (_) {
      // 초기 로드 실패 시 무시
    }
  }

  function insertExpressionIntoInput(exprText) {
    if (!exprText || !sentenceInput) return;
    const current = sentenceInput.value;
    if (!current.trim()) {
      sentenceInput.value = `${exprText} `;
    } else if (current.endsWith(" ")) {
      sentenceInput.value = `${current}${exprText} `;
    } else {
      sentenceInput.value = `${current} ${exprText} `;
    }
    setInputMode("text");
    updateCounter();
    hideStatus();
    sentenceInput.focus();
  }

  function renderMission(data) {
    if (!data || !data.mission) return;
    const mission = data.mission;
    currentMissionObj = mission;
    currentMissionCategory = data.selectedCategory || "all";

    if (missionCategoryBadge) {
      missionCategoryBadge.textContent = mission.categoryLabel || "상황 미션";
    }
    if (missionStatusBadge) {
      if (data.completedToday) {
        missionStatusBadge.textContent = "오늘 미션 완료!";
        missionStatusBadge.className = "routine-state-badge goal-met";
      } else {
        missionStatusBadge.textContent = "오늘 미션 대기 중";
        missionStatusBadge.className = "routine-state-badge";
      }
    }

    if (missionCategoryBar) {
      missionCategoryBar.querySelectorAll(".mission-cat-btn").forEach((btn) => {
        const cat = btn.getAttribute("data-category");
        btn.classList.toggle("active", cat === currentMissionCategory);
      });
    }

    if (missionTitle) {
      missionTitle.textContent = mission.title || "";
    }
    if (missionSituation) {
      missionSituation.textContent = mission.situation || "";
    }
    if (missionGuide) {
      missionGuide.textContent = mission.guide || "";
    }

    if (missionHintsList) {
      missionHintsList.innerHTML = "";
      (mission.hints || []).forEach((hint) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "mission-expr-chip";
        const en = document.createElement("span");
        en.className = "mission-chip-en";
        en.textContent = hint.expression;
        const ko = document.createElement("span");
        ko.className = "mission-chip-ko";
        ko.textContent = ` · ${hint.meaning}`;
        btn.appendChild(en);
        btn.appendChild(ko);
        btn.addEventListener("click", () => {
          insertExpressionIntoInput(hint.expression);
        });
        missionHintsList.appendChild(btn);
      });
    }

    if (missionVocabList) {
      missionVocabList.innerHTML = "";
      const suggestions = data.vocabSuggestions || [];
      if (!suggestions.length) {
        const emptySpan = document.createElement("span");
        emptySpan.className = "mission-vocab-empty";
        emptySpan.textContent =
          "아직 내 단어장에 담긴 표현이 없습니다. 첨삭 결과에서 [+ 단어장에 담기]를 누르면 이곳에 오늘 써볼 표현으로 추천됩니다.";
        missionVocabList.appendChild(emptySpan);
      } else {
        suggestions.forEach((item) => {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = item.isDue
            ? "mission-expr-chip vocab-due-chip"
            : "mission-expr-chip vocab-saved-chip";
          const en = document.createElement("span");
          en.className = "mission-chip-en";
          en.textContent = item.expression;
          const ko = document.createElement("span");
          ko.className = "mission-chip-ko";
          ko.textContent = item.isDue
            ? ` · ${item.meaning} (복습 대상)`
            : ` · ${item.meaning}`;
          btn.appendChild(en);
          btn.appendChild(ko);
          btn.addEventListener("click", () => {
            insertExpressionIntoInput(item.expression);
          });
          missionVocabList.appendChild(btn);
        });
      }
    }
  }

  async function fetchMission(options) {
    const opts = options || {};
    const category =
      opts.category !== undefined ? opts.category : currentMissionCategory;
    const params = new URLSearchParams();
    if (category) {
      params.set("category", category);
    }
    if (opts.missionId) {
      params.set("missionId", opts.missionId);
    }
    if (opts.excludeId) {
      params.set("excludeId", opts.excludeId);
    }
    try {
      const res = await fetch(`/api/mission/today?${params.toString()}`);
      if (!res.ok) return;
      const data = await res.json();
      renderMission(data);
    } catch (_) {
      // 초기 로드 실패 시 무시
    }
  }

  async function submitDailyGoal() {
    const fbGoal = parseInt(goalFeedbackInput.value, 10);
    const rvGoal = parseInt(goalReviewInput.value, 10);

    if (Number.isNaN(fbGoal) || fbGoal < 1 || fbGoal > 20) {
      showGoalStatus("하루 목표 첨삭 문장 수는 1~20 사이의 숫자로 입력해 주세요.", "error");
      return;
    }
    if (Number.isNaN(rvGoal) || Number.isNaN(rvGoal) || rvGoal < 1 || rvGoal > 50) {
      showGoalStatus("하루 목표 단어 복습 수는 1~50 사이의 숫자로 입력해 주세요.", "error");
      return;
    }

    goalSaveBtn.disabled = true;
    try {
      const res = await fetch("/api/routine/goal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dailyFeedbackGoal: fbGoal,
          dailyReviewGoal: rvGoal,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        showGoalStatus(data.error || "목표 저장에 실패했습니다.", "error");
        return;
      }
      renderRoutine(data);
      showGoalStatus(
        `하루 학습 목표(첨삭 ${fbGoal}문장 · 복습 ${rvGoal}단어)가 저장되었습니다.`,
        "info"
      );
    } catch (_) {
      showGoalStatus("서버와 통신할 수 없습니다.", "error");
    } finally {
      goalSaveBtn.disabled = false;
    }
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
      await fetchMission({
        category: currentMissionCategory,
        missionId: currentMissionObj ? currentMissionObj.id : undefined,
      });
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
      showVocabFormStatus("영어 표현의 우리말 뜻을 입력해 주세요.", "error");
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
          `"${data.expression}" 표현은 이미 단어장에 등록되어 있습니다 (다음 복습 예정일: ${data.nextReviewDate}).`,
          "info"
        );
      } else {
        vocabExprInput.value = "";
        vocabMeaningInput.value = "";
        vocabExampleInput.value = "";
        showVocabFormStatus(
          `"${data.expression}" 표현이 단어장에 추가되었습니다. 위 복습 카드에서 바로 학습할 수 있습니다.`,
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
        await fetchRoutine();
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
    showStatus("문장을 읽고 자연스러운 영어 표현을 정리하고 있습니다...", "info");

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
      await fetchRoutine();
      await fetchMission({
        category: currentMissionCategory,
        missionId: currentMissionObj ? currentMissionObj.id : undefined,
      });
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
      voiceBtn.textContent = "말하기 종료";
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
      showStatus("음성이 글자로 입력되었습니다. 내용을 확인한 뒤 [문장 첨삭받기]를 눌러주세요.", "info");
    });

    recognition.addEventListener("error", () => {
      showStatus("음성을 인식하지 못했습니다. 마이크 권한을 확인하거나 다시 시도해 주세요.", "error");
    });

    recognition.addEventListener("end", () => {
      isRecording = false;
      voiceBtn.textContent = "마이크로 말하기";
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

  function showApikeyStatus(text, kind) {
    if (!apikeyStatusMsg) return;
    apikeyStatusMsg.hidden = false;
    apikeyStatusMsg.textContent = text;
    apikeyStatusMsg.className = `status-msg ${kind || "info"}`;
  }

  function showBackupStatus(text, kind) {
    if (!backupStatusMsg) return;
    backupStatusMsg.hidden = false;
    backupStatusMsg.textContent = text;
    backupStatusMsg.className = `status-msg ${kind || "info"}`;
  }

  function renderStandaloneSettings() {
    const engine = window.ImproveEnglishStandalone;
    if (!engine) return;

    const mode = engine.getMode();
    const isStandalone = mode === "standalone";

    if (settingsModeBadge) {
      settingsModeBadge.textContent = isStandalone ? "단독 앱 모드" : "PC 서버 모드";
      settingsModeBadge.className = isStandalone
        ? "tab-badge has-due"
        : "tab-badge";
    }
    if (engineStatusPill) {
      engineStatusPill.textContent = isStandalone
        ? "온디바이스 단독 실행 중 (서버 불필요)"
        : "PC 로컬 서버 연동 중";
    }
    if (modeStandaloneBtn && modeServerBtn) {
      modeStandaloneBtn.className = isStandalone
        ? "btn btn-primary"
        : "btn btn-secondary";
      modeServerBtn.className = !isStandalone
        ? "btn btn-primary"
        : "btn btn-secondary";
    }

    const hasKey = engine.hasApiKey();
    if (apikeyStatusBadge) {
      apikeyStatusBadge.textContent = hasKey
        ? "개인 Gemini API 키 연결됨"
        : "내장 스마트 코치 동작 중";
      apikeyStatusBadge.className = hasKey
        ? "routine-state-badge goal-met"
        : "mode-badge mode-text";
    }
    if (apikeyMaskedHint) {
      apikeyMaskedHint.textContent = hasKey
        ? `현재 기기에 저장된 키: ${engine.getMaskedApiKey()}`
        : "현재 기기에 저장된 API 키가 없습니다 (내장 스마트 코치 사용 중).";
    }

    const stats = engine.getLocalStats();
    if (backupStatsBadge) {
      backupStatsBadge.textContent = `기기 보관 중: 첨삭 ${stats.historyCount}건 · 단어 ${stats.vocabCount}개`;
    }
  }

  async function refreshAllData() {
    await fetchVocab();
    await fetchHistory();
    await fetchRoutine();
    await fetchMission();
    renderStandaloneSettings();
  }

  function setupMobileSettingsAndPwa() {
    const engine = window.ImproveEnglishStandalone;

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("./sw.js").catch(() => {});
    }

    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferredInstallPrompt = e;
      if (pwaInstallBox) {
        pwaInstallBox.hidden = false;
      }
    });

    if (pwaInstallBtn) {
      pwaInstallBtn.addEventListener("click", async () => {
        if (!deferredInstallPrompt) return;
        deferredInstallPrompt.prompt();
        await deferredInstallPrompt.userChoice;
        deferredInstallPrompt = null;
        if (pwaInstallBox) {
          pwaInstallBox.hidden = true;
        }
      });
    }

    if (modeStandaloneBtn && engine) {
      modeStandaloneBtn.addEventListener("click", async () => {
        engine.setMode("standalone");
        await refreshAllData();
      });
    }
    if (modeServerBtn && engine) {
      modeServerBtn.addEventListener("click", async () => {
        engine.setMode("server");
        await refreshAllData();
      });
    }

    if (apikeySaveBtn && engine) {
      apikeySaveBtn.addEventListener("click", () => {
        const val = settingsApikeyInput ? settingsApikeyInput.value.trim() : "";
        if (!val) {
          showApikeyStatus("저장할 Gemini API 키를 입력해 주세요.", "error");
          return;
        }
        engine.saveApiKey(val);
        if (settingsApikeyInput) settingsApikeyInput.value = "";
        renderStandaloneSettings();
        showApikeyStatus(
          "개인 Gemini API 키가 이 기기 내부에 안전하게 저장되었습니다.",
          "info"
        );
      });
    }

    if (apikeyClearBtn && engine) {
      apikeyClearBtn.addEventListener("click", () => {
        engine.clearApiKey();
        if (settingsApikeyInput) settingsApikeyInput.value = "";
        renderStandaloneSettings();
        showApikeyStatus(
          "기기에 저장된 API 키가 삭제되었습니다. 내장 스마트 코치 모드로 동작합니다.",
          "info"
        );
      });
    }

    if (backupExportBtn && engine) {
      backupExportBtn.addEventListener("click", () => {
        const payload = engine.exportBackupPayload();
        const blob = new Blob([JSON.stringify(payload, null, 2)], {
          type: "application/json;charset=utf-8",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const dateTag = new Date().toISOString().slice(0, 10);
        a.href = url;
        a.download = `improve-english-backup-${dateTag}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showBackupStatus(
          "내 학습 데이터 백업 파일(.json)을 다운로드했습니다.",
          "info"
        );
      });
    }

    if (backupImportInput && engine) {
      backupImportInput.addEventListener("change", async (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        try {
          const text = await file.text();
          const parsed = JSON.parse(text);
          const result = engine.importBackupPayload(parsed);
          await refreshAllData();
          showBackupStatus(
            `백업 파일 복원 완료! (첨삭 ${result.historyCount}건 · 단어 ${result.vocabCount}개)`,
            "info"
          );
        } catch (err) {
          showBackupStatus(
            err && err.message
              ? err.message
              : "올바른 백업 JSON 파일이 아닙니다.",
            "error"
          );
        } finally {
          backupImportInput.value = "";
        }
      });
    }

    renderStandaloneSettings();
  }

  // 이벤트 리스너 연결
  tabFeedbackBtn.addEventListener("click", () => switchTab("feedback"));
  tabVocabBtn.addEventListener("click", () => switchTab("vocab"));
  if (tabRoutineBtn) {
    tabRoutineBtn.addEventListener("click", () => switchTab("routine"));
  }
  if (tabSettingsBtn) {
    tabSettingsBtn.addEventListener("click", () => {
      renderStandaloneSettings();
      switchTab("settings");
    });
  }
  if (bannerGoRoutineBtn) {
    bannerGoRoutineBtn.addEventListener("click", () => switchTab("routine"));
  }
  if (goalSaveBtn) {
    goalSaveBtn.addEventListener("click", submitDailyGoal);
  }
  if (missionCategoryBar) {
    missionCategoryBar.querySelectorAll(".mission-cat-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cat = btn.getAttribute("data-category") || "all";
        currentMissionCategory = cat;
        fetchMission({ category: cat });
      });
    });
  }
  if (missionNextBtn) {
    missionNextBtn.addEventListener("click", () => {
      fetchMission({
        category: currentMissionCategory,
        excludeId: currentMissionObj ? currentMissionObj.id : undefined,
      });
    });
  }
  if (missionUseSampleBtn) {
    missionUseSampleBtn.addEventListener("click", () => {
      if (!currentMissionObj) return;
      sentenceInput.value =
        currentMissionObj.sampleSentence ||
        currentMissionObj.starterTemplate ||
        "";
      setInputMode("text");
      updateCounter();
      hideStatus();
      sentenceInput.focus();
    });
  }

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
  setupMobileSettingsAndPwa();
  fetchVocab();
  fetchHistory();
  fetchRoutine();
  fetchMission();
})();
