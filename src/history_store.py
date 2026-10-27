"""첨삭 결과를 내 PC의 로컬 JSON 파일(data/feedback-history.json)에 자동 저장하고 불러오는 모듈."""

from __future__ import annotations

import json
import pathlib
import threading
from typing import Any

from src.feedback_types import FeedbackRecord, ValidationError

DEFAULT_HISTORY_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "data" / "feedback-history.json"
)


class HistoryStore:
    """첨삭 학습 기록을 최신순으로 로컬 JSON 파일에 저장하고 조회한다([G3] 보장)."""

    def __init__(self, file_path: pathlib.Path | None = None) -> None:
        self.file_path = file_path or DEFAULT_HISTORY_PATH
        self._lock = threading.Lock()

    def list_records(self) -> list[FeedbackRecord]:
        """저장된 첨삭 기록을 최신순(가장 최근 기록이 맨 앞)으로 반환한다."""
        with self._lock:
            return self._read_all_unlocked()

    def save_record(self, record: FeedbackRecord) -> FeedbackRecord:
        """새 첨삭 기록을 맨 앞(최신순)에 추가하고 파일에 즉시 저장한다."""
        with self._lock:
            existing = self._read_all_unlocked()
            updated = [record, *existing]
            self._write_all_unlocked(updated)
            return record

    def _read_all_unlocked(self) -> list[FeedbackRecord]:
        if not self.file_path.is_file():
            return []
        try:
            raw_text = self.file_path.read_text(encoding="utf-8")
            if not raw_text.strip():
                return []
            raw_list = json.loads(raw_text)
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(raw_list, list):
            return []

        records: list[FeedbackRecord] = []
        for item in raw_list:
            try:
                records.append(FeedbackRecord.from_dict(item))
            except ValidationError:
                continue
        return records

    def _write_all_unlocked(self, records: list[FeedbackRecord]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload: list[dict[str, Any]] = [rec.to_dict() for rec in records]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.file_path)
