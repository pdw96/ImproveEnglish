# 부적합 대장 — 지나간 것

**지나간 것**을 든다 — 닫힌 부적합과 회차 절. 닫는 규칙 · 열린 부적합 · 다음 번호는 `docs/audit/nc-ledger.md` 가 든다. 이 파일은
소급해 고치지 않는다 — 뒤 회차가 앞 회차를 뒤집었으면 뒤 절이 그렇게 적는다.

## 닫힌 부적합

살아 있는 쪽에서 닫힘이 된 줄을 옮겨 온다. 글자는 바꾸지 않는다. 번호는 두 표를 가로질러 하나다.

| NC | 무엇 | 낸 회차 | 담당 | 심각도 | 상태 | 판정과 근거 |
|---|---|---|---|---|---|---|
| 1 | 금고를 푼 창에서 비밀번호 없이 새 키를 저장해도 옛 해제 키가 `sessionStorage`(`ie_gemini_api_key_session`)에 남아, 새로고침 뒤 새 키 대신 옛 키가 Gemini 에 가고 설정 탭에도 옛 키 끝 4자가 보인다(`public/standalone-engine.js` 평문 갈래) | 회차 12 | `audit-secrets` | 낮음 | **닫힘** | 저자 판정 고침(2026-10-29) — 조각 api-key-vault 안. 평문 갈래에서 세션 값을 지우고, 시험 `test_v5_plain_save_after_unlock_replaces_old_key` 를 더했다(설계 끝 2026-10-29 항목의 PR 2). 담당 `audit-secrets` 재감사가 닫는다 · 회차 13(`audit-secrets`, 담당) 해소 — 같은 창의 평문 갈래가 세션 값을 지우고 같은 증상으로 가는 다른 길이 같은 창 안에 없음을 봤다 |
| 2 | 다른 탭에서 키를 바꾸거나 지워도, 금고를 풀어 둔 탭은 그 탭을 닫을 때까지(새로고침해도) 옛 키를 쓴다 — 엔진이 다른 탭의 저장소 변화를 듣지 않고, 로드할 때 세션 값을 저장소와 맞춰 보지 않는다(`public/standalone-engine.js` 세션 읽기 · 해제 · 삭제) | 회차 13 | `audit-secrets` | 낮음 | **닫힘** | 저자 판정 반박(2026-10-29) — 폰 앱을 한 창으로 쓰면 생기지 않는 길이라 코드는 두고, 설계 ② 「보장하지 않는 것」에 「다른 탭에서 바꾸거나 지워도 이미 열린 해제 탭은 닫을 때까지 옛 키를 쓴다」를 적고 V6 의 범위를 「누른 그 탭」으로 좁혔다(설계 끝 두 번째 2026-10-29 항목). 담당 `audit-secrets` 재감사가 닫는다 · 회차 14(`audit-secrets`, 담당) 해소 — 한계 문장이 회차 13 의 증상 여섯을 모두 덮고 코드가 그 문장보다 나쁘지 않음을 봤다. **고친 것이 아니라 한계로 받아들여 닫았다** — 코드 결함은 그대로이고, 설치한 앱과 브라우저 탭을 함께 여는 식으로 두 창을 쓰게 되면 다시 볼 자리다 |
| 3 | P8 의 오류 갈래와 코드 · 주석이 다르다 — `FATAL_ERRORS` 에 설계에 없는 `language-not-supported` 가 있고, `no-speech` · `aborted` 말고 다른 오류(`bad-grammar` · 모르는 코드)도 알리지 않고 다시 켠다. 주석 두 곳이 코드보다 좁다(`public/app.js` 오류 목록 · error 처리) | 회차 15 | `audit-internal` | 낮음 | **닫힘** | 저자 판정 고침(2026-10-29) — 조각 speaking-practice 안. PR 6 에서 고쳤다(설계 끝 「감사 회차 15 뒤 덧붙임」). 담당 `audit-internal` 재감사가 닫는다 — 알리지 않고 다시 켜는 오류를 `no-speech` · `aborted` 로 좁히고(`RESTARTABLE_ERRORS`) 그 밖은 안내하고 그만둔다. 시험 P8 을 고쳤다 · 회차 16(`audit-internal`, 담당) 해소 — `RESTARTABLE_ERRORS` 가 no-speech · aborted 뿐이고 그 밖은 안내하고 그만두며, 주석이 덧붙임과 같은 말 |
| 4 | 「말 없음 3번」으로 멈출 때 설계의 안내가, 이미 글이 붙은 듣기에서는 나오지 않는다 — 조건이 `!endNoticeShown && !addedThisListen`(`public/app.js` end 처리) | 회차 15 | `audit-internal` | 낮음 | **닫힘** | 저자 판정 고침(2026-10-29) — 조각 speaking-practice 안. PR 6 에서 고쳤다(설계 끝 「감사 회차 15 뒤 덧붙임」). 담당 `audit-internal` 재감사가 닫는다 — 조건을 `!endNoticeShown` 으로 — 글이 붙었어도 안내한다. 시험 P8 을 고쳤다 · 회차 16(`audit-internal`, 담당) 해소 — 말 없음 안내 조건이 `!endNoticeShown` 하나 — 글을 붙였어도 안내 |
| 5 | `tests/test_speaking.py` 모듈 독스트링이 P10(PR 5)을 빠뜨렸다 | 회차 15 | `audit-internal` | 낮음 | **닫힘** | 저자 판정 고침(2026-10-29) — 조각 speaking-practice 안. PR 6 에서 고쳤다(설계 끝 「감사 회차 15 뒤 덧붙임」). 담당 `audit-internal` 재감사가 닫는다 — 독스트링에 P10 · 임시 진단 빼기 · 회차 15 고침을 더했다 · 회차 16(`audit-internal`, 담당) 해소 — 독스트링에 P10 · 진단 빼기 · 회차 15 고침이 들었다 |
| 6 | `public/app.js` 머리 주석이 조각 1~3 과 그 API 만 말한다 — 미션 · 설정 · 백업 · 음성 인식 · 읽기도 맡는다 | 회차 15 | `audit-internal` | 낮음 | **닫힘** | 저자 판정 고침(2026-10-29) — 조각 speaking-practice 안. PR 6 에서 고쳤다(설계 끝 「감사 회차 15 뒤 덧붙임」). 담당 `audit-internal` 재감사가 닫는다 — 머리 주석에 맡은 조각을 이름으로 적고 미션 · 설정 · 말하기 줄을 더했다 · 회차 16(`audit-internal`, 담당) 해소 — 머리 주석이 맡은 조각 7개를 이름으로 적고 `/api/` 호출이 모두 목록 안 |
| 7 | 조각 7 설계가 다른 조각을 번호로 가리킨다 — 「(조각 1 ~ 5 와 같다)」(`docs/slices/7-speaking-practice/design.md` ④ 첫 줄), 범위도 조각 6 을 빠뜨렸다 | 회차 15 | `audit-internal` | 낮음 | **닫힘** | 저자 판정 고침(2026-10-29) — 조각 speaking-practice 안. PR 6 에서 고쳤다(설계 끝 「감사 회차 15 뒤 덧붙임」). 담당 `audit-internal` 재감사가 닫는다 — 설계는 기록이라 지난 줄은 두고, 설계 끝 덧붙임에 조각 이름으로 바로잡았다 · 회차 16(`audit-internal`, 담당) 해소 — 설계 끝 덧붙임이 조각 6개를 이름으로 바로잡았고, 원 문장은 기록이라 둠 |
| 8 | 「다시 켜기」 중에 브라우저가 시작을 거절하면 「마이크를 켜지 못했습니다」 안내가 나오지 않는다 — 버튼 누름만 안내하고 P8 다시 켜기 타이머는 `isStarting` · `keepListening` 만 되돌린다(`public/app.js` 다시 켜기 타이머) | 회차 16 | `audit-internal` | 낮음 | **닫힘** | 저자 판정 고침(2026-10-29) — 조각 speaking-practice 안. 두 길이 같은 `failStart()` 를 쓰게 했다(PR 6, 설계 끝 「감사 회차 16 뒤 덧붙임」). 시험 P8 · 화면 확인 S2. 담당 `audit-internal` 재감사가 닫는다 · 회차 17(`audit-internal`, 담당) 해소 — 다시 켜기 타이머와 버튼의 catch 가 둘 다 `failStart()` 를 부르고, `recognition.start(` 는 이 두 곳뿐이다 |
| 9 | 맡은 범위를 적은 머리 주석 · 독스트링이 조각 review-quiz 를 빠뜨렸다 — `public/app.js:2-10` · `public/standalone-engine.js:2-6` · `src/app.py:1`(`GET /api/quiz/scores` · 옛 누락 `GET /api/mission/today`) | 회차 19 | `audit-internal` | 낮음 | **닫힘** | 저자 판정(2026-10-31) 고침 — 세 머리글에 review-quiz 와 퀴즈 길 넷 · 백업 퀴즈 칸 · 미션 길을 더했다. NC-6 의 잔여가 아니라 새 기능이 문장을 거짓으로 만든 경우라 새 번호(감사자 판단 그대로). 재감사 대기 · 회차 22(`audit-internal`, 담당) 해소 — 세 머리글이 실제 경로(`app.js` fetch · 엔진 라우트 · 서버 `do_GET`/`do_POST`/`do_DELETE`)와 모두 같다 |
| 10 | `tests/test_quiz.py` 모듈 독스트링이 PR 3 몫(Q6 · Q8)을 빠뜨렸다 | 회차 19 | `audit-internal` | 낮음 | **닫힘** | 저자 판정(2026-10-31) 고침 — 「PR 3 몫: Q6 · Q8, 닫기 전 감사 고침: Q8(NC-12)」를 더했다. 재감사 대기 · 회차 22(`audit-internal`, 담당) 해소 — 독스트링이 실제 클래스 · 시험(PR 3 · NC-12 시험)과 같다 |
| 11 | 「정리」 규칙을 주석(`src/quiz_types.py:37`) · 설계 [Q1] 은 「앞뒤 공백」이라 하는데 코드는 가운데 연속 공백도 하나로 합친다 | 회차 19 | `audit-internal` | 낮음 | **닫힘** | 저자 판정(2026-10-31) 고침 — 글을 코드에 맞췄다: 주석(서버 `normalize_text` · 엔진 `quizNormalize`)과 설계 끝 「2026-10-31 — 닫기 전 감사 뒤 정한 것」에 「앞뒤 공백을 지우고 가운데 연속 공백은 하나로」. 재감사 대기 · 회차 22(`audit-internal`, 담당) 해소 — 주석 둘 · 설계 끝 절이 코드 `" ".join(value.split()).lower()` · `split(/\s+/)…join(" ")` 와 같다 |
| 12 | 백업 불러오기에서 퀴즈를 쓴 뒤 첨삭 · 단어장 · 루틴 쓰기가 실패해도(삼킴) 「복원 완료」가 뜨고 기록이 섞인다 — `public/standalone-engine.js` `importBackupPayload` · `writeJsonStorage` | 회차 20 | `audit-data` | 보통 | **닫힘** | 저자 판정(2026-10-31) 고침 — 네 칸을 한 묶음으로 쓰고, 하나라도 실패하면 이미 바꾼 칸을 불러오기 전 값으로 되돌리고(없던 칸은 지움) 오류를 던진다. 시험 `test_q8_later_save_failure_on_restore_rolls_back_quiz_too`(첨삭 · 단어장 · 루틴 칸 실패 셋, 고치기 전 코드에서 떨어짐, 변조본 넷 모두 떨어짐). 설계 끝 「2026-10-31 — 닫기 전 감사 뒤 정한 것」. 재감사 대기 · 회차 21(`audit-data`, 담당) 해소 — 불러오기가 `writeJsonStorage` 를 쓰지 않고 네 칸을 직접 쓰며, 성공한 칸만 역순으로 되돌리고(없던 칸은 지움) 예외를 던진다. 옛 백업은 퀴즈 칸을 쓰지도 되돌리지도 않는다 |
| 13 | 설계 끝 「코드 주석의 조각 표기」가 「이 조각의 주석은 그렇게 맞췄다」고 했는데 `tests/test_quiz.py:465` 독스트링이 「조각 8」 번호만 쓴다 | 회차 22 | `audit-internal` | 낮음 | **닫힘** | 판정(2026-10-31) 고침 — 업무 영향이 없는 기술 결정이라 프로필 규칙대로 추천안으로 정했다. 독스트링을 「조각 8(review-quiz)」로 맞췄고(같은 꼴을 `src` · `public` · `tests` 전체에서 다시 찾아 남은 자리 없음), 감사의 제안대로 규칙을 `docs/master-plan.md` 조각 나눔 머리말에 한 줄 두었다. 재감사 대기 · 회차 23(`audit-internal`, 담당) 해소 — `tests/test_quiz.py:465` 가 「조각 8(review-quiz)」 꼴이고, `src` · `public` · `tests` 전수에서 조각 8 을 번호만으로 쓴 자리가 없다. 규칙은 `docs/master-plan.md` 조각 나눔 머리말에 섰다 |

## 회차 1 — `audit-secrets` · 조각 1 `ai-feedback` (2026-10-27)

- **감사한 커밋**: `bbf98e2` · **감사자**: `audit-secrets`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 없음 — 첫 회차
- 관찰: 없음
- 담당 없음: 없음

## 회차 2 — `audit-contract` · 조각 1 `ai-feedback` (2026-10-27)

- **감사한 커밋**: `bbf98e2` · **감사자**: `audit-contract`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 없음 — 첫 회차
- 관찰: OB-1 (`POST /api/feedback` 32KB 바이트 상한 및 `Content-Length` 헤더 기반 읽기는 코드에 정의됨), OB-2 (`design.md` 하단 `바뀐 결정` 절에 Python 3.14 파일 경로가 정의됨)
- 담당 없음: 없음

## 회차 3 — `audit-data` · 조각 2 `vocab-review` (2026-10-28)

- **감사한 커밋**: `315216f` · 커밋 안 된 변경 포함 · **감사자**: `audit-data`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 없음 — 첫 회차
- 관찰: OB-1 (`data/vocab-items.json` 수동 편집 등으로 JSON 파싱 실패 시 빈 목록으로 읽힘 — 정상 쓰기 경로는 임시 파일 원자적 교체 사용)
- 담당 없음: 없음

## 회차 4 — `audit-contract` · 조각 2 `vocab-review` (2026-10-28)

- **감사한 커밋**: `315216f` · 커밋 안 된 변경 포함 · **감사자**: `audit-contract`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 회차 2 (`audit-contract`, 열린 NC 및 U 없음)
- 관찰: OB-1 (`POST /api/vocab` 및 `POST /api/vocab/review` 성공 응답에서 최상위 필드와 `item` 중첩 객체를 함께 제공하여 양쪽 클라이언트 접근 방식을 모두 지원함)
- 담당 없음: 없음

## 회차 5 — `audit-data` · 조각 3 `study-routine` (2026-10-28)

- **감사한 커밋**: `5b12815` · 커밋 안 된 변경 포함 · **감사자**: `audit-data`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 회차 3 (`audit-data`, 열린 NC 및 U 없음)
- 관찰: OB-1 (`iso_to_local_date_str`에서 ISO 문자열 앞 10자 추출 기준), OB-2 (`data/routine-settings.json` 수동 편집 파손 시 기본 목표 복구 동작)
- 담당 없음: 없음

## 회차 6 — `audit-contract` · 조각 3 `study-routine` (2026-10-28)

- **감사한 커밋**: `5b12815` · 커밋 안 된 변경 포함 · **감사자**: `audit-contract`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 회차 4 (`audit-contract`, 열린 NC 및 U 없음)
- 관찰: OB-1 (`POST /api/routine/goal` 응답에서 `GET /api/routine`과 동일한 루틴 요약 스키마 전체와 `message`를 함께 반환하여 추가 요청 없이 즉시 화면을 갱신함)
- 담당 없음: 없음

## 회차 7 — `audit-data` · 조각 4 `daily-mission` (2026-10-28)

- **감사한 커밋**: `d6be9e5` · 커밋 안 된 변경 포함 · **감사자**: `audit-data`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 회차 5 (`audit-data`, 열린 NC 및 U 없음)
- 관찰: OB-1 (`GET /api/mission/today`는 내장 상황 미션 풀(`MISSION_POOL`)과 기존 `VocabStore`·`HistoryStore`를 읽기 전용으로 집계하므로 기존 로컬 JSON 파일(`data/vocab-items.json`, `data/feedback-history.json`, `data/routine-settings.json`)의 스키마나 쓰기 경로를 변경하지 않고 완전한 하위 호환성을 유지함)
- 담당 없음: 없음

## 회차 8 — `audit-contract` · 조각 4 `daily-mission` (2026-10-28)

- **감사한 커밋**: `d6be9e5` · 커밋 안 된 변경 포함 · **감사자**: `audit-contract`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 회차 6 (`audit-contract`, 열린 NC 및 U 없음)
- 관찰: OB-1 (`GET /api/mission/today` 쿼리 파라미터 `category`는 닫힌 목록(`all`, `work`, `daily`, `travel`, `opinion`)으로, `missionId`/`excludeId`는 내장 미션 ID 목록으로 엄격히 검증되며 위반 시 기존 API와 동일한 `400 Bad Request` 및 `{"error": "<한국어 메시지>"}` 규약을 따름)
- 담당 없음: 없음

## 회차 9 — `audit-secrets` · 조각 5 `standalone-mobile-app` (2026-10-28)

- **감사한 커밋**: `6b86536` · 커밋 안 된 변경 포함 · **감사자**: `audit-secrets`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 회차 1 (`audit-secrets`, 열린 NC 및 U 없음)
- 관찰: OB-1 (`public/standalone-engine.js` 및 `public/` 내 모든 파일에 하드코딩된 API 키가 없으며, 사용자가 `[모바일 앱 · 설정]` 탭에서 입력한 키는 해당 기기의 `localStorage`(`ie_gemini_api_key`)에만 저장되고 Gemini 호출 시 URL 쿼리가 아닌 `x-goog-api-key` 헤더로만 전송됨)
- 담당 없음: 없음

## 회차 10 — `audit-data` · 조각 5 `standalone-mobile-app` (2026-10-28)

- **감사한 커밋**: `6b86536` · 커밋 안 된 변경 포함 · **감사자**: `audit-data`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 회차 7 (`audit-data`, 열린 NC 및 U 없음)
- 관찰: OB-1 (`importBackupPayload`에서 JSON 객체 여부, `history`·`vocab` 배열 여부, `routine.goal`의 정수 범위(`1~20`, `1~50`)를 먼저 검증한 뒤에만 `localStorage`를 갱신하여 잘못된 백업 파일로부터 기존 기기 데이터를 보호함)
- 담당 없음: 없음

## 회차 11 — `audit-contract` · 조각 5 `standalone-mobile-app` (2026-10-28)

- **감사한 커밋**: `6b86536` · 커밋 안 된 변경 포함 · **감사자**: `audit-contract`
- 기록: `docs/audit/nc-ledger-history.md`
- 낸 것: 없음
- 지난 회차: 회차 8 (`audit-contract`, 열린 NC 및 U 없음)
- 관찰: OB-1 (`public/standalone-engine.js`의 `handleLocalApiRequest`가 기존 파이썬 서버의 9개 `/api/*` 경로(`GET /api/history`, `POST /api/feedback`, `GET/POST /api/vocab`, `POST /api/vocab/review`, `DELETE /api/vocab/<id>`, `GET /api/routine`, `POST /api/routine/goal`, `GET /api/mission/today`)와 100% 동일한 JSON 응답 필드·상태 코드를 반환하여 프론트엔드 코드 변경 없이 단독 실행과 서버 연동을 모두 지원함)
- 담당 없음: 없음

## 회차 12 — `audit-secrets` · 조각 6 `api-key-vault` (2026-10-29)

- **감사한 커밋**: 모름(기록 머리 — 감사자가 본 작업 트리 머리는 `71011d7`, 브리핑 없음) · **감사자**: `audit-secrets`
- 기록: `.claude/audits/audit-secrets-2026-10-29-075446.md`
- 낸 것: NC-1(낮음) · U-1 · U-2
- 지난 회차: 회차 1 · 회차 9 (`audit-secrets`, 이어 받은 NC · U 없음)
- 관찰: OB-1(해제 중 설정 탭이 키 앞 4자 · 뒤 4자를 보인다) · OB-2(이미 해제된 창에서는 아무 비밀번호나 「해제되었습니다」가 된다) · OB-3(설정 카드 문구가 설계 ② 의 한계보다 강하게 말한다 — 키는 첨삭마다 Google 로 가고, 4자리 PIN 은 저장소 복사에 풀린다) · OB-4(PBKDF2 100,000회는 OWASP 2023 권장 600,000회보다 낮다 — 설계 ④ 에서 저자가 고른 값)
- 담당 없음: 없음
- 판정(2026-10-29, 저자): NC-1 고침 · U-1 닫힘(다른 Pages 사이트 없음) · U-2 저자 기기 확인 대기
- 판정 덧붙임(2026-10-29, 저자): U-2 닫힘 — 저자 Android 폰에서 밀어 닫기 · 브라우저 재시작 · 탭 복제 뒤 모두 잠김

## 회차 13 — `audit-secrets` · 조각 6 `api-key-vault` 재감사 (2026-10-29)

- **감사한 커밋**: 모름(기록 머리 — 감사자가 본 작업 트리 머리는 `c46133d`, 브리핑 없음) · **감사자**: `audit-secrets`
- 기록: `.claude/audits/audit-secrets-2026-10-29-082250.md`
- 낸 것: NC-2(낮음)
- 지난 회차: 회차 12 — NC-1 해소(담당이라 닫힘) · U-1 해소(닫힘 유지) · U-2 해소(닫힘 유지)
- 관찰: OB-1(암호화 저장 · 해제 갈래는 세션 쓰기가 실패하면 옛 해제 키를 남긴다 — 실제로 일어날 조건이 없다) · OB-2(오프라인이면 고치기 전 엔진이 캐시에서 돌 수 있다 — 고침이 기기에 닿는 것은 온라인으로 다시 로드할 때)
- 담당 없음: 저장이 예외로 끝나면 설정 탭에 아무 안내가 없다(`public/app.js` 저장 버튼) — 저자가 조각 api-key-vault 안에서 고치기로 정했다(2026-10-29, 설계 끝 두 번째 2026-10-29 항목의 PR 3)
- 판정(2026-10-29, 저자): NC-2 반박(한계로 적음)

## 회차 14 — `audit-secrets` · 조각 6 `api-key-vault` 재감사 (2026-10-29)

- **감사한 커밋**: 모름(감사자가 본 작업 트리 머리는 `c46133d`, 브리핑 없음, 커밋 안 된 변경은 diff 없이 지금 파일로 판정) · **감사자**: `audit-secrets`
- 기록: `.claude/audits/audit-secrets-2026-10-29-082816.md`
- 낸 것: 없음
- 지난 회차: 회차 13 — NC-2 해소(담당이라 닫힘, 한계로 받아들여 닫음 · 코드는 그대로)
- 관찰: OB-1(이미 풀린 탭에서는 한 창에서도 아무 비밀번호에나 「해제되었습니다」가 나온다 — 회차 12 OB-2 와 같은 것, 두 번째) · OB-2(저장이 실패하면 키와 비밀번호가 그 탭의 입력칸에 남는다 — 설계 PR 3 이 고른 동작) · OB-3(저장 실패 안내는 엔진이 삼키는 세션 쓰기 실패에는 닿지 않는다 — 회차 13 OB-1 과 같은 것, 두 번째)
- 담당 없음: 없음

## 회차 15 — `audit-internal` · 조각 7 `speaking-practice` (2026-10-29)

- **감사한 커밋**: 모름(작업 트리 머리 `b3f6745`, 브리핑 없음) — 호출자 덧붙임: `b3f6745` 과 main `9c921e8` 은 파일 내용이 같다 · **감사자**: `audit-internal`
- 기록: `.claude/audits/audit-internal-2026-10-29-135500.md`
- 낸 것: NC-3 · NC-4 · NC-5 · NC-6 · NC-7(모두 낮음) · U-3 · U-4
- 지난 회차: 없음 — `audit-internal` 의 첫 회차
- 관찰: OB-1([듣기] 목소리 고르기가 `en_US` 꼴도 받는다 — 같은 지역 코드) · OB-2(요구사항 성공 기준 셋째 줄은 설계 덧붙임으로 바뀌었고 요구사항에는 옛 문구가 남았다 — 기록이라 맞다. 「닫으며」는 새 문구로 대어 본다)
- 담당 없음: 듣기 시작을 브라우저가 거절하면 `keepListening` 이 남아 한 번 헛누름이 된다(`public/app.js` 말하기 버튼) — 저자가 조각 speaking-practice 안에서 고치기로 정했다(2026-10-29, 설계 끝 「감사 회차 15 뒤 덧붙임」의 PR 6)
- 판정(2026-10-29, 저자): NC-3 ~ NC-7 고침

## 회차 16 — `audit-internal` · 조각 7 `speaking-practice` 재감사 (2026-10-29)

- **감사한 커밋**: `abebd8d`(브리핑 — 호출자가 만든 diff 파일 A · A-2 · B, 커밋 안 된 변경은 확인 못 함) · **감사자**: `audit-internal`
- 기록: `.claude/audits/audit-internal-2026-10-29-141200.md`
- 낸 것: NC-8(낮음) · U-5
- 지난 회차: 회차 15 — NC-3 · NC-4 · NC-5 · NC-6 · NC-7 해소(담당이라 닫힘) · U-3 판정 적합(닫힘) · U-4 유지(1회차째 멈춤)
- 관찰: OB-1(조각 7 밖의 옛 글은 아직 조각을 번호로 가리킨다 — 소급하지 않음, `verify-docs.py` 에 검사를 세울 수 있다) · OB-2(요구사항 성공 기준 셋째 줄의 옛 문구 — 회차 15 OB-2 와 같은 것, 두 번째) · OB-3(요구사항 머리말의 ADR 틀 문구와 설계 「ADR 을 두지 않는다」) · OB-4(시험 주석 두 곳이 고친 뒤 오류 갈래보다 좁게 말한다)
- 담당 없음: 없음
- 판정(2026-10-29, 저자): NC-8 고침

## 회차 17 — `audit-internal` · 조각 7 `speaking-practice` 재감사 (2026-10-29)

- **감사한 커밋**: `d2942c6`(브리핑 — 호출자가 만든 diff 파일: U-5 거르지 않은 stat · U-4 본문 diff · NC-8 diff, 커밋 안 된 변경은 확인 못 함) · **감사자**: `audit-internal`
- 기록: `.claude/audits/audit-internal-2026-10-29-143000.md`
- 낸 것: 없음
- 지난 회차: 회차 16 — NC-8 해소(담당이라 닫힘) · U-4 판정 적합(닫힘, 1회차 멈춘 뒤) · U-5 판정 적합(닫힘)
- 관찰: OB-1(옛 글의 조각 번호 — 이어짐) · OB-2(요구사항 성공 기준 셋째 줄 옛 문구 — 세 번째) · OB-3(ADR 틀 문구 — 이어짐) · OB-4(P8 시험 독스트링이 그만두는 경우를 다 들지 않는다 — 넓어짐) · OB-5(`failStart` 주석이 회차 15 덧붙임만 가리킨다) · OB-6(⑥ PR 6 줄의 닫는 것에 NC-8 이 없다 — 덧붙임에만 있다)
- 담당 없음: 없음
- 다음 회차 몫: 없음 — 담당 `audit-internal` 의 열린 줄이 없다. OB-4 · OB-5 주석은 이 회차 등록 커밋에서 다듬었다

## 회차 18 — `audit-secrets` · 조각 8 `review-quiz` 닫기 전 (2026-10-31)

- **감사한 커밋**: `248838c`(브리핑 — 호출자가 만든 `c3599f8..248838c` stat · code.diff · docs.diff · commits, 커밋 안 된 변경은 확인 못 함) · **감사자**: `audit-secrets`
- 기록: `.claude/audits/audit-secrets-2026-10-31-051813.md`
- 낸 것: 없음
- 지난 회차: 회차 14 — U-1 · U-2 닫힘 유지(다시 열 사유 없음)
- 관찰: OB-1(PC 서버가 켜져 있으면 같은 PC 브라우저의 다른 사이트가 `POST /api/quiz/today` 를 보내 내 키로 AI 를 한 번 부르게 할 수 있다 — 키는 어느 응답에도 실리지 않고 하루 한 세트로 묶인다. 조각 ai-feedback 의 `POST /api/feedback` 에도 같은 길이 있다. 조각 ai-provider-choice 착공 때 `Origin` 검사를 규칙으로 세울지 정한다)
- 담당 없음: 없음

## 회차 19 — `audit-internal` · 조각 8 `review-quiz` 닫기 전 (2026-10-31)

- **감사한 커밋**: `248838c`(브리핑 — 회차 18 과 같은 파일) · **감사자**: `audit-internal`
- 기록: `.claude/audits/audit-internal-2026-10-31-052042.md`
- 낸 것: NC-9 · NC-10 · NC-11(모두 낮음)
- 지난 회차: 회차 17 — 이어 받을 열린 줄 없음. U-3 · U-4 · U-5 닫힘 유지. 회차 17 OB-1(옛 글의 조각 번호) · OB-3(ADR 틀 문구) 이어짐(세 번째)
- 관찰: OB-1(`MINE_DEFAULT_COUNT = 7` 을 쓰는 곳이 없다) · OB-2(성공 기준 「보기를 누르면 … 다음 문제로 넘어간다」를 [다음 문제] 버튼으로 구현 — 문서가 정하지 않음) · OB-3(퀴즈 카드 안내 글이 AI 새 문제를 말하지 않는다) · OB-4(요구사항 머리말 「ADR」 대 설계 「ADR 을 두지 않는다」, 세 번째) · OB-5(설계 ⑤ 저자 실제 기기 확인은 닫는 기록에 들어가야 한다)
- 문서에 없어서 판정 못 한 것: 「AI 새 문제는 한 세트에 한 번」이 모델 후보 넘김을 몇 번으로 세는가 · 백업 `quiz` 검증이 설계 ③ 보다 더 막는 셋(`bestScore < firstScore` · 같은 날짜 둘 · `createdAt` 없음) · 「조각을 번호가 아니라 이름으로」가 코드 주석에도 걸리는가(세 번째)
- 담당 없음: 없음
- 판정(2026-10-31, 저자): NC-9 · NC-10 · NC-11 고침 · OB-3 카드 안내 글을 AI 새 문제까지 말하게 바꿈. 기술 결정(설계 끝 「2026-10-31 — 닫기 전 감사 뒤 정한 것」): NC-11 은 글을 코드에 맞춤 · 「한 번」은 한 번의 요청 묶음(후보 넘김은 첨삭과 같음) · 코드 주석도 번호를 쓰면 이름을 함께 씀(이 조각 주석을 맞춤)

## 회차 20 — `audit-data` · 조각 8 `review-quiz` 닫기 전 (2026-10-31)

- **감사한 커밋**: `248838c`(브리핑 — 회차 18 과 같은 파일) · **감사자**: `audit-data`
- 기록: `.claude/audits/audit-data-2026-10-31-052209.md`
- 낸 것: NC-12(보통 — 기록 안의 번호는 NC-9, 회차 19 와 같은 때 돌아 대장에서 다시 매김) · U-6
- 지난 회차: 회차 10 — 이어 받을 줄 없음
- 관찰: OB-1(깨진 저장 파일 · 키를 「기록 없음」으로 읽고 덮는다 — 회차 3 OB-1 · 회차 5 OB-2 에 이어 세 번째) · OB-2(AI 문제의 대상 표현이 내 표현 모음에 있는지는 보지 않는다 — 설계 ② 「모양만 검증」) · OB-3(백업의 `today` 세트 날짜에 위쪽 한도가 없다 — 미래 날짜 세트면 그날까지 새 세트가 안 열림)
- 담당 없음: 없음. 「안 본 것」에 `audit-contract` 몫으로 서버가 더 새 세트를 돌려줄 때 점수 줄을 요청 날짜로 찾는 것(`app.py:334`)을 남겼다 — 만들기 잠금 안에서 다시 확인하므로 한 서버 안에서는 닿지 않는다(호출자 확인)
- 판정(2026-10-31, 저자): NC-12 고침 · OB-1 은 마스터플랜 후보 조각 storage-safety 로 넘김. U-6 은 호출자가 git 근거를 붙였다(대장 U-6 줄) — 담당 회차 판정 대기

## 회차 21 — `audit-data` · 조각 8 `review-quiz` 재감사 (2026-10-31)

- **감사한 커밋**: `3de9c20`(브리핑 — 호출자가 만든 `248838c..3de9c20` stat · 고침 diff, U-6 근거 `ec0e41c..248838c` diff, 커밋 안 된 변경은 확인 못 함) · **감사자**: `audit-data`
- 기록: `.claude/audits/audit-data-2026-10-31-053117.md`
- 낸 것: 없음
- 지난 회차: 회차 20 — NC-12 해소(담당이라 닫힘) · U-6 판정 적합(닫힘)
- 관찰: OB-1(되돌리는 쓰기의 실패는 삼키고 그때도 「불러오기 전 그대로」라 알린다 — 설계가 보장하지 않는다고 적었고, 역순으로 되돌려 같은 탭에서는 저장 공간 초과로 닿지 않는다. 되돌리는 순서를 바꾸면 이 성질이 깨진다)
- 담당 없음: 없음. 「안 본 것」에 단독 앱의 다른 쓰기 길(첨삭 저장 · 단어장 추가 · 복습 · 하루 목표)이 저장 공간 초과를 삼키는 것을 남겼다 — 조각 5 이래의 길. 호출자 판단(2026-10-31): 후보 조각 storage-safety 를 착공할 때 함께 본다(그 줄의 범위는 착공 때 정한다)

## 회차 22 — `audit-internal` · 조각 8 `review-quiz` 재감사 (2026-10-31)

- **감사한 커밋**: `3de9c20`(브리핑 — 회차 21 과 같은 stat · 고침 diff) · **감사자**: `audit-internal`
- 기록: `.claude/audits/audit-internal-2026-10-31-053157.md`
- 낸 것: NC-13(낮음)
- 지난 회차: 회차 19 — NC-9 · NC-10 · NC-11 해소(담당이라 닫힘). 회차 19 OB-3 은 저자 판정으로 바뀜, OB-1 · OB-2 · OB-5 그대로, OB-4(ADR 머리말) 이어짐(네 번째)
- 관찰: 없음
- 문서에 없어서 판정 못 한 것: 코드 주석의 조각 표기 규칙이 조각 8 설계에만 있다(→ 호출자가 `docs/master-plan.md` 조각 나눔 머리말에 한 줄 둠) · 백업 `quiz` 검증이 설계 ③ 보다 더 막는 셋(이어짐) · 요구사항 머리말 「ADR」 대 설계 「ADR 을 두지 않는다」(네 번째)
- 담당 없음: 없음
- 판정(2026-10-31): NC-13 고침(기술 결정)

## 회차 23 — `audit-internal` · 조각 8 `review-quiz` 재감사 (2026-10-31)

- **감사한 커밋**: `4346094`(브리핑 — 호출자가 만든 `3de9c20..4346094` stat · `tests` · `docs/master-plan.md` diff, 커밋 안 된 변경은 확인 못 함) · **감사자**: `audit-internal`
- 기록: `.claude/audits/audit-internal-2026-10-31-053703.md`
- 낸 것: U-7
- 지난 회차: 회차 22 — NC-13 해소(담당이라 닫힘). 회차 19 OB-1 그대로, OB-4(ADR 머리말) 이어짐(다섯 번째)
- 관찰: 없음
- 문서에 없어서 판정 못 한 것: 마스터플랜의 새 규칙에 「옛 글은 소급하지 않는다」가 빠짐(→ 호출자가 그 줄에 더함) · NC 판정을 가르는 사람이 대장(「저자」)과 `Profile.md`(업무 영향 없는 기술 결정은 추천안으로)에서 겹침 — NC-13 이 처음으로 프로필 위임 판정 · 닫힌 U 줄도 지나간 쪽으로 옮기는가(지금은 살아 있는 쪽 표에 둠) · ADR 머리말(다섯 번째) · 백업 `quiz` 검증이 설계 ③ 보다 더 막는 셋(이어짐)
- 담당 없음: 없음

## 회차 24 — `audit-internal` · 조각 8 `review-quiz` 재감사 (2026-10-31)

- **감사한 커밋**: `ab91b9f`(브리핑 — 호출자가 만든 `3de9c20..ab91b9f` 대장 diff · `4346094..ab91b9f` 마스터플랜 diff, 같은 회차 덧붙임에서 `4346094..ab91b9f` 대장 diff 와 거르지 않은 stat) · **감사자**: `audit-internal`
- 기록: `.claude/audits/audit-internal-2026-10-31-054101.md`(끝에 같은 회차 덧붙임)
- 낸 것: U-8(같은 회차에 근거를 받아 닫힘)
- 지난 회차: 회차 23 — U-7 판정 적합(닫힘). 회차 23 「문서에 없어서」 ①(소급 한정)은 문서가 정함, ②(판정하는 사람이 대장과 프로필에서 겹침) · ③(닫힌 U 줄을 옮기는가) 그대로
- 관찰: 없음
- 담당 없음: 없음
- 다음 회차 몫: 없음 — 담당 `audit-internal` · `audit-data` · `audit-secrets` 의 열린 줄이 없다
