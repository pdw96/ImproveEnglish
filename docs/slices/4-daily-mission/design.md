# 조각 4 설계 — daily-mission

설계다 — **어떻게 · 경계.** 무엇을 · 왜는 같은 폴더의 `requirements.md`.

## ① 바뀌는 것

| 파일 | PR | 무엇 |
|---|---|---|
| `src/mission_types.py` | PR 1 | 상황별 미션 항목(`MissionPrompt`), 미션 카테고리 검증(`all`, `work`, `daily`, `travel`, `opinion`), 오늘의 미션 응답(`DailyMissionStatus`) 데이터 구조 및 내장 상황별 미션 풀 모듈 |
| `src/mission_service.py` | PR 1 | 날짜·카테고리·선택 ID에 따른 미션 선정, 내 단어장(`VocabStore`)에서 오늘 써볼 표현(최대 2개) 추출, 오늘 첨삭 기록(`HistoryStore`) 기반 미션 완료 여부(`completedToday`) 집계 모듈 |
| `src/app.py` | PR 1 | 오늘의 상황별 미션 및 추천 단어 조회(`GET /api/mission/today`) API 추가 |
| `tests/test_mission.py` | PR 1 | [M1] 카테고리·미션 ID 입력 검증, [M2] 상황별 미션 선정 및 다른 미션 전환, [M3] 내 단어장 추천 표현(복습 예정 우선 최대 2개) 연동 및 오늘 첨삭 완료 상태 반영 자동 시험 |
| `public/index.html`, `public/app.js`, `public/styles.css` | PR 2 | 첨삭 탭 상단 `🎯 오늘의 영작·말하기 미션` 카드, 상황 카테고리 필터 버튼, `[🔄 다른 미션 보기]`, 추천 표현 클릭 시 입력창 삽입 및 미션 완료 배지 화면(UI) |

1번 조각의 앵커볼트(`src/feedback_types.py`), 2번 조각의 단어장 데이터 구조(`src/vocab_types.py`), 3번 조각의 루틴 데이터 구조(`src/routine_types.py`)는 건드리지 않고 그대로 유지한다.

## ② 보장하는 것 / 보장하지 않는 것

**보장하는 것**

- **[M1] 카테고리 및 미션 선택 파라미터 입력 검증**:
  - `GET /api/mission/today`의 쿼리 파라미터 `category`는 닫힌 목록(`all`, `work`, `daily`, `travel`, `opinion`)만 허용하며(생략 시 `all`), 목록 밖의 값은 `400 Bad Request`로 거절한다.
  - 특정 미션을 지정하는 `missionId` 또는 제외할 `excludeId`가 주어졌을 때 존재하지 않는 미션 ID이면 `400 Bad Request`로 거절한다.
- **[M2] 날짜 기반 기본 미션 및 카테고리별 전환 보장**:
  - 별도 선택이 없으면 오늘 날짜(`YYYY-MM-DD`)를 기준으로 매일 일관된 기본 추천 미션 1개를 반환한다.
  - 특정 `category`를 선택하거나 `excludeId`(현재 보고 있는 미션 제외)를 전달하면 해당 카테고리 안에서 다른 상황 미션을 반환한다.
- **[M3] 내 단어장 표현 추천 및 오늘 미션 완료 상태 연동**:
  - 내 단어장(`VocabStore`)에 저장된 항목 중 **오늘 복습 대상(`isDue = True`)인 표현을 우선**으로, 부족하면 최근 추가된 표현에서 최대 2개를 골라 `vocabSuggestions`(`expression`, `meaning`, `example`)로 함께 반환한다.
  - 오늘 날짜(`YYYY-MM-DD`)에 수행한 AI 첨삭 기록(`HistoryStore`)이 1건 이상 있으면 `completedToday = True`를 반환한다.

**보장하지 않는 것(알려진 한계)**

- 사용자가 작성한 영작문이 미션 주제와 의미상 일치하는지 별도로 채점해 실패 처리하지는 않는다(미션 주제를 참고해 자유롭게 한 문장 이상 첨삭을 받으면 미션 달성으로 인정).

## ③ 받는 입력

- **오늘의 미션 조회 입력 (`GET /api/mission/today`)**:
  - `category` (문자열, 선택, 기본값 `"all"`): `"all"`(전체), `"work"`(비즈니스/업무), `"daily"`(일상 대화), `"travel"`(여행/외출), `"opinion"`(감정/의견) 중 하나.
  - `missionId` (문자열, 선택): 내장 미션 풀에 존재하는 미션 ID.
  - `excludeId` (문자열, 선택): 다른 미션을 뽑을 때 직전 미션을 제외하기 위한 내장 미션 ID.
- 위 닫힌 목록을 벗어난 `category`나 존재하지 않는 `missionId` / `excludeId`는 `400 Bad Request`와 한국어 안내 메시지로 거절한다.

## ④ 결정

**정한 것**

- **내장 상황별 미션 풀 + 내 단어장 하이브리드 구성**: 화면을 열자마자 대기 시간이나 API 비용 없이 미션이 즉시 뜨도록 4개 카테고리(`work`, `daily`, `travel`, `opinion`)의 실전 상황 미션 풀을 내장하고, 여기에 내 단어장의 복습 예정 단어를 `오늘 써볼 추천 표현`으로 결합해 개인화된 미션 카드를 제공한다.
- **표현 칩 클릭 시 영작 입력창 즉시 삽입**: 미션 카드의 기본 힌트 표현이나 내 단어장 추천 표현을 클릭하면 영작 입력창(`#sentenceInput`)에 해당 영어 표현이 자연스럽게 이어 붙여져 타이핑 부담을 줄인다.

**열어 둔 것**

- 없음.

## ⑤ 검증 계획

- **PR 1 (미션 선정 · 단어장 연동 · API 자동 시험)**:
  - `tests/test_mission.py`:
    - [M1] 거절 시험: 허용되지 않은 `category`(예: `invalid`, 빈 값 외 특수문자) 및 존재하지 않는 `missionId` / `excludeId` 요청 시 `400` 거절 확인.
    - [M2] 상황별 미션 선정 및 변조본 대조 시험:
      - 기본 호출 시 오늘의 미션 반환 및 카테고리(`work`, `daily`, `travel`, `opinion`) 필터 시 해당 카테고리 미션만 반환되는지 확인.
      - `excludeId` 전달 시 직전 미션과 다른 미션이 반환되는지 확인.
    - [M3] 단어장 추천 표현(복습 예정 우선 최대 2개) 연동 및 첨삭(`POST /api/feedback`) 후 `completedToday = True` 전환 확인.
- **PR 2 (웹 화면 연결 및 Chrome 브라우저 검증)**:
  - Chrome 브라우저에서 ① 첨삭 탭 상단 `🎯 오늘의 영작·말하기 미션` 카드 및 내 단어장 추천 표현 표시, ② 카테고리 전환 및 `[🔄 다른 미션 보기]` 동작, ③ 추천 표현 칩 클릭 시 입력창 삽입 및 첨삭 후 `✅ 오늘 미션 완료!` 배지 전환을 확인하고 화면을 캡처한다.

## ⑥ PR 나눔

| PR | 담는 것 | 닫는 것 |
|---|---|---|
| PR 1 | 미션 데이터·내장 풀(`src/mission_types.py`), 미션·단어장 연동 서비스(`src/mission_service.py`), 서버 API(`src/app.py`) 및 자동 시험(`tests/test_mission.py`) | [M1], [M2], [M3] 서버·데이터 계층 |
| PR 2 | 첨삭 탭 상단 오늘의 상황별 미션 카드, 카테고리 필터, 다른 미션 보기, 추천 표현 클릭 삽입 및 완료 배지 화면(UI) 연결 | 조각 4 전체 시나리오 및 화면 동작 |
