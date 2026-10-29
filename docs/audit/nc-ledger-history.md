# 부적합 대장 — 지나간 것

**지나간 것**을 든다 — 닫힌 부적합과 회차 절. 닫는 규칙 · 열린 부적합 · 다음 번호는 `docs/audit/nc-ledger.md` 가 든다. 이 파일은
소급해 고치지 않는다 — 뒤 회차가 앞 회차를 뒤집었으면 뒤 절이 그렇게 적는다.

## 닫힌 부적합

살아 있는 쪽에서 닫힘이 된 줄을 옮겨 온다. 글자는 바꾸지 않는다. 번호는 두 표를 가로질러 하나다.

| NC | 무엇 | 낸 회차 | 담당 | 심각도 | 상태 | 판정과 근거 |
|---|---|---|---|---|---|---|
| 1 | 금고를 푼 창에서 비밀번호 없이 새 키를 저장해도 옛 해제 키가 `sessionStorage`(`ie_gemini_api_key_session`)에 남아, 새로고침 뒤 새 키 대신 옛 키가 Gemini 에 가고 설정 탭에도 옛 키 끝 4자가 보인다(`public/standalone-engine.js` 평문 갈래) | 회차 12 | `audit-secrets` | 낮음 | **닫힘** | 저자 판정 고침(2026-10-29) — 조각 api-key-vault 안. 평문 갈래에서 세션 값을 지우고, 시험 `test_v5_plain_save_after_unlock_replaces_old_key` 를 더했다(설계 끝 2026-10-29 항목의 PR 2). 담당 `audit-secrets` 재감사가 닫는다 · 회차 13(`audit-secrets`, 담당) 해소 — 같은 창의 평문 갈래가 세션 값을 지우고 같은 증상으로 가는 다른 길이 같은 창 안에 없음을 봤다 |
| 2 | 다른 탭에서 키를 바꾸거나 지워도, 금고를 풀어 둔 탭은 그 탭을 닫을 때까지(새로고침해도) 옛 키를 쓴다 — 엔진이 다른 탭의 저장소 변화를 듣지 않고, 로드할 때 세션 값을 저장소와 맞춰 보지 않는다(`public/standalone-engine.js` 세션 읽기 · 해제 · 삭제) | 회차 13 | `audit-secrets` | 낮음 | **닫힘** | 저자 판정 반박(2026-10-29) — 폰 앱을 한 창으로 쓰면 생기지 않는 길이라 코드는 두고, 설계 ② 「보장하지 않는 것」에 「다른 탭에서 바꾸거나 지워도 이미 열린 해제 탭은 닫을 때까지 옛 키를 쓴다」를 적고 V6 의 범위를 「누른 그 탭」으로 좁혔다(설계 끝 두 번째 2026-10-29 항목). 담당 `audit-secrets` 재감사가 닫는다 · 회차 14(`audit-secrets`, 담당) 해소 — 한계 문장이 회차 13 의 증상 여섯을 모두 덮고 코드가 그 문장보다 나쁘지 않음을 봤다. **고친 것이 아니라 한계로 받아들여 닫았다** — 코드 결함은 그대로이고, 설치한 앱과 브라우저 탭을 함께 여는 식으로 두 창을 쓰게 되면 다시 볼 자리다 |

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
