# -*- coding: utf-8 -*-
"""backlog-xlsx 共通ユーティリティ"""
from pathlib import Path


def validate_folder(value: str) -> str:
    """--folder 引数のサニティチェック。プレースホルダー残留・相対パスを early-exit。"""
    if "{" in value or "}" in value:
        raise SystemExit(
            f"[FATAL] placeholder not resolved: {value!r}\n"
            "        /backlog Phase 1.5 に戻って {xlsx_folder} を実値で置換してください。"
        )
    p = Path(value)
    if not p.is_absolute():
        raise SystemExit(
            f"[FATAL] --folder must be absolute path: {value!r}"
        )
    return str(p)
