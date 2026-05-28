"""
機能ID台帳の読み書きモジュール。

docs/feature_ids.yml をプロジェクト内の唯一の機能ID台帳として管理する。
- 採番はこのモジュール経由のみ（他コマンドは参照のみ）
- API名 + type をキーに既存IDを再利用
- 削除された機能は deprecated=true にしてID欠番を保持（IDは再利用しない）

台帳フォーマット:
    # ⚠ このファイルはスクリプト自動管理。手編集不可
    next_id: 42
    features:
      - id: F-001
        type: Apex
        api_name: AccountHelper
        deprecated: false
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

import yaml


LEDGER_HEADER = (
    "# ⚠ このファイルはスクリプト（scan_features.py）が自動管理します。\n"
    "# 手編集は原則禁止。API名リネームなど特殊ケースのみ手編集可。\n"
    "# 機能ID は一度割り当てたら再利用しません（削除機能は deprecated=true で欠番保持）。\n"
)


def _make_key(ftype: str, api_name: str) -> str:
    return f"{ftype}::{api_name}"


def load_ledger(ledger_path: Path) -> dict:
    """台帳を読み込む。存在しなければ空の台帳を返す。"""
    if not ledger_path.exists():
        return {"next_id": 1, "features": []}
    try:
        with ledger_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError(f"台帳の読込に失敗: {ledger_path}: {e}")

    data.setdefault("next_id", 1)
    data.setdefault("features", [])
    return data


def save_ledger(ledger_path: Path, ledger: dict) -> None:
    """台帳を保存する（ヘッダーコメント付き）。"""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(
        ledger, allow_unicode=True, sort_keys=False, default_flow_style=False,
    )
    ledger_path.write_text(LEDGER_HEADER + body, encoding="utf-8")


# classes/ 配下の .cls ファイルから生成される型グループ。
# 同一 api_name は同一コンポーネントのリクラシフィケーションとみなし、ID を再利用する。
_APEX_GROUP = {"Apex", "Batch", "Integration"}

# flows/ 配下から生成される型グループ。
# 画面の有無による Flow ↔ 画面フロー の型変更は同一コンポーネントとみなし ID を再利用する。
_FLOW_GROUP = {"Flow", "画面フロー"}


def _index_by_key(ledger: dict) -> dict[str, dict]:
    return {_make_key(f["type"], f["api_name"]): f for f in ledger["features"]}


def resolve_id(ledger: dict, ftype: str, api_name: str) -> str:
    """type + api_name に対応するIDを取得。無ければ新規採番。
    採番した場合は ledger を更新する（呼び出し側で save_ledger 必須）。

    Apex グループ（Apex / Batch / Integration）内での型変更は同一コンポーネントの
    リクラシフィケーションとみなし、既存エントリの type を更新して同一IDを返す。
    """
    idx = _index_by_key(ledger)
    key = _make_key(ftype, api_name)
    if key in idx:
        entry = idx[key]
        # 復活したケース（以前 deprecated だったが再追加）
        if entry.get("deprecated"):
            entry["deprecated"] = False
        return entry["id"]

    # Apex グループ内でのリクラシフィケーション検出
    # 例: Apex → Integration へ型変更された場合、別IDを振らずに既存エントリを更新する
    if ftype in _APEX_GROUP:
        for entry in ledger["features"]:
            if (entry["api_name"] == api_name
                    and entry["type"] in _APEX_GROUP
                    and entry["type"] != ftype
                    and not entry.get("deprecated")):
                entry["type"] = ftype
                return entry["id"]

    # Flow グループ内でのリクラシフィケーション検出
    # 例: Flow → 画面フロー（画面追加）/ 画面フロー → Flow（画面削除）
    if ftype in _FLOW_GROUP:
        for entry in ledger["features"]:
            if (entry["api_name"] == api_name
                    and entry["type"] in _FLOW_GROUP
                    and entry["type"] != ftype
                    and not entry.get("deprecated")):
                entry["type"] = ftype
                return entry["id"]

    new_id = f"F-{ledger['next_id']:03d}"
    ledger["features"].append({
        "id":         new_id,
        "type":       ftype,
        "api_name":   api_name,
        "deprecated": False,
    })
    ledger["next_id"] += 1
    return new_id


def mark_deprecated(ledger: dict, active_keys: set[str]) -> list[dict]:
    """今回のスキャンで見つからなかった機能を deprecated=true にする。
    戻り値: 今回 deprecated に変わった機能のリスト（変更通知用）。
    """
    newly_deprecated = []
    for entry in ledger["features"]:
        key = _make_key(entry["type"], entry["api_name"])
        if key not in active_keys and not entry.get("deprecated"):
            entry["deprecated"] = True
            newly_deprecated.append(entry.copy())
    return newly_deprecated


def lookup_id(ledger: dict, ftype: str, api_name: str) -> Optional[str]:
    """参照のみ（採番しない）。見つからなければ None。"""
    idx = _index_by_key(ledger)
    key = _make_key(ftype, api_name)
    entry = idx.get(key)
    return entry["id"] if entry else None
