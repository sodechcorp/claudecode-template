"""
verify_cat4_completeness.py — cat4 設計書の生成完了率を突合する。

_metadata_cache.json の対象種別件数と docs/design/{kind}/ の生成済み件数を比較し、
未生成コンポーネントがあれば exit 1 で報告する。

Usage:
  python verify_cat4_completeness.py --project-dir <PATH> --kind <flow|apex|lwc>

Exit code:
  0 — missing == 0（全件生成済み）
  1 — missing > 0（未生成あり。stderr に一覧）
  2 — 入力ファイル・_metadata_cache.json の対象キーが無い
"""
import argparse, json, sys
from pathlib import Path

import yaml

from feature_id_ledger import _APEX_GROUP, _FLOW_GROUP
from scan_features import classify_apex, design_doc_ids, is_trivial_vf_page


# kind ごとのメタデータキー・API 名フィールド・ソースのパス（force-app/main/default/ 配下）・台帳の type のマッピング
_KIND_META = {
    "flow": [
        ("flow_definitions", "ApiName", "flows/{}.flow-meta.xml", _FLOW_GROUP),
    ],
    "apex": [
        ("apex_classes", "Name", "classes/{}.cls", _APEX_GROUP),
        ("apex_triggers", "Name", "triggers/{}.trigger", {"Trigger"}),
    ],
    "lwc": [
        ("lwc_bundles", "DeveloperName", "lwc/{}", {"LWC"}),
        ("apex_pages", "Name", "pages/{}.page-meta.xml", {"Visualforce"}),
        ("aura_bundles", "DeveloperName", "aura/{}", {"Aura"}),
    ],
}

# kind ごとの設計書出力ディレクトリ（docs/design/ 配下）
_KIND_DESIGN_DIRS = {
    "flow": ["flow"],
    "apex": ["apex", "batch", "integration"],
    "lwc": ["lwc", "vf", "aura"],
}


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
    missing_keys = [meta_key for meta_key, *_ in _KIND_META[kind] if meta_key not in cache]
    if missing_keys:
        print(
            f"[verify_cat4] ERROR: _metadata_cache.json に {', '.join(missing_keys)} が無い。"
            " Phase 1 のクエリを build_metadata_cache.py に通してキャッシュしてから再実行してください。",
            file=sys.stderr,
        )
        sys.exit(2)

    # 2. kind に対応するメタデータから (メタデータキー, API 名) → (台帳の type, ソースのパス) を収集
    src_root = proj / "force-app" / "main" / "default"
    expected_sources: dict[tuple[str, str], tuple[set[str], Path]] = {}
    for meta_key, name_field, src_pattern, types in _KIND_META[kind]:
        records = cache.get(meta_key, [])
        for rec in records:
            api_name = rec.get(name_field)
            if not api_name:
                continue
            src = src_root / src_pattern.format(api_name)
            # scan_features.py が機能一覧に入れないもの（空・雛形 VF、テスト・Batch を起動する Schedulable のクラス）は doc 必須対象外
            if meta_key == "apex_pages" and is_trivial_vf_page(src):
                continue
            if meta_key == "apex_classes" and classify_apex(src) is None:
                continue
            expected_sources[(meta_key, api_name)] = (types, src)

    # 3. feature_ids.yml を読み、(type, API 名) → (cmp_id, deprecated) のマップを作る
    fids_path = proj / "docs" / ".sf" / "feature_ids.yml"
    if not fids_path.exists():
        print(f"[verify_cat4] ERROR: {fids_path} not found", file=sys.stderr)
        sys.exit(2)

    fids_data = yaml.safe_load(fids_path.read_text(encoding="utf-8")) or {}
    fids: dict[tuple[str, str], tuple[str, bool]] = {}
    for feat in fids_data.get("features", []):
        api_name = feat.get("api_name")
        if api_name:
            fids[(feat.get("type"), api_name)] = (feat["id"], bool(feat.get("deprecated", False)))

    # 4. 期待 CMP ID 集合（deprecated=false のもの）を構築
    expected_cmps: set[str] = set()
    deprecated_count = 0
    not_in_fids: list[Path] = []

    for (_, api_name), (types, src) in expected_sources.items():
        entries = [fids[(t, api_name)] for t in types if (t, api_name) in fids]
        if not entries:
            not_in_fids.append(src)
            continue
        # 同じ type のグループに deprecated と有効が並ぶ（Flow から画面フローに変わった）ときは有効な方
        cmp_id, is_deprecated = min(entries, key=lambda e: (e[1], e[0]))
        if is_deprecated:
            deprecated_count += 1
        else:
            expected_cmps.add(cmp_id)

    # scan_features.py はソースを走査して台帳に入れるため、ソースが無いものは再実行では入らない
    no_source = [src for src in not_in_fids if not src.exists()]
    if len(not_in_fids) > len(no_source):
        print(
            f"[verify_cat4] WARNING: {len(not_in_fids) - len(no_source)} API 名が feature_ids.yml に未登録"
            " (scan_features.py を再実行してください)",
            file=sys.stderr,
        )
    if no_source:
        print(
            f"[verify_cat4] WARNING: {len(no_source)} API 名が force-app に無く feature_ids.yml に未登録"
            " (このフェーズでは取得しない。/sf-retrieve で取得してから scan_features.py を再実行してください)",
            file=sys.stderr,
        )

    # 5. docs/design/{kind}/ から生成済み CMP ID 集合を取得
    generated_cmps: set[str] = set()
    for dir_name in _KIND_DESIGN_DIRS[kind]:
        design_dir = proj / "docs" / "design" / dir_name
        if design_dir.exists():
            for md_file in design_dir.glob("*.md"):
                generated_cmps |= design_doc_ids(md_file)

    # 6. 差分を計算
    missing_cmps = expected_cmps - generated_cmps
    missing_count = len(missing_cmps)

    # 7. 未生成一覧を stderr に出力（最大 50 件）
    if missing_cmps:
        # CMP ID → API 名の逆引きマップ
        cmp_to_api = {cmp_id: api for (_, api), (cmp_id, _) in fids.items()}
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
