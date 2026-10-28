"""조각 5(standalone-mobile-app) 자동 시험 — [S1] 온디바이스 엔진·PWA 매니페스트·서비스워커 · [S2] API 키 하드코딩 부재 · [S3] 백업·복원 규약 검증."""

from __future__ import annotations

import json
import pathlib
import re
import unittest

from src.app import FeedbackApp

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestSlice5StandaloneMobileAppGuarantees(unittest.TestCase):
    """설계 ② 보장하는 것 [S1] ~ [S3] 검증 시험."""

    def setUp(self) -> None:
        self.app = FeedbackApp()

    def test_s1_pwa_manifest_service_worker_and_standalone_engine_served(self) -> None:
        """[S1] 모바일 앱 매니페스트(manifest.webmanifest), 아이콘(icon.svg), 서비스워커(sw.js), 온디바이스 엔진(standalone-engine.js)이 정상 제공된다."""
        # 1) manifest.webmanifest 검증
        status_mf, mime_mf, body_mf = self.app.handle_static("/manifest.webmanifest")
        self.assertEqual(status_mf, 200)
        self.assertIn("manifest+json", mime_mf)
        manifest = json.loads(body_mf.decode("utf-8"))
        self.assertEqual(manifest["short_name"], "ImproveEnglish")
        self.assertEqual(manifest["display"], "standalone")
        self.assertIn(manifest["start_url"], ("/", "./"))
        self.assertTrue(len(manifest.get("icons", [])) >= 1)

        # 2) icon.svg 검증
        status_ic, mime_ic, body_ic = self.app.handle_static("/icon.svg")
        self.assertEqual(status_ic, 200)
        self.assertIn("image/svg+xml", mime_ic)
        self.assertIn("<svg", body_ic.decode("utf-8"))

        # 3) sw.js 오프라인 서비스워커 검증
        status_sw, _, body_sw = self.app.handle_static("/sw.js")
        self.assertEqual(status_sw, 200)
        sw_text = body_sw.decode("utf-8")
        self.assertIn("standalone-engine.js", sw_text)
        self.assertIn("caches.open", sw_text)

        # 4) standalone-engine.js 에 조각 1~4의 모든 API 경로 핸들러가 포함되어 있는지 확인
        status_eng, _, body_eng = self.app.handle_static("/standalone-engine.js")
        self.assertEqual(status_eng, 200)
        eng_text = body_eng.decode("utf-8")
        for api_path in (
            "/api/history",
            "/api/feedback",
            "/api/vocab",
            "/api/vocab/review",
            "/api/routine",
            "/api/routine/goal",
            "/api/mission/today",
        ):
            with self.subTest(endpoint=api_path):
                self.assertIn(api_path, eng_text)

    def test_s2_no_hardcoded_api_key_and_uses_header_auth(self) -> None:
        """[S2] 온디바이스 엔진 및 웹 코드 어디에도 실제 Google API 키(AIza...)가 하드코딩되지 않고 x-goog-api-key 헤더만 사용한다."""
        public_dir = REPO_ROOT / "public"
        real_key_pattern = re.compile(r"AIza[0-9A-Za-z\-_]{20,}")

        for file_path in public_dir.glob("*"):
            if file_path.is_file():
                content = file_path.read_text(encoding="utf-8")
                self.assertIsNone(
                    real_key_pattern.search(content),
                    f"{file_path.name} 에 API 키 패턴이 발견되었습니다.",
                )

        eng_text = (public_dir / "standalone-engine.js").read_text(encoding="utf-8")
        self.assertIn('"x-goog-api-key"', eng_text)
        self.assertNotIn("?key=", eng_text)

    def test_s3_mobile_settings_and_backup_restore_ui_present(self) -> None:
        """[S3] 모바일 앱 · 설정 탭, API 키 입력/삭제, 백업 파일(.json) 다운로드·복원 UI가 HTML/JS에 연결되어 있다."""
        status_html, _, raw_html = self.app.handle_static("/")
        html = raw_html.decode("utf-8")
        self.assertEqual(status_html, 200)
        self.assertIn("manifest.webmanifest", html)
        self.assertIn("standalone-engine.js", html)
        self.assertIn("모바일 앱 · 설정", html)
        self.assertIn("내 학습 데이터 백업 파일(.json) 다운로드", html)
        self.assertIn("백업 파일(.json) 불러오기(복원)", html)

        status_js, _, raw_js = self.app.handle_static("/app.js")
        js = raw_js.decode("utf-8")
        self.assertEqual(status_js, 200)
        self.assertIn("setupMobileSettingsAndPwa", js)
        self.assertIn("exportBackupPayload", js)
        self.assertIn("importBackupPayload", js)


if __name__ == "__main__":
    unittest.main()
