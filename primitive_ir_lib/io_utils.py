"""io_utils.py — Lưu/đọc PrimitiveIRDocument (đã to_dict()) ra file JSON."""

from __future__ import annotations

import json

from .models import PrimitiveIRDocument


def save_document(doc: PrimitiveIRDocument, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc.to_dict(), f, indent=2, ensure_ascii=False)


def load_document_dict(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
