"""조각 6(api-key-vault) 자동 시험 — 설계 ② 보장 V1 ~ V7.

암호화는 브라우저의 Web Crypto 에서만 돌아서, `tests/vault_harness.mjs` 가 Node 로 `public/standalone-engine.js` 를
가짜 브라우저 저장소 위에서 실제로 돌리고 장면마다 본 것을 내보낸다. 이 파일은 그것을 판정한다.
Node 가 없으면 Node 시험은 건너뛰고 그 이유를 남긴다.

시험 규칙(설계 ⑤): 거절 시험은 거절 뒤 저장 값 전체가 거절 전과 같은지 본다. 성공 시험은 저장 값 이름 목록 전체를 본다.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "tests" / "vault_harness.mjs"
APP_JS = REPO_ROOT / "public" / "app.js"

SALT = "ie_gemini_api_key_salt"
IV = "ie_gemini_api_key_iv"
CIPHER = "ie_gemini_api_key_encrypted"
PLAIN = "ie_gemini_api_key"
SESSION = "ie_gemini_api_key_session"

NODE = shutil.which("node")


def _run_harness() -> dict:
    proc = subprocess.run(
        [NODE, str(HARNESS)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"vault_harness.mjs 실행 실패: {proc.stderr}")
    return json.loads(proc.stdout)


@unittest.skipIf(NODE is None, "Node 가 없어 금고 엔진을 실제로 돌리는 시험을 건너뜁니다 (Node 18 이상 필요)")
class TestSlice6VaultEngine(unittest.TestCase):
    """엔진을 실제로 돌려 V1 · V2 · V3 · V4(첨삭) · V5 · V6 · V7 을 본다."""

    out: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.out = _run_harness()

    def test_v1_encrypted_storage_holds_only_cipher_salt_iv(self) -> None:
        """[V1] 비밀번호와 함께 저장하면 기기 저장소에는 암호문 · 소금 · 초기값 셋만 남고 평문 키는 없다."""
        enc = self.out["encrypted"]
        self.assertTrue(enc["ok"])
        self.assertEqual(set(enc["local"]), {SALT, IV, CIPHER})
        self.assertNotIn(self.out["KEY"], json.dumps(enc["local"]))
        self.assertEqual(len(json.loads(enc["local"][SALT])), 16)
        self.assertEqual(len(json.loads(enc["local"][IV])), 12)

    def test_v1_salt_and_iv_are_new_each_save(self) -> None:
        """[V1] 같은 키 · 같은 비밀번호로 다시 저장해도 소금과 초기값이 새로 뽑힌다."""
        first = self.out["encrypted"]["local"]
        again = self.out["encryptedAgain"]["local"]
        self.assertNotEqual(first[SALT], again[SALT])
        self.assertNotEqual(first[IV], again[IV])
        self.assertNotEqual(first[CIPHER], again[CIPHER])

    def test_v2_wrong_pin_does_not_unlock_or_touch_storage(self) -> None:
        """[V2] 틀린 비밀번호는 풀지 못하고 저장 값을 바꾸지 않는다."""
        wrong = self.out["wrongPin"]
        self.assertFalse(wrong["ok"])
        self.assertFalse(wrong["isUnlocked"])
        self.assertEqual(wrong["local"], self.out["encrypted"]["local"])
        self.assertEqual(wrong["session"], {})

    def test_v2_corrupt_storage_does_not_unlock_or_touch_storage(self) -> None:
        """[V2] 망가진 저장 값은 풀지 못하고 지우지 않는다."""
        corrupt = self.out["corrupt"]
        self.assertFalse(corrupt["ok"])
        self.assertFalse(corrupt["isUnlocked"])
        self.assertEqual(corrupt["local"], corrupt["before"])
        self.assertEqual(corrupt["session"], {})

    def test_v2_right_pin_unlocks(self) -> None:
        """[V2] 맞는 비밀번호는 키를 되살리고, 저장 값은 그대로다."""
        right = self.out["rightPin"]
        self.assertTrue(right["ok"])
        self.assertTrue(right["isUnlocked"])
        self.assertEqual(right["local"], self.out["encrypted"]["local"])
        self.assertEqual(right["session"], {SESSION: self.out["KEY"]})

    def test_v3_reload_keeps_unlock_and_reopen_locks(self) -> None:
        """[V3] 같은 창 새로고침은 해제를 유지하고, 창을 닫았다 열면 잠긴다."""
        self.assertTrue(self.out["reload"]["isUnlocked"])
        reopened = self.out["reopened"]
        self.assertFalse(reopened["isUnlocked"])
        self.assertTrue(reopened["isEncrypted"])
        self.assertEqual(reopened["session"], {})

    def test_v4_locked_feedback_uses_coach_not_gemini(self) -> None:
        """[V4] 잠긴 동안 첨삭 요청은 Gemini 를 부르지 않고 내장 코치 답을 낸다. 풀면 Gemini 를 키 머리글로 부른다."""
        locked = self.out["lockedFeedback"]
        self.assertEqual(locked["status"], 200)
        self.assertTrue(locked["hasCorrected"])
        self.assertEqual(locked["geminiCalls"], [])

        unlocked = self.out["unlockedFeedback"]
        self.assertGreaterEqual(len(unlocked["geminiCalls"]), 1)
        for call in unlocked["geminiCalls"]:
            self.assertEqual(call["apiKeyHeader"], self.out["KEY"])
            self.assertNotIn(self.out["KEY"], call["url"])

    def test_v5_short_pin_is_rejected_without_touching_storage(self) -> None:
        """[V5] 1 ~ 3자 비밀번호는 빈 기기에서도, 금고가 있는 기기에서도 저장하지 않는다."""
        self.assertEqual(self.out["MIN_PIN_LENGTH"], 4)
        empty = self.out["shortPinEmpty"]
        self.assertFalse(empty["ok"])
        self.assertEqual(empty["local"], {})
        self.assertEqual(empty["session"], {})

        vault = self.out["shortPinVault"]
        self.assertFalse(vault["ok"])
        self.assertEqual(vault["local"], vault["before"])

    def test_v5_empty_pin_keeps_plain_storage(self) -> None:
        """[V5] 빈 비밀번호는 조각 standalone-mobile-app 처럼 평문으로 보관한다."""
        plain = self.out["plain"]
        self.assertTrue(plain["ok"])
        self.assertEqual(plain["local"], {PLAIN: self.out["KEY"]})
        self.assertFalse(plain["isEncrypted"])
        self.assertTrue(plain["isUnlocked"])

    def test_v6_clear_removes_all_five_values(self) -> None:
        """[V6] 키 삭제는 평문 키 · 암호문 · 소금 · 초기값 · 해제 상태를 모두 지운다."""
        cleared = self.out["cleared"]
        self.assertEqual(cleared["local"], {})
        self.assertEqual(cleared["session"], {})
        self.assertFalse(cleared["hasApiKey"])

    def test_v7_backup_excludes_vault_values(self) -> None:
        """[V7] 학습 데이터 백업 파일에는 키도 금고 값도 들어가지 않는다."""
        text = self.out["backupText"]
        for name in (PLAIN, SALT, IV, CIPHER, SESSION, self.out["KEY"]):
            self.assertNotIn(name, text)
        enc_local = self.out["encrypted"]["local"]
        self.assertNotIn(enc_local[CIPHER], text)


class TestSlice6VaultScreen(unittest.TestCase):
    """설정 탭 화면 코드(`public/app.js`)를 읽어 V4 · V5 와 설계 ③ 의 입력 갈래를 본다."""

    def setUp(self) -> None:
        self.app = APP_JS.read_text(encoding="utf-8")

    def test_v4_badge_has_locked_state(self) -> None:
        """[V4] 배지 · 안내 줄이 쓸 수 있음 · 잠김 · 없음 셋으로 갈리고, 잠김을 「연결됨」으로 보이지 않는다."""
        self.assertIn("engine.isUnlocked()", self.app)
        self.assertIn("금고 잠김 — 비밀번호로 해제", self.app)
        self.assertIn("금고가 잠겨 있습니다", self.app)
        # 예전 판정(키가 하나라도 있으면 연결됨)이 돌아오지 않았는지
        self.assertNotIn("const hasKey = engine.hasApiKey();", self.app)

    def test_v5_screen_rejects_short_pin_before_saving(self) -> None:
        """[V5] 저장 버튼이 짧은 비밀번호를 엔진에 넘기기 전에 안내하고 멈춘다."""
        guard = self.app.index("pin.length < engine.MIN_PIN_LENGTH")
        save = self.app.index("await engine.saveApiKeyWithPin(val, pin)")
        self.assertLess(guard, save)

    def test_input_branches_of_settings_form(self) -> None:
        """설계 ③ — 해제 갈래(키 없이 비밀번호만)와 빈 입력 안내가 저장 갈래보다 먼저 있다."""
        unlock = self.app.index("if (!val && engine.isEncrypted() && pin)")
        empty = self.app.index("저장할 Gemini API 키를 입력해 주세요.")
        save = self.app.index("await engine.saveApiKeyWithPin(val, pin)")
        self.assertLess(unlock, empty)
        self.assertLess(empty, save)


if __name__ == "__main__":
    unittest.main()
