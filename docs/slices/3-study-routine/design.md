# 조각 3 설계 — study-routine

설계다 — **어떻게 · 경계.** 무엇을 · 왜는 같은 폴더의 `requirements.md`.

## ① 바뀌는 것

| 파일 | PR | 무엇 |
|---|---|---|
| `src/routine_types.py` | PR 1 | 일일 학습 목표(`DailyGoal`), 날짜별 학습 요약(`DailyActivitySummary`), 연속 학습 루틴 상태(`RoutineStatus`) 데이터 구조 및 스트릭(연속일·최장 연속일)·목표 달성률 계산 모듈 |
| `src/routine_store.py` | PR 1 | 내 PC 로컬 파일(`data/routine-settings.json`)에 하루 목표 설정과 일자별 복습 활동 로그를 원자적으로 저장·조회하고, 기존 첨삭 기록(`HistoryStore`)·단어장(`VocabStore`) 데이터와 합쳐 날짜별 학습 내역을 집계하는 모듈 |
| `src/app.py` | PR 1 | 루틴 및 일별 학습 현황 조회(`GET /api/routine`), 하루 목표 변경(`POST /api/routine/goal`) API 추가 및 단어 복습(`POST /api/vocab/review`) 시 오늘의 복습 활동 카운트 자동 기록 연결 |
| `tests/test_routine.py` | PR 1 | [R1] 목표 설정 입력 검증, [R2] 연속 학습일(스트릭)·최장 연속일·최근 14일 달력 계산, [R3] 로컬 영속성 및 첨삭·복습 연동 자동 시험 |
| `public/index.html`, `public/app.js`, `public/styles.css` | PR 2 | 상단 연속 학습·오늘의 목표 배너, `[🔥 내 학습 루틴 · 기록]` 탭, 최근 14일 학습 달력(잔디), 날짜별 학습 상세 내역(첨삭 문장·복습 단어) 및 하루 목표 설정 화면(UI) |

1번 조각의 앵커볼트(`src/feedback_types.py`)와 2번 조각의 단어장 데이터 구조(`src/vocab_types.py`)는 건드리지 않고 그대로 유지한다.

## ② 보장하는 것 / 보장하지 않는 것

**보장하는 것**

- **[R1] 하루 학습 목표 입력 검증**: 일일 목표 첨삭 문장 수(`dailyFeedbackGoal`)는 `1 ~ 20` 사이의 정수, 일일 목표 복습 단어 수(`dailyReviewGoal`)는 `1 ~ 50` 사이의 정수만 허용하며, 범위를 벗어나거나 정수가 아닌 입력(`bool`, 문자열, 음수 등)은 `400 Bad Request`로 거절한다.
- **[R2] 연속 학습일(스트릭) 및 일별 학습 달성 판정 보장**:
  - 특정 날짜(`YYYY-MM-DD`)에 **AI 첨삭 1건 이상** 또는 **단어 복습 1건 이상**을 수행하면 그날은 **학습 완료일(`studied = True`)**로 인정된다.
  - 특정 날짜의 첨삭 건수가 `dailyFeedbackGoal` 이상이고 복습 건수가 `dailyReviewGoal` 이상이면 **일일 목표 100% 달성(`goalMet = True`)**으로 판정한다.
  - **현재 연속 학습일(`currentStreak`)**: 오늘 학습을 이미 했으면 오늘부터 과거로 연속된 학습일 수를 세고, 오늘 아직 학습 전이면 어제부터 과거로 연속된 학습일 수를 유지한다(어제도 학습하지 않았으면 `0`).
  - **최장 연속 학습일(`longestStreak`)**: 전체 학습 기록 중 가장 길게 이어진 연속 학습일 수를 계산한다.
- **[R3] 로컬 자동 저장 및 날짜별 내역 집계**:
  - 하루 목표 설정과 일자별 복습 이력은 `data/routine-settings.json`에 임시 파일 원자적 교체 방식으로 저장되어 새로고침·재시작 후에도 유지된다.
  - 기존 첨삭 기록(`data/feedback-history.json`)과 단어장 기록(`data/vocab-items.json`)의 타임스탬프를 함께 읽어 최근 14일 달력(`recentDays`)과 날짜별 공부 내역을 자동으로 구성한다.

**보장하지 않는 것(알려진 한계)**

- 날짜 기준은 내 PC의 날짜(`YYYY-MM-DD`)를 따르며, PC 시스템 날짜를 임의로 변경하면 연속 학습일 계산 기준일도 함께 바뀐다.

## ③ 받는 입력

- **하루 목표 설정 입력 (`POST /api/routine/goal`)**:
  - `dailyFeedbackGoal` (정수, 필수): `1` 이상 `20` 이하의 정수(하루 목표 첨삭 문장 수, 기본값 `1`).
  - `dailyReviewGoal` (정수, 필수): `1` 이상 `50` 이하의 정수(하루 목표 단어 복습 수, 기본값 `3`).
- 위 조건을 벗어난 입력은 `400 Bad Request`와 한국어 안내 메시지로 거절한다.

## ④ 결정

**정한 것**

- **출석(연속 학습일 유지)과 목표 달성의 2단 구분**: 매일 부담 없이 루틴을 이어갈 수 있도록 **첨삭 1회 또는 단어 복습 1회만 해도 오늘의 연속 학습일(🔥 스트릭)이 유지**되도록 하고, 내가 정한 하루 목표치(예: 첨삭 1문장 + 복습 3단어)를 다 채우면 **`🎉 오늘 목표 달성`** 배지가 추가로 켜지도록 설계했다.
- **복습 이력 일자별 집계**: `VocabItem`은 마지막 복습 시각(`lastReviewedAt`)만 들고 있으므로, 같은 날 여러 단어를 복습하거나 같은 단어를 다른 날 다시 복습한 횟수를 정확히 집계하기 위해 `data/routine-settings.json`에 일자별 복습 완료 기록(`reviewLogs`)을 함께 기록하되, 기존 `VocabItem.lastReviewedAt` 기록도 하위 호환으로 함께 반영한다.

**열어 둔 것**

- 없음.

## ⑤ 검증 계획

- **PR 1 (루틴 계산 · 저장소 · API 자동 시험)**:
  - `tests/test_routine.py`:
    - [R1] 목표 설정 거절 시험: `0`, 음수, 상한 초과(`dailyFeedbackGoal > 20`, `dailyReviewGoal > 50`), 불리언(`True`/`False`), 문자열 입력 시 `400` 거절 확인.
    - [R2] 연속 학습일(스트릭) 및 변조본 대조 시험:
      - 3일 연속 학습 시 `currentStreak = 3`, `longestStreak = 3` 확인.
      - 오늘 아직 안 했어도 어제까지 3일 연속이면 `currentStreak = 3` 유지 확인.
      - 중간에 하루가 비면 `currentStreak`가 끊기고 `longestStreak`에는 이전 최장 기록이 남는지 확인.
    - [R3] 첨삭(`POST /api/feedback`) · 단어 복습(`POST /api/vocab/review`) 호출 시 오늘의 루틴 현황과 최근 14일 달력(`recentDays`), 날짜별 상세 내역이 즉시 갱신되고 재로드 후에도 유지되는지 확인.
- **PR 2 (웹 화면 연결 및 Chrome 브라우저 검증)**:
  - Chrome 브라우저에서 ① 상단 연속 학습 배너 표시, ② 첨삭·단어 복습 후 오늘의 진행률 및 스트릭 즉시 상승, ③ `[🔥 내 학습 루틴 · 기록]` 탭에서 최근 14일 달력·날짜별 학습 내역 조회 및 하루 목표 변경이 정상 동작하는지 확인하고 화면을 캡처한다.

## ⑥ PR 나눔

| PR | 담는 것 | 닫는 것 |
|---|---|---|
| PR 1 | 루틴·스트릭 계산 모듈(`src/routine_types.py`), 루틴 저장·집계 모듈(`src/routine_store.py`), 서버 API(`src/app.py`) 및 자동 시험(`tests/test_routine.py`) | [R1], [R2], [R3] 서버·데이터 계층 |
| PR 2 | 상단 연속 학습 배너, `[🔥 내 학습 루틴 · 기록]` 탭, 최근 14일 달력, 날짜별 학습 상세 내역 및 목표 변경 화면(UI) 연결 | 조각 3 전체 시나리오 및 화면 동작 |
