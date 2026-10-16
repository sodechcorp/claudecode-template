# -*- coding: utf-8 -*-
"""改版履歴管理（小数点バージョン対応）"""

from datetime import date


# ------------------------------------------------------------------ #
# バージョン文字列ユーティリティ
# ------------------------------------------------------------------ #

def increment_version(current: str, mode: str) -> str:
    """バージョン文字列をインクリメントする。
    mode='minor': '1.0' → '1.1', '1.1' → '1.2'
    mode='major': '1.0' → '2.0', '1.2' → '2.0'
    """
    try:
        major, minor = map(int, current.split("."))
    except ValueError:
        raise ValueError(f"バージョン文字列の形式が不正です: {current!r}（期待: 'MAJOR.MINOR' 例: '1.0'）")
    if mode == "major":
        return f"{major + 1}.0"
    return f"{major}.{minor + 1}"


# ------------------------------------------------------------------ #
# VersionManager
# ------------------------------------------------------------------ #

class VersionManager:

    def __init__(self, author: str):
        self._author = author

    # ------------------------------------------------------------------ #
    # 差分計算
    # ------------------------------------------------------------------ #

    def compare(self, old_objects: dict | None, new_metadata_list: list) -> dict:
        """old_objects と新メタデータを比較し差分を返す。
        old_objects: {api_name: metadata_dict} 形式（_meta の objects フィールド）
        戻り値: {api_name: {"label", "fields": {added/removed/modified}, ...}}
        """
        if old_objects is None:
            return {}

        diffs = {}
        for meta in new_metadata_list:
            api_name = meta["object_api_name"]
            label    = meta.get("object_info", {}).get("label", api_name)

            if api_name not in old_objects:
                diffs[api_name] = {
                    "label": label, "new_object": True,
                    "fields": {"added": [f["api_name"] for f in meta.get("fields", [])],
                               "removed": [], "modified": []},
                }
                continue

            old_meta = old_objects[api_name]
            obj_diff = {"label": label}

            # フィールド比較
            old_f = {f["api_name"]: f for f in old_meta.get("fields", [])}
            new_f = {f["api_name"]: f for f in meta.get("fields", [])}
            added    = [k for k in new_f if k not in old_f]
            removed  = [k for k in old_f if k not in new_f]
            modified = [k for k in new_f
                        if k in old_f and _comparable(old_f[k]) != _comparable(new_f[k])]
            if added or removed or modified:
                obj_diff["fields"] = {
                    "added":    added,
                    "removed":  removed,
                    "modified": modified,
                }

            # その他セクションは内容の変化を記録
            for sec in _SECTION_NAMES:
                if old_meta.get(sec) != meta.get(sec):
                    obj_diff[sec] = True

            if len(obj_diff) > 1:   # label 以外に差分あり
                diffs[api_name] = obj_diff

        # 今回の一覧から外れたオブジェクト
        new_names = {m["object_api_name"] for m in new_metadata_list}
        for api_name, old_meta in old_objects.items():
            if api_name not in new_names:
                diffs[api_name] = {
                    "label": old_meta.get("object_info", {}).get("label", api_name),
                    "removed_object": True,
                }

        return diffs

    # ------------------------------------------------------------------ #
    # 履歴エントリ構築
    # ------------------------------------------------------------------ #

    def build_entries(self, version: str, diffs: dict,
                      start_no: int = 1,
                      is_major: bool = False) -> list[dict]:
        today = str(date.today())

        if version == "1.0":
            return [{
                "no": start_no, "version": version, "date": today,
                "sheet": "全シート", "content": "新規作成",
                "author": self._author,
            }]

        # メジャー更新：1行で「メジャーバージョンアップ」を記録
        if is_major:
            return [{
                "no": start_no, "version": version, "date": today,
                "sheet": "全シート", "content": "メジャーバージョンアップ（注記リセット）",
                "author": self._author,
            }]

        if not diffs:
            return [{
                "no": start_no, "version": version, "date": today,
                "sheet": "—", "content": "変更なし",
                "author": self._author,
            }]

        # 変更箇所・内容を1行に集約
        sheets   = [diff["label"] for diff in diffs.values()]
        contents = [_summarize(diff) for diff in diffs.values()]
        return [{
            "no":      start_no,
            "version": version,
            "date":    today,
            "sheet":   "・".join(sheets),
            "content": "・".join(contents),
            "author":  self._author,
        }]


# ------------------------------------------------------------------ #
# ヘルパー
# ------------------------------------------------------------------ #

# 項目以外で定義書に書くセクション（値は改版履歴に出す名前）
_SECTION_NAMES = {
    "object_info":      "オブジェクト基本情報",
    "record_types":     "レコードタイプ",
    "page_layouts":     "ページレイアウト",
    "lightning_pages":  "Lightning ページ",
    "compact_layouts":  "コンパクトレイアウト",
    "search_layouts":   "検索レイアウト",
    "field_sets":       "項目セット",
    "validation_rules": "入力規則",
    "lookup_filters":   "参照条件",
}


def _comparable(field: dict) -> tuple:
    """差分検出に使うフィールド値を tuple 化"""
    keys = ("label", "data_type", "length", "scale", "required", "unique",
            "external_id", "formula", "default_value", "picklist_values",
            "reference_to", "help_text", "description")
    return tuple(str(field.get(k)) for k in keys)


def _summarize(diff: dict) -> str:
    if diff.get("new_object"):
        return "新規オブジェクト追加"
    if diff.get("removed_object"):
        return "オブジェクト削除"
    parts = []
    fd = diff.get("fields", {})
    if fd.get("added"):
        parts.append(f"項目追加 {len(fd['added'])}件")
    if fd.get("removed"):
        parts.append(f"項目削除 {len(fd['removed'])}件")
    if fd.get("modified"):
        parts.append(f"項目変更 {len(fd['modified'])}件")
    parts += [f"{name}変更" for sec, name in _SECTION_NAMES.items() if diff.get(sec)]
    return "、".join(parts) if parts else "変更あり"
