"""조각 7(speaking-practice) 정적 시험 — 설계 ② 보장 [P1] ~ [P4](PR 1).

이 레포 시험은 Python 이라 브라우저 음성 기능을 돌리지 못한다. `public/app.js` · `public/index.html` 을 읽어
보장마다 「있어야 할 장치」와 「없어야 할 옛 장치」를 함께 본다. 실제 동작은 PR 마다 Chromium 화면 확인으로 본다(설계 ⑤).
"""

from __future__ import annotations

import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_JS = (REPO_ROOT / "public" / "app.js").read_text(encoding="utf-8")
INDEX_HTML = (REPO_ROOT / "public" / "index.html").read_text(encoding="utf-8")


def speech_block() -> str:
    """`setupSpeechRecognition` 함수 몸만 잘라 낸다 — 다른 함수의 글자에 우연히 맞지 않게."""
    start = APP_JS.index("function setupSpeechRecognition()")
    end = APP_JS.index("\n  function ", start + 1)
    return APP_JS[start:end]


def handler(block: str, name: str) -> str:
    """`recognition.addEventListener("<name>", ...)` 의 몸."""
    start = block.index(f'recognition.addEventListener("{name}"')
    end = block.index("\n    });", start)
    return block[start:end]


class TestSlice7SpeakingPracticePR1(unittest.TestCase):
    """설계 ② 보장하는 것 [P1] ~ [P4]."""

    def setUp(self) -> None:
        self.block = speech_block()

    def test_p1_continuous_listening_appends_each_final_once(self) -> None:
        """[P1] 이어 듣기를 켜고, 확정 결과는 결과 번호로 한 번만 입력창 끝에 붙인다(옛 「첫 결과만」 꼴은 없다)."""
        self.assertRegex(self.block, r"recognition\.continuous\s*=\s*true")
        self.assertNotRegex(self.block, r"recognition\.continuous\s*=\s*false")
        result = handler(self.block, "result")
        self.assertIn("isFinal", result)
        self.assertRegex(result, r"appendedResults\.has\(i\)")
        self.assertRegex(result, r"appendedResults\.add\(i\)")
        self.assertIn("appendVoiceText(", result)
        # 옛 꼴 — 매번 첫 결과만 읽던 줄
        self.assertNotIn("event.results[0][0]", result)
        # 새로 누를 때 번호 기억을 비운다(새 듣기는 번호가 0 부터다)
        self.assertRegex(self.block, r"appendedResults\s*=\s*new Set\(\)")

    def test_p2_interim_goes_to_preview_line_only(self) -> None:
        """[P2] 확정 전 글자는 미리보기 줄(#voice-interim)에만 쓰고, 듣기가 끝나면 비우고 숨긴다."""
        self.assertRegex(self.block, r"recognition\.interimResults\s*=\s*true")
        self.assertNotRegex(self.block, r"recognition\.interimResults\s*=\s*false")
        self.assertRegex(
            INDEX_HTML,
            r'<textarea[^>]*id="sentence-input"[\s\S]*?</textarea>\s*<p id="voice-interim"[^>]*hidden',
        )
        result = handler(self.block, "result")
        self.assertIn("showVoiceInterim(interim)", result)
        # 미리보기는 모든 결과에서 다시 만든다 — 바뀐 결과(resultIndex)부터만 훑으면 앞의 확정 전 글자가 빠진다
        self.assertRegex(result, r"for \(let i = 0; i < event\.results\.length")
        self.assertNotRegex(result, r"let i = event\.resultIndex")
        # 확정 전 글자를 입력창에 쓰는 줄이 없다 — 입력창 쓰기는 appendVoiceText 한 곳뿐이다
        self.assertNotRegex(result, r"sentenceInput\.value\s*=")
        self.assertIn("hideVoiceInterim()", handler(self.block, "end"))

    def test_p3_end_restores_button_and_keeps_text(self) -> None:
        """[P3] 어떻게 끝나든 버튼이 [마이크로 말하기] 로 돌아오고 미리보기 줄이 숨으며, 확정 글자는 지우지 않는다."""
        end = handler(self.block, "end")
        self.assertIn('voiceBtn.textContent = "마이크로 말하기"', end)
        self.assertIn('voiceBtn.classList.remove("recording")', end)
        self.assertIn("isRecording = false", end)
        self.assertNotRegex(end, r"sentenceInput\.value\s*=")
        # 브라우저가 끝내도 스스로 다시 켜지 않는다(설계 ④)
        self.assertNotIn("recognition.start()", end)
        # 권한 거부는 따로 안내한다
        error = handler(self.block, "error")
        self.assertIn('"not-allowed"', error)
        self.assertIn("마이크 권한을 허용해 주세요", error)
        # 확정 글자가 붙으면 입력 모드는 음성이다
        self.assertIn('setInputMode("voice")', handler(self.block, "result"))

    def test_p4_stops_at_1000_chars_and_never_overflows(self) -> None:
        """[P4] 1,000자에 닿으면 듣기를 멈추고 안내하며, 넘는 부분은 잘라 붙이지 않는다."""
        self.assertRegex(APP_JS, r"const VOICE_MAX_CHARS\s*=\s*1000;")
        start = APP_JS.index("function appendVoiceText(")
        append = APP_JS[start:APP_JS.index("\n  }\n", start)]
        self.assertIn("VOICE_MAX_CHARS - current.length", append)
        self.assertIn("text.slice(0, room)", append)
        result = handler(self.block, "result")
        self.assertRegex(result, r"VOICE_MAX_CHARS[\s\S]*recognition\.stop\(\)")
        self.assertIn("최대 1,000자", result)
        # 옛 꼴 — 길이를 보지 않고 그대로 이어 붙이던 줄
        self.assertNotRegex(APP_JS, r"sentenceInput\.value\.trim\(\)\} \$\{transcript\}")
        # 이미 1,000자면 듣기를 시작하지 않는다
        self.assertRegex(self.block, r"sentenceInput\.value\.length >= VOICE_MAX_CHARS\)\s*\{\s*showStatus")


if __name__ == "__main__":
    unittest.main()
