"""조각 7(speaking-practice) 정적 시험 — 설계 ② 보장 [P1] ~ [P4](PR 1) · [P5] ~ [P7](PR 2).

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


def function_body(name: str) -> str:
    """`function <name>(` 부터 다음 최상위 함수 앞까지."""
    start = APP_JS.index(f"function {name}(")
    end = APP_JS.index("\n  function ", start + 1)
    return APP_JS[start:end]


class TestSlice7SpeakingPracticePR2(unittest.TestCase):
    """설계 ② 보장하는 것 [P5] ~ [P7]."""

    def test_p5_listen_buttons_on_feedback_note_only(self) -> None:
        """[P5] 교정 문장 · 추천 표현 · 핵심 표현 예문마다 [듣기]가 있고 en-US 로 읽으며, 새로 누르면 앞 소리를 멈춘다."""
        render = function_body("renderRecord")
        self.assertIn("createListenButton(fb.corrected)", render)
        self.assertIn("createListenButton(item.expression)", render)
        self.assertIn("createListenButton(item.example)", render)
        # 원문(내가 쓴 글)과 핵심 표현 낱말만은 읽지 않는다(설계 ④)
        self.assertNotIn("createListenButton(record.text)", render)
        self.assertEqual(render.count("createListenButton("), 3)
        # 첨삭 노트에만 단다 — 단어장 복습 · 미션 화면에는 없다(요구사항 하지 않을 일 4)
        self.assertEqual(APP_JS.count("createListenButton("), 4)  # 정의 1 + renderRecord 3
        speak = function_body("speakEnglish")
        self.assertRegex(speak, r'utterance\.lang\s*=\s*"en-US"')
        self.assertRegex(speak, r"stopSpeaking\(\);[\s\S]*speechSynthesis\.speak\(utterance\)")
        self.assertIn("speechSynthesis.cancel()", function_body("stopSpeaking"))
        # 속도 조절 · 목소리 고르기는 넣지 않는다(하지 않을 일 5)
        self.assertNotRegex(APP_JS, r"utterance\.(rate|pitch)\s*=")
        # 이전 기록을 열 때도 같은 renderRecord 를 쓴다
        self.assertRegex(APP_JS, r'li\.addEventListener\("click", \(\) => \{[\s\S]{0,80}renderRecord\(item\)')

    def test_p6_mic_start_stops_speaking_first(self) -> None:
        """[P6] 마이크를 켜면 읽던 소리를 먼저 멈추고, 듣는 중에 [듣기]를 누르면 말하기를 먼저 끝낸다(설계 끝 덧붙임)."""
        block = speech_block()
        self.assertRegex(block, r"stopSpeaking\(\);\s*try \{\s*recognition\.start\(\)")
        self.assertNotRegex(block, r"recognition\.start\(\);[\s\S]{0,40}stopSpeaking\(\)")
        speak = function_body("speakEnglish")
        # 읽기 전에 듣기를 끝낸다 — abort() 는 말한 글을 버리므로 쓰지 않는다
        self.assertRegex(speak, r"if \(isRecording && recognition\) recognition\.stop\(\);[\s\S]*speechSynthesis\.speak\(")
        self.assertNotIn("recognition.abort()", speak)

    def test_p7_no_listen_button_without_speech_synthesis(self) -> None:
        """[P7] 음성 합성이 없거나 읽을 글이 비면 [듣기]를 그리지 않고, 나머지(단어장 담기)는 그대로 그린다."""
        self.assertRegex(
            APP_JS,
            r'const canSpeak =\s*"speechSynthesis" in window && typeof window\.SpeechSynthesisUtterance === "function";',
        )
        listen = function_body("createListenButton")
        self.assertRegex(listen, r"if \(!canSpeak \|\| !trimmed\) return null;")
        render = function_body("renderRecord")
        # [듣기]는 있을 때만 붙인다 — null 을 그대로 appendChild 하면 첨삭 노트 그리기가 멈춘다
        self.assertEqual(render.count("appendIfPresent("), 3)
        self.assertNotRegex(render, r"\.appendChild\(createListenButton\(")
        self.assertIn("createSaveToVocabButton(", render)


if __name__ == "__main__":
    unittest.main()
