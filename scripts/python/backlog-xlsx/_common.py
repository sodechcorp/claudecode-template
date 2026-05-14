# -*- coding: utf-8 -*-
"""backlog-xlsx 共通ユーティリティ"""
from pathlib import Path

try:
    from openpyxl.styles import PatternFill
    _OPENPYXL_AVAILABLE = True
except ImportError:
    _OPENPYXL_AVAILABLE = False

# リリース・ロールバックシート「リリース実施記録」の開始行（xlsx テンプレート固定値）
# テンプレートを更新した場合はここを変更するだけで全スクリプトに反映される
RELEASE_HISTORY_START_ROW = 38

_STRIPE_A_RGB = "FFFFFF"  # 偶数インデックス行（0, 2, 4, ...）
_STRIPE_B_RGB = "F2F7FB"  # 奇数インデックス行（1, 3, 5, ...）（薄青）


def _stripe_fill(i):
    """0-indexed の行番号 i に対応する縞模様 PatternFill を毎回 fresh に生成して返す。

    openpyxl の style index aliasing バグ（singleton を使うと白代入が青セルで
    silent no-op になる）を回避するため、呼び出し毎に新規インスタンスを生成する。
    """
    rgb = _STRIPE_A_RGB if i % 2 == 0 else _STRIPE_B_RGB
    return PatternFill("solid", fgColor=rgb)


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
