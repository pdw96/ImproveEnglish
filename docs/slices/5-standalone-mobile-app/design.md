# 조각 5 설계 — standalone-mobile-app

설계다 — **어떻게 · 경계.** 무엇을 · 왜는 같은 폴더의 `requirements.md`.

## ① 바뀌는 것

| 파일 | PR | 무엇 |
|---|---|---|
| `public/standalone-engine.js` | PR 1 | 서버 없이 동작하는 온디바이스 엔진 — `localStorage` 기반 학습 데이터(첨삭·단어장·루틴·미션) 저장소, 브라우저 직접 Gemini REST 호출(`x-goog-api-key` 헤더 사용) 및 내장 스마트 코치 폴백, 백업 JSON 내보내기·검증·복원, `/api/*` 자동 인터셉터 모듈 |
| `public/manifest.webmanifest`, `public/icon.svg`, `public/sw.js` | PR 1 | 모바일 홈 화면 앱 설치 및 구글 플레이 패키징(PWA / TWA / Capacitor)을 위한 앱 매니페스트, 벡터 앱 아이콘, 오프라인 캐시 서비스 워커 |
| `public/index.html`, `public/app.js`, `public/styles.css` | PR 2 | 상단 `[⚙️ 앱 설정 · 백업]` 탭, 온디바이스/서버 동작 모드 배지, 기기 내 Gemini API 키 설정·삭제 폼, 학습 기록 백업(`.json`) 다운로드·불러오기 UI 및 모바일 하단/터치 최적화 |
| `src/app.py` | PR 1 | `manifest.webmanifest` 및 `sw.js`, `icon.svg` MIME 타입 정적 서빙 지원 보강 |
| `tests/test_mobile_app.py` | PR 1 | [S1] 매니페스트·서비스워커·온디바이스 엔진 제공 및 정적 리소스 검증, [S2] API 키 하드코딩 부재 및 백업 데이터 스키마 호환성 자동 시험 |

1번 조각의 앵커볼트(`src/feedback_types.py`) 및 조각 1~4의 서버 API 규약은 건드리지 않고 그대로 유지하며, 온디바이스 엔진(`public/standalone-engine.js`)이 동일한 요청·응답 계약을 클라이언트 내부에서 수행한다.

## ② 보장하는 것 / 보장하지 않는 것

**보장하는 것**

- **[S1] 서버 없는 100% 단독 실행 보장 (온디바이스 API 엔진)**:
  - 백엔드 서버가 없거나 네트워크가 끊긴 상태(또는 사용자가 '모바일 단독 모드'를 켠 상태)에서도 `/api/feedback`, `/api/history`, `/api/vocab`, `/api/vocab/review`, `/api/routine`, `/api/routine/goal`, `/api/mission/today` 요청을 온디바이스 엔진이 가로채어 기기 내 `localStorage`에서 동일 규약으로 즉시 응답한다.
- **[S2] 기기 내 API 키 안전 보관 및 하드코딩 금지**:
  - 저장소 코드 어디에도 API 키를 하드코딩하지 않는다.
  - 사용자가 `[⚙️ 앱 설정 · 백업]` 탭에 입력한 Gemini API 키는 해당 스마트폰 브라우저의 `localStorage`(`ie_gemini_api_key`)에만 저장되며, Gemini API 호출 시 URL 쿼리가 아닌 `x-goog-api-key` HTTP 헤더로만 전송한다.
  - API 키가 설정되지 않았거나 오프라인·할당량 초과(402/429) 상태일 때는 온디바이스 내장 스마트 코치가 3단 첨삭(`corrected`, `explanation`, `alternatives` 2~3개, `keyExpressions`)을 즉시 생성해 학습이 멈추지 않도록 보장한다.
- **[S3] 학습 기록 백업 및 복원 무결성**:
  - 첨삭 기록(`history`), 단어장(`vocab`), 루틴 설정 및 복습 로그(`routine`) 전체를 하나의 JSON 파일로 내보내고(Download), 다시 불러올 때(Import) 필수 배열·객체 구조를 검증한 뒤 복원한다. 잘못된 JSON이나 규약 밖의 파일은 거절하고 기존 데이터를 보존한다.

**보장하지 않는 것(알려진 한계)**

- 스마트폰 브라우저의 사이트 데이터(캐시·저장소)를 사용자가 강제로 전체 초기화하면 기기 내 `localStorage` 기록도 함께 지워지므로, 기기 초기화 전에는 백업 파일 다운로드 기능을 사용해야 한다.

## ③ 받는 입력

- **온디바이스 API 키 설정 입력**:
  - `apiKey` (문자열): 공백 제거 후 비어 있지 않은 문자열(저장 시 기기 `localStorage`에 보관, 비워서 초기화 가능).
- **학습 데이터 백업 복원 입력 (JSON 파일)**:
  - `version` (정수, 선택): 백업 포맷 버전(`1`).
  - `history` (배열, 필수): 첨삭 기록 배열.
  - `vocab` (배열, 필수): 단어장 항목 배열.
  - `routine` (객체, 필수): `goal`(`dailyFeedbackGoal` 1~20, `dailyReviewGoal` 1~50) 및 `reviewLogs` 배열.
- 위 형식을 만족하지 않는 백업 파일은 복원하지 않고 한국어 오류 메시지로 거절한다.

## ④ 결정

**정한 것**

- **Fetch 인터셉터 기반 하이브리드 온디바이스 아키텍처**: 기존 `public/app.js`의 화면 제어 코드를 중복 작성하지 않고, `public/standalone-engine.js`가 `/api/*` 요청을 처리할 수 있게 구성한다.
  - 사용자가 **모바일 단독 모드(기본값: 서버 미응답 시 자동 전환 또는 설정에서 강제 활성화)**를 쓰면 서버 네트워크 요청 없이 스마트폰 내부에서 0.01초 만에 단어장·루틴·미션이 동작한다.
- **PWA + 구글 플레이 패키징(`manifest.webmanifest` + `sw.js`)**: 별도 빌드 도구 없이도 스마트폰 크롬에서 즉시 **[앱 설치]**가 가능하고, 무료 도구인 **PWABuilder** 또는 **Capacitor**에 넣으면 곧바로 구글 플레이 스토어 등록용 `.aab` / `.apk` 파일이 생성되도록 표준 매니페스트를 구성한다.

**열어 둔 것**

- 없음.

## ⑤ 검증 계획

- **PR 1 & PR 2 통합 자동 시험 (`tests/test_mobile_app.py`)**:
  - [S1] `manifest.webmanifest`, `sw.js`, `icon.svg`, `standalone-engine.js` 정적 서빙 및 필수 PWA 매니페스트 필드(`name`, `short_name`, `display: "standalone"`, `start_url`, `icons`) 검증.
  - [S2] 저장소 전체 파일에 실제 API 키 패턴(`AIza...`)이 하드코딩되지 않았음을 검증하고, 온디바이스 엔진에 조각 1~4의 모든 엔드포인트 핸들러와 백업·복원 검증 로직이 포함되어 있는지 확인.

## ⑥ PR 나눔

| PR | 담는 것 | 닫는 것 |
|---|---|---|
| PR 1 | 온디바이스 엔진(`public/standalone-engine.js`), PWA 매니페스트·아이콘·서비스워커(`public/manifest.webmanifest`, `public/icon.svg`, `public/sw.js`), 서버 MIME 보강(`src/app.py`) | [S1], [S2], [S3] 코어 엔진 및 모바일 앱 규격 |
| PR 2 | `[⚙️ 앱 설정 · 백업]` 탭, API 키 설정·삭제, 백업 파일 내보내기·불러오기 UI, 모바일 앱 설치 안내 및 자동 시험(`tests/test_mobile_app.py`) | 조각 5 전체 시나리오 및 모바일 앱 완성 |
