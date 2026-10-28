"""내 PC의 로컬 JSON 파일(data/vocab-items.json)에 단어장 항목을 저장·중복 방지·복습 갱신·삭제하는 저장소 모듈."""

from __future__ import annotations

from datetime import date
import json
import pathlib
import threading
from typing import Any
import uuid

from src.feedback_types import ValidationError
from src.vocab_types import (
    VocabCreateRequest,
    VocabItem,
    VocabReviewRequest,
    normalize_expression,
)

DEFAULT_VOCAB_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "data" / "vocab-items.json"
)


class VocabStore:
    """단어장 항목을 로컬 JSON 파일에 원자적으로 저장하고 중복 방지·복습 주기 갱신·삭제를 수행한다([V1]~[V3] 보장)."""

    def __init__(self, file_path: pathlib.Path | None = None) -> None:
        self.file_path = file_path or DEFAULT_VOCAB_PATH
        self._lock = threading.Lock()

    def list_items(self) -> list[VocabItem]:
        """저장된 전체 단어장 항목을 최신 등록순으로 반환한다."""
        with self._lock:
            return self._read_all_unlocked()

    def list_due_items(self, today: date | None = None) -> list[VocabItem]:
        """오늘 복습할 대상(nextReviewDate <= 오늘) 항목만 추려 반환한다."""
        with self._lock:
            items = self._read_all_unlocked()
            return [item for item in items if item.is_due(today=today)]

    def add_item(
        self,
        req: VocabCreateRequest,
        today: date | None = None,
    ) -> tuple[VocabItem, bool]:
        """단어장에 새 표현을 추가한다.

        이미 같은 영어 표현(대소문자·앞뒤 공백 무시)이 있으면 중복 생성하지 않고
        (기존 항목, True)를 반환하며, 신규 생성 시 (새 항목, False)를 반환한다([V1] 보장).
        """
        target_key = normalize_expression(req.expression)
        with self._lock:
            existing = self._read_all_unlocked()
            for item in existing:
                if normalize_expression(item.expression) == target_key:
                    return item, True

            new_item = VocabItem.create(req, today=today)
            updated = [new_item, *existing]
            self._write_all_unlocked(updated)
            return new_item, False

    def review_item(
        self,
        req: VocabReviewRequest,
        today: date | None = None,
    ) -> VocabItem | None:
        """지정한 ID의 단어장 항목에 복습 난이도 평가를 반영하고 파일에 즉시 저장한다([V2], [V3] 보장)."""
        target_id = req.id.strip()
        with self._lock:
            existing = self._read_all_unlocked()
            updated_list: list[VocabItem] = []
            reviewed_item: VocabItem | None = None

            for item in existing:
                if item.id == target_id and reviewed_item is None:
                    reviewed_item = item.apply_review(req.rating, today=today)
                    updated_list.append(reviewed_item)
                else:
                    updated_list.append(item)

            if reviewed_item is None:
                return None

            self._write_all_unlocked(updated_list)
            return reviewed_item

    def delete_item(self, item_id: str) -> bool:
        """지정한 ID의 단어장 항목을 삭제하고 파일에 반영한다([V3] 보장)."""
        cleaned_id = item_id.strip()
        if not cleaned_id:
            return False

        with self._lock:
            existing = self._read_all_unlocked()
            remaining = [item for item in existing if item.id != cleaned_id]
            if len(remaining) == len(existing):
                return False

            self._write_all_unlocked(remaining)
            return True

    def _read_all_unlocked(self) -> list[VocabItem]:
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

        items: list[VocabItem] = []
        seen_ids: set[str] = set()
        seen_exprs: set[str] = set()
        for raw in raw_list:
            try:
                item = VocabItem.from_dict(raw)
            except ValidationError:
                continue
            norm_expr = normalize_expression(item.expression)
            if item.id in seen_ids or norm_expr in seen_exprs:
                continue
            seen_ids.add(item.id)
            seen_exprs.add(norm_expr)
            items.append(item)
        return items

    def _write_all_unlocked(self, items: list[VocabItem]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload: list[dict[str, Any]] = [item.to_dict() for item in items]
        temp_path = self.file_path.with_name(
            f"{self.file_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_path.replace(self.file_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
