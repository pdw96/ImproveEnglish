# 부적합 대장 — 지나간 것

**지나간 것**을 든다 — 닫힌 부적합과 회차 절. 닫는 규칙 · 열린 부적합 · 다음 번호는 `docs/audit/nc-ledger.md` 가 든다. 이 파일은
소급해 고치지 않는다 — 뒤 회차가 앞 회차를 뒤집었으면 뒤 절이 그렇게 적는다.

## 닫힌 부적합

살아 있는 쪽에서 닫힘이 된 줄을 옮겨 온다. 글자는 바꾸지 않는다. 번호는 두 표를 가로질러 하나다.

| NC | 무엇 | 낸 회차 | 담당 | 심각도 | 상태 | 판정과 근거 |
|---|---|---|---|---|---|---|

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

