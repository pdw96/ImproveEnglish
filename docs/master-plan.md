# ImproveEnglish 마스터플랜

**살아 있는 문서**다. 다른 문서가 든 값은 옮겨 적지 않고 가리킨다. 여기가 직접 드는 것은 조각 나눔과 범위 변경뿐이다.

## 가리키는 문서

| 무엇 | 어디 |
|---|---|
| 의도 — Why · What · Not | `INTENT.md` |
| 시스템 구조 | 없음 — 첫 조각 착공 시 정한다 |
| 데이터 모델 | 없음 — 첫 조각 착공 시 정한다 |
| 작업 규칙과 앵커볼트 | `GEMINI.md` · `CLAUDE.md` |
| 절차 | 없음 — vibe-slice 플러그인 절차를 따른다 |
| 조각의 요구사항 · 설계 | `docs/slices/` |

## 조각 나눔

`순서` 가 `—` 이면 순서를 매기지 않은 후보다. 일하다 새 조각이 필요하면 그 자리에서 만들지 않고 여기 한 줄을
더한다. 다른 문서는 조각을 번호가 아니라 이름으로 가리킨다.

| 순서 | 조각 | 목표 한 줄 | 의존 | 상태 | 조각 폴더 |
|---|---|---|---|---|---|
| 1 | ai-feedback | 내가 쓴 영작문·말하기 문장에 대해 AI 첨삭과 자연스러운 표현 추천을 받는다 | — | 닫힘 | `docs/slices/1-ai-feedback/` |
| 2 | vocab-review | 첨삭받은 표현과 모르는 단어를 저장하고 복습 주기에 맞춰 다시 학습한다 | ai-feedback | 닫힘 | `docs/slices/2-vocab-review/` |
| 3 | study-routine | 매일 학습한 기록과 연속 학습 루틴을 확인하고 관리한다 | ai-feedback | 닫힘 | `docs/slices/3-study-routine/` |
| 4 | daily-mission | 매일 상황별 영작·말하기 미션과 내 단어장의 써볼 표현을 추천받고 바로 첨삭 연습으로 이어간다 | ai-feedback · vocab-review | 닫힘 | `docs/slices/4-daily-mission/` |
| 5 | standalone-mobile-app | 별도 서버 없이 스마트폰 기기 자체에 학습 기록·API 키를 저장하고 앱으로 설치해 언제든 학습한다 | ai-feedback · vocab-review · study-routine · daily-mission | 닫힘 | `docs/slices/5-standalone-mobile-app/` |
| 6 | api-key-vault | 스마트폰에 보관한 Gemini API 키를 내 비밀번호로 암호화해 잠가 두고, 쓸 때만 풀어 쓴다 | standalone-mobile-app | 닫힘 | `docs/slices/6-api-key-vault/` |
| 7 | speaking-practice | 길게 이어 말한 영어를 실시간 글자로 보며 입력하고, 첨삭받은 문장 · 표현을 원어민 발음으로 들어 본다 | ai-feedback | 닫힘 | `docs/slices/7-speaking-practice/` |

## 범위 변경

| 날짜 | 무엇을 | 왜 | 어느 조각에서 |
|---|---|---|---|

없음.
