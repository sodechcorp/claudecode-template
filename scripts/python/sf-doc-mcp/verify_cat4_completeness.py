"""
verify_cat4_completeness.py — cat4 設計書の生成完了率を突合する。

_metadata_cache.json の対象種別件数と docs/design/{kind}/ の生成済み件数を比較し、
未生成コンポーネントがあれば exit 1 で報告する。

Usage:
  python verify_cat4_completeness.py --project-dir <PATH> --kind <flow|apex|lwc>

Exit code:
  0 — missing == 0（全件生成済み）
  1 — missing > 0（未生成あり。stderr に一覧）
  2 — 入力ファイルが見つからない
"""
import argparse, json, re, sys
from pathlib import Path

import yaml


# kind ごとのメタデータキーと API 名フィールドのマッピング
_KIND_META = {
    "flow": [
        ("flow_definitions", "ApiName"),
    ],
    "apex": [
        ("apex_classes", "Name"),
        ("apex_triggers", "Name"),
    ],
    "lwc": [
        ("lwc_bundles", "DeveloperName"),
        ("apex_pages", "Name"),
        ("aura_bundles", "DeveloperName"),
    ],
}

# kind ごとの設計書出力ディレクトリ（docs/design/ 配下）
_KIND_DESIGN_DIRS = {
    "flow": ["flow"],
    "apex": ["apex", "batch", "integration"],
    "lwc": ["lwc", "vf", "aura"],
}

_CMP_PATTERN = re.compile(r"【([A-Z]+-\d+)】")


def main():
    parser = argparse.ArgumentParser(
        description="cat4 設計書の生成完了率を突合する"
    )
    parser.add_argument("--project-dir", required=True, help="プロジェクトルートパス")
    parser.add_argument(
        "--kind", required=True, choices=["flow", "apex", "lwc"],
        help="対象種別"
    )
    args = parser.parse_args()

    proj = Path(args.project_dir)
    kind = args.kind

    # 1. _metadata_cache.json を読む
    cache_path = proj / "docs" / ".sf" / "_metadata_cache.json"
    if not cache_path.exists():
        print(f"[verify_cat4] ERROR: {cache_path} not found", file=sys.stderr)
        sys.exit(2)

    cache = json.loads(cache_path.read_text(encoding="utf-8"))

    # 2. kind に対応するメタデータから API 名一覧を収集
    expected_api_names: set[str] = set()
    for meta_key, name_field in _KIND_META[kind]:
        records = cache.get(meta_key, [])
        for rec in records:
            api_name = rec.get(name_field)
            if api_name:
                expected_api_names.add(api_name)

    if not expected_api_names:
        print(
            f"[verify_cat4] WARNING: _metadata_cache.json に kind={kind} の対象キーが見つかりません。"
            " scan_features.py / build_metadata_cache.py を先に実行してください。",
            file=sys.stderr,
        )

    # 3. feature_ids.yml を読み、API 名 → (cmp_id, deprecated) のマップを作る
    fids_path = proj / "docs" / ".sf" / "feature_ids.yml"
    if not fids_path.exists():
        print(f"[verify_cat4] ERROR: {fids_path} not found", file=sys.stderr)
        sys.exit(2)

    fids_data = yaml.safe_load(fids_path.read_text(encoding="utf-8")) or {}
    api_to_cmp: dict[str, tuple[str, bool]] = {}
    for feat in fids_data.get("features", []):
        api_name = feat.get("api_name")
        if api_name:
            api_to_cmp[api_name] = (feat["id"], bool(feat.get("deprecated", False)))

    # 4. 期待 CMP ID 集合（deprecated=false のもの）を構築
    expected_cmps: set[str] = set()
    deprecated_count = 0
    not_in_fids: set[str] = set()

    for api_name in expected_api_names:
        if api_name not in api_to_cmp:
            not_in_fids.add(api_name)
            continue
        cmp_id, is_deprecated = api_to_cmp[api_name]
        if is_deprecated:
            deprecated_count += 1
        else:
            expected_cmps.add(cmp_id)

    if not_in_fids:
        print(
            f"[verify_cat4] WARNING: {len(not_in_fids)} API 名が feature_ids.yml に未登録"
            " (scan_features.py を再実行してください)",
            file=sys.stderr,
        )

    # 5. docs/design/{kind}/ から生成済み CMP ID 集合を取得
    generated_cmps: set[str] = set()
    for dir_name in _KIND_DESIGN_DIRS[kind]:
        design_dir = proj / "docs" / "design" / dir_name
        if design_dir.exists():
            for md_file in design_dir.glob("*.md"):
                m = _CMP_PATTERN.search(md_file.name)
                if m:
                    generated_cmps.add(m.group(1))

    # 6. 差分を計算
    missing_cmps = expected_cmps - generated_cmps
    missing_count = len(missing_cmps)

    # 7. 未生成一覧を stderr に出力（最大 50 件）
    if missing_cmps:
        # CMP ID → API 名の逆引きマップ
        cmp_to_api = {cmp_id: api for api, (cmp_id, _) in api_to_cmp.items()}
        print(f"[verify_cat4] MISSING {missing_count} 件の設計書が未生成:", file=sys.stderr)
        for cmp_id in sorted(missing_cmps, key=lambda x: int(x.split("-")[1]))[:50]:
            api_name = cmp_to_api.get(cmp_id, "?")
            print(f"  {cmp_id} ({api_name})", file=sys.stderr)
        if missing_count > 50:
            print(f"  ... 他 {missing_count - 50} 件", file=sys.stderr)

    # 8. stdout に集計行（1 行のみ）
    print(
        f"[verify_cat4] kind={kind} expected={len(expected_cmps)}"
        f" generated={len(generated_cmps)} missing={missing_count}"
        f" deprecated={deprecated_count}"
    )

    sys.exit(1 if missing_count > 0 else 0)


if __name__ == "__main__":
    main()
