"""
feature_groups.yml と feature_ids.yml の整合チェックスクリプト。

sf-analyst-cat5 の Phase 3（feature_groups.yml 生成）直後に呼び出し、
登録済み CMP が機能ID台帳と矛盾していないかを検出する。

検出する不整合:
  ERROR   : feature_groups.yml にあるが feature_ids.yml に存在しない CMP（幻CMP）
  WARNING : feature_groups.yml にあるが feature_ids.yml で deprecated=True の CMP

検出しない（正常扱い）:
  - 孤児 CMP（feature_ids.yml にあるが feature_groups.yml に無い）
    → 関連性のない単独コンポーネントは詳細設計で扱わなくてよい
  - 重複 CMP（複数 FG に登録されている）
    → 1 CMP が複数グループで使われるのは正常運用

  WARNING（追加）:
  - generated_at が YYYY-MM-DD 形式でない（長文・改行混入等）
    → cat5 Phase 3 ガードで実行日に上書きすること

Usage:
    python check_feature_groups.py \
        --groups docs/.sf/feature_groups.yml \
        --ids docs/.sf/feature_ids.yml

終了コード:
    0: エラーなし（警告のみは 0）
    1: エラーあり（FGから該当CMPを削除するか、feature_ids.yml 側を更新すること）
    2: 入力ファイルエラー
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml が必要です。`pip install pyyaml` を実行してください。",
          file=sys.stderr)
    sys.exit(2)


def load_yaml(path: Path) -> dict:
    if not path.exists():
        print(f"ERROR: ファイルが見つかりません: {path}", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


_GENERATED_AT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check(groups_path: Path, ids_path: Path) -> tuple[list[str], list[str]]:
    groups_data = load_yaml(groups_path)
    ids_data = load_yaml(ids_path)

    # feature_ids.yml: {id: {deprecated: bool, ...}} 形式のルックアップを作る
    id_to_feature: dict[str, dict] = {}
    for feat in ids_data.get("features", []):
        fid = feat.get("id")
        if fid:
            id_to_feature[fid] = feat

    errors: list[str] = []
    warnings: list[str] = []

    # generated_at 書式チェック
    generated_at = groups_data.get("generated_at")
    if generated_at is not None and not _GENERATED_AT_PATTERN.match(str(generated_at).strip()):
        snippet = str(generated_at).replace("\n", " ")[:60]
        warnings.append(
            f"[meta] generated_at が YYYY-MM-DD 形式ではありません: \"{snippet}\" "
            f"— 修正経緯は docs/logs/changelog.md へ移動し、generated_at は実行日のみに修正してください"
        )

    for g in groups_data.get("groups", []):
        gid = g.get("group_id", "?")
        gname = g.get("name_ja", "?")
        for fid in g.get("feature_ids", []):
            feat = id_to_feature.get(fid)
            if feat is None:
                errors.append(
                    f"[{gid}:{gname}] {fid} が feature_ids.yml に存在しません（幻CMP）"
                )
            elif feat.get("deprecated", False):
                warnings.append(
                    f"[{gid}:{gname}] {fid}"
                    f" ({feat.get('api_name', '?')})"
                    f" は feature_ids.yml で deprecated=true です"
                )

    return errors, warnings


def main() -> int:
    p = argparse.ArgumentParser(description="feature_groups.yml の整合チェック")
    p.add_argument("--groups", required=True,
                   help="feature_groups.yml のパス")
    p.add_argument("--ids", required=True,
                   help="feature_ids.yml のパス")
    args = p.parse_args()

    errors, warnings = check(Path(args.groups), Path(args.ids))

    if not errors and not warnings:
        print("OK: feature_groups.yml と feature_ids.yml の整合性に問題ありません")
        return 0

    if errors:
        print(f"ERROR: {len(errors)} 件", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
    if warnings:
        print(f"WARNING: {len(warnings)} 件", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
