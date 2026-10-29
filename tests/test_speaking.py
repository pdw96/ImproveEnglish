"""조각 7(speaking-practice) 정적 시험 — 설계 ② 보장 [P1] ~ [P4](PR 1) · [P5] ~ [P7](PR 2) · 설계 끝 덧붙임 [P8] · [P9](PR 3) · [P10] · 임시 진단 빼기(PR 5) · 감사 회차 15 · 16 고침(PR 6).

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


def function_body_in(block: str, name: str) -> str:
    """`block` 안에 든 안쪽 함수 `function <name>(` 의 몸 — 4칸 들여쓴 닫는 괄호까지."""
    start = block.index(f"function {name}(")
    end = block.index("\n    }\n", start)
    return block[start:end]


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
        # 결과 번호마다 붙인 글을 기억해, 같은 결과는 다시 붙이지 않는다
        self.assertRegex(result, r"const prev = committedByIndex\.get\(i\);\s*if \(prev !== undefined && covers\(prev, key\)\) continue;")
        self.assertIn("commitIndex(i, transcript)", result)
        commit_index = function_body_in(self.block, "commitIndex")
        self.assertRegex(commit_index, r"if \(key === prev \|\| !covers\(key, prev\)\) return true;")
        self.assertIn("committedByIndex.set(i, key);", commit_index)
        self.assertIn("appendVoiceText(", function_body_in(self.block, "commitVoice"))
        # 옛 꼴 — 매번 첫 결과만 읽던 줄
        self.assertNotIn("event.results[0][0]", result)
        # 듣기가 (다시) 시작될 때마다 번호 기억을 비운다(새 듣기는 번호가 0 부터다)
        self.assertRegex(handler(self.block, "start"), r"committedByIndex\s*=\s*new Map\(\)")

    def test_p2_interim_goes_to_preview_line_only(self) -> None:
        """[P2] 확정 전 글자는 미리보기 줄(#voice-interim)에만 쓰고, 듣기가 끝나면 비우고 숨긴다."""
        self.assertRegex(self.block, r"recognition\.interimResults\s*=\s*true")
        self.assertNotRegex(self.block, r"recognition\.interimResults\s*=\s*false")
        self.assertRegex(
            INDEX_HTML,
            r'<textarea[^>]*id="sentence-input"[\s\S]*?</textarea>\s*<p id="voice-interim"[^>]*hidden',
        )
        result = handler(self.block, "result")
        self.assertIn("showVoiceInterim(previewText(pendingResults))", result)
        # 미리보기는 모든 결과에서 다시 만든다 — 바뀐 결과(resultIndex)부터만 훑으면 앞의 확정 전 글자가 빠진다
        self.assertRegex(result, r"for \(let i = 0; i < event\.results\.length")
        self.assertNotRegex(result, r"let i = event\.resultIndex")
        # 확정 전 글자를 입력창에 쓰는 줄이 없다 — 입력창 쓰기는 appendVoiceText 한 곳뿐이다
        self.assertNotRegex(result, r"sentenceInput\.value\s*=")
        # 듣기를 마치면 미리보기 줄을 숨긴다(다시 켜는 동안은 「듣는 중…」 — P10)
        finish = self.block[self.block.index("finishListeningUi = () => {"):]
        self.assertIn("hideVoiceInterim()", finish[:finish.index("\n    };")])

    def test_p3_end_restores_button_and_keeps_text(self) -> None:
        """[P3] 듣기를 마치면(종료 버튼 · 오류 · 상한 · 말 없음) 버튼이 [마이크로 말하기] 로 돌아오고 미리보기 줄이 숨으며,
        확정 글자는 지우지 않는다. 브라우저가 스스로 끝낸 경우는 [P8] 대로 다시 켠다(설계 끝 덧붙임)."""
        end = handler(self.block, "end")
        finish = self.block[self.block.index("finishListeningUi = () => {"):self.block.index("\n    };", self.block.index("finishListeningUi = () => {"))]
        self.assertIn('voiceBtn.textContent = "마이크로 말하기"', finish)
        self.assertIn('voiceBtn.classList.remove("recording")', finish)
        self.assertIn("hideVoiceInterim()", finish)
        self.assertIn("finishListeningUi();", end)
        self.assertIn("isRecording = false", end)
        self.assertNotRegex(end, r"sentenceInput\.value\s*=")
        self.assertNotRegex(finish, r"sentenceInput\.value\s*=")
        # 권한 거부는 따로 안내한다
        error = handler(self.block, "error")
        self.assertIn('"not-allowed"', error)
        self.assertIn("마이크 권한을 허용해 주세요", error)
        # 확정 글자가 붙으면 입력 모드는 음성이다
        self.assertIn('setInputMode("voice")', function_body_in(self.block, "commitVoice"))

    def test_p4_stops_at_1000_chars_and_never_overflows(self) -> None:
        """[P4] 1,000자에 닿으면 듣기를 멈추고 안내하며, 넘는 부분은 잘라 붙이지 않는다."""
        self.assertRegex(APP_JS, r"const VOICE_MAX_CHARS\s*=\s*1000;")
        start = APP_JS.index("function appendVoiceText(")
        append = APP_JS[start:APP_JS.index("\n  }\n", start)]
        self.assertIn("VOICE_MAX_CHARS - current.length", append)
        self.assertIn("text.slice(0, room)", append)
        commit = function_body_in(self.block, "commitVoice")
        self.assertRegex(commit, r"VOICE_MAX_CHARS[\s\S]*stopListening\(\)")
        self.assertIn("최대 1,000자", commit)
        self.assertRegex(handler(self.block, "result"), r"if \(!commitIndex\(i, transcript\)\) return;")
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
        self.assertRegex(block, r"stopSpeaking\(\);\s*try \{\s*isStarting = true;\s*recognition\.start\(\)")
        self.assertNotRegex(block, r"recognition\.start\(\);[\s\S]{0,40}stopSpeaking\(\)")
        speak = function_body("speakEnglish")
        # 읽기 전에 듣기를 끝낸다 — 다시 켜기를 기다리는 중이어도 끝낸다
        self.assertRegex(speak, r"if \(keepListening \|\| isRecording \|\| isStarting\) stopListening\(\);[\s\S]*speechSynthesis\.speak\(")
        stop = function_body("stopListening")
        # abort() 는 말한 글을 버리므로 쓰지 않는다
        self.assertRegex(stop, r"keepListening = false;[\s\S]*recognition\.stop\(\)")
        self.assertNotIn("recognition.abort()", APP_JS)

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



class TestSlice7SpeakingPracticePR3(unittest.TestCase):
    """설계 끝 「실제 기기 확인(Android Chrome) 뒤 덧붙임」 [P8] · [P9]."""

    def setUp(self) -> None:
        self.block = speech_block()

    def test_p8_restarts_until_user_stops(self) -> None:
        """[P8] [말하기 종료]를 누르기 전에 브라우저가 끝내면 다시 켠다. 종료 · 치명 오류 · 상한 · 말 없음 3번이면 그만둔다."""
        end = handler(self.block, "end")
        self.assertRegex(end, r"if \(keepListening\) \{[\s\S]*setTimeout\([\s\S]*recognition\.start\(\)[\s\S]*return;")
        self.assertRegex(end, r"if \(!keepListening\) return;")
        # 말소리 없이 연달아 끝나면 그만둔다
        self.assertRegex(self.block, r"const VOICE_IDLE_RESTART_LIMIT = 3;")
        self.assertRegex(end, r"idleSessions >= VOICE_IDLE_RESTART_LIMIT\) \{\s*keepListening = false;")
        # 누르면 켜 두기, 다시 누르면 그만두기
        click = self.block[self.block.rindex('voiceBtn.addEventListener("click"'):]
        self.assertRegex(click, r"if \(keepListening \|\| isRecording \|\| isStarting\) \{\s*stopListening\(\);\s*return;")
        self.assertRegex(click, r"keepListening = true;[\s\S]*recognition\.start\(\)")
        stop = function_body("stopListening")
        self.assertIn("clearTimeout(restartTimer)", stop)
        # 켜는 중(start 이벤트 전)에 누른 멈춤도 지킨다(리뷰 1회차)
        self.assertIn("recognition && (isRecording || isStarting)) recognition.stop()", stop)
        self.assertRegex(handler(self.block, "start"), r"if \(!keepListening\) \{\s*recognition\.stop\(\);\s*return;")
        self.assertEqual(len(re.findall(r"isStarting = true;\s*recognition\.start\(\)", self.block)), 2)
        # 권한 · 마이크 · 네트워크 오류는 다시 켜지 않는다. 말 없음(no-speech)은 다시 켠다
        error = handler(self.block, "error")
        # 다시 켜는 오류는 no-speech · aborted 뿐이고, 그 밖은 안내하고 그만둔다(감사 회차 15 NC-3)
        self.assertIn('const RESTARTABLE_ERRORS = new Set(["no-speech", "aborted"]);', self.block)
        self.assertRegex(error, r"if \(RESTARTABLE_ERRORS\.has\(code\)\) return;\s*keepListening = false;\s*endNoticeShown = true;")
        self.assertNotIn("FATAL_ERRORS", self.block)
        # 말 없음으로 멈추면 앞서 글을 붙였어도 알린다(감사 회차 15 NC-4)
        self.assertRegex(end, r"idleSessions >= VOICE_IDLE_RESTART_LIMIT\) \{\s*keepListening = false;[\s\S]*?if \(!endNoticeShown\) \{")
        self.assertNotIn("!endNoticeShown && !addedThisListen", self.block)
        # 시작을 거절당하면 듣지 않은 상태로 되돌린다(감사 회차 15 담당 없음)
        fail = function_body_in(self.block, "failStart")
        self.assertRegex(fail, r"isStarting = false;\s*keepListening = false;\s*endNoticeShown = true;\s*showStatus\(\"마이크를 켜지 못했습니다[\s\S]*?finishListeningUi\(\);")
        # 버튼으로 켤 때도, 쉬는 동안 다시 켤 때도 같은 처리를 쓴다(감사 회차 16 NC-8)
        self.assertRegex(click[click.index("} catch (_) {"):], r"^\} catch \(_\) \{\s*failStart\(\);")
        self.assertRegex(end, r"recognition\.start\(\);\s*\} catch \(_\) \{\s*failStart\(\);")
        self.assertEqual(self.block.count("failStart();"), 2)

    def test_p9_android_zero_confidence_is_interim_and_not_lost(self) -> None:
        """[P9] isFinal 이어도 confidence 가 0 이면 확정 전으로 미리보기에 두고, 확정 없이 끝나면 그 글을 붙인다. 같은 문장은 한 번만."""
        result = handler(self.block, "result")
        self.assertRegex(result, r"const isFinal = result\.isFinal && !\(alt && alt\.confidence === 0\);")
        self.assertRegex(result, r"if \(isFinal\) \{")
        self.assertNotRegex(result, r"if \(result\.isFinal\) \{")
        end = handler(self.block, "end")
        self.assertRegex(end, r"if \(pendingResults\.length\) flushPending\(\"\"\);")
        # 확정 결과 앞에 남은 확정 전 결과는 순서대로 먼저 붙인다(리뷰 1회차)
        self.assertRegex(result, r"if \(!flushPending\(key\)\) return;\s*if \(!commitIndex\(i, transcript\)\) return;")
        flush = function_body_in(self.block, "flushPending")
        # 덮인 결과는 덮은 확정 결과로 기록해 다음 이벤트에 다시 붙지 않게 한다(리뷰 2회차)
        self.assertRegex(flush, r"if \(covering && covers\(covering, normalizeVoice\(p\.transcript\)\)\) \{[^}]*?committedByIndex\.set\(p\.i, covering\);\s*continue;")
        self.assertIn("commitIndex(p.i, p.transcript)", flush)
        # 미리보기는 누적 · 반복 결과를 하나로 합친다(리뷰 1회차)
        preview = function_body_in(self.block, "previewText")
        self.assertRegex(preview, r"if \(last && covers\(key, last\.key\)\) parts\[parts\.length - 1\]")
        self.assertRegex(preview, r"else if \(last && covers\(last\.key, key\)\) continue;")
        commit = function_body_in(self.block, "commitVoice")
        self.assertRegex(commit, r"if \(!key \|\| \(fullKey \|\| key\) === lastCommitted\) return true;")
        # 늘어난 부분만 붙일 때도 다음 누적 결과의 기준은 전체 글이다(리뷰 3회차)
        self.assertIn("lastCommitted = fullKey || key;", commit)
        self.assertRegex(function_body_in(self.block, "commitIndex"), r"return commitVoice\(dropWords\(transcript, prev\.split\(\" \"\)\.length\), key\);")
        # 누적 문장(앞 문장 + 새 말)은 새 말만 붙인다
        self.assertRegex(commit, r"if \(!fullKey && lastCommitted && key\.startsWith\(`\$\{lastCommitted\} `\)\) \{\s*piece = dropWords\(piece, lastCommitted\.split\(\" \"\)\.length\)")
        self.assertIn("appendVoiceText(piece)", commit)
        self.assertNotIn("appendVoiceText(transcript)", commit)


class TestSlice7ListeningIndicator(unittest.TestCase):
    """설계 끝 「진단 뒤 판정」 [P10] — 듣는 동안 확정 전 글자가 없으면 「듣는 중…」, 임시 진단은 뺐다."""

    def test_p10_listening_indicator_and_debug_removed(self) -> None:
        block = speech_block()
        show = function_body("showVoiceInterim")
        self.assertIn("const listening = keepListening || isRecording || isStarting;", show)
        self.assertIn('voiceInterim.textContent = text || (listening ? "듣는 중…" : "");', show)
        self.assertIn('voiceInterim.classList.toggle("is-listening", !text && listening);', show)
        self.assertIn('classList.remove("is-listening")', function_body("hideVoiceInterim"))
        # 켜질 때 보이고, 다시 켜는 동안 남는다
        self.assertIn('showVoiceInterim("");', handler(block, "start"))
        self.assertIn('showVoiceInterim("");', handler(block, "end"))
        self.assertNotIn("hideVoiceInterim()", handler(block, "end"))
        # 임시 진단(?voice-debug)은 원인을 확인한 뒤 뺐다
        styles = (REPO_ROOT / "public" / "styles.css").read_text(encoding="utf-8")
        for text in (APP_JS, styles):
            self.assertNotIn("voice-debug", text)
        self.assertNotIn("voiceDebug", APP_JS)

if __name__ == "__main__":
    unittest.main()
