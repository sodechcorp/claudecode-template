"""
ソースファイルのハッシュを計算し、既存 Excel の _meta に保存されたハッシュと比較する。

Usage:
  python source_hash_checker.py \
    --project-dir "path/to/project" \
    --source-paths "file1.cls,file2.cls" \
    --existing-excel "path/to/design.xlsx" \
    [--feature-group FG-001]   # 詳細設計: 機能グループの定義・UC の節・設計書に載るオブジェクトの項目と翻訳もハッシュに入れる

Output (stdout):
  hash:XXXXXXXX...    # 計算した SHA256 ハッシュ（ハッシュする中身が無ければ空）
  status:MATCH        # または CHANGED / NEW / NO_HASH

Exit code:
  0: ハッシュ一致 → LLM スキップ可能
  1: 不一致 / Excel なし / ハッシュ未記録 / ソースなし → LLM 実行が必要
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from meta_store import compute_source_hash, read_meta


def _uc_sections(text: str, uc_ids: list[str], group_id: str) -> str:
    """usecases.md の UC-xx の見出しの節（次の同じか上の階層の見出しまで）のうち、
    uc_ids にあるものと、本文にこの機能グループIDが出てくるもの（「対応FG: FG-004 / FG-005」等）を返す。"""
    lines = text.splitlines(keepends=True)
    heads = []
    for i, line in enumerate(lines):
        m = re.match(r"(#+)\s*(UC-\d+)", line)
        if m:
            heads.append((i, len(m.group(1)), m.group(2)))
    out = []
    for i, level, uc in heads:
        end = next((j for j in range(i + 1, len(lines))
                    if (h := re.match(r"(#+)\s*\S", lines[j])) and len(h.group(1)) <= level), len(lines))
        sec = "".join(lines[i:end])
        if uc in uc_ids or re.search(rf"(?<![\w-]){re.escape(group_id)}(?![\w-])", sec):
            out.append(sec)
    return "".join(out)


def _source_object_names(paths: list[str], base: Path) -> set[str]:
    """ソースの本文に名前が出てくるオブジェクト（objects/・objectTranslations/*-ja にあるもの。大文字小文字は区別しない）。"""
    names = {p.name for p in (base / "objects").iterdir() if p.is_dir()} if (base / "objects").is_dir() else set()
    if (base / "objectTranslations").is_dir():
        names |= {p.name[:-3] for p in (base / "objectTranslations").iterdir() if p.is_dir() and p.name.endswith("-ja")}
    by_lower = {n.lower(): n for n in names}
    found = set()
    for raw in paths:
        p = Path(raw)
        for f in (x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p] if p.is_file() else []:
            for tok in re.findall(r"\w+", f.read_text(encoding="utf-8", errors="ignore")):
                if tok.lower() in by_lower:
                    found.add(by_lower[tok.lower()])
    return found


def _group_inputs(project_dir: str, group_id: str, meta: dict | None, source_paths: list[str]) -> tuple[list[str], str]:
    """詳細設計の生成が読む、ソース以外の入力（設計書に載るオブジェクトの項目・翻訳のパスと、機能グループの定義・UC の節）。"""
    import yaml
    proj = Path(project_dir)
    raw = yaml.safe_load((proj / "docs" / ".sf" / "feature_groups.yml").read_text(encoding="utf-8"))
    groups = raw.get("groups", []) if isinstance(raw, dict) else (raw or [])
    group = next((g for g in groups if isinstance(g, dict) and g.get("group_id") == group_id), None)
    if group is None:
        return [], ""
    # オブジェクトは related_objects・ソースに名前が出るもの・前回の設計書に載ったもの（生成はコンポーネントのコードからも組み立てる）
    base = proj / "force-app" / "main" / "default"
    objs = [o for o in (group.get("related_objects") or []) if isinstance(o, str)] if isinstance(group.get("related_objects"), list) else []
    objs += sorted(_source_object_names(source_paths, base))
    data = (meta or {}).get("data") or {}
    objs += [o.get("api_name") for o in data.get("related_objects") or [] if isinstance(o, dict)]
    objs += [o.get("object") for o in data.get("object_access") or [] if isinstance(o, dict)]
    paths = []
    for obj in sorted({o for o in objs if isinstance(o, str) and re.fullmatch(r"\w+", o)}):
        paths += [base / "objects" / obj / f"{obj}.object-meta.xml", base / "objects" / obj / "fields",
                  base / "objectTranslations" / f"{obj}-ja"]
    text = json.dumps(group, ensure_ascii=False, sort_keys=True, default=str)
    uc_path = proj / "docs" / "flow" / "usecases.md"
    if uc_path.exists():
        # UC は uc_id だけでなく related_uc_ids・説明の中の「（UC-14）」も拾う
        text += _uc_sections(uc_path.read_text(encoding="utf-8"), set(re.findall(r"UC-\d+", text)), group_id)
    return [str(p) for p in paths], text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", default="",
                        help="相対パスの基準（feature_list.json の source_file は案件のルートからの相対パス）")
    parser.add_argument("--source-paths", required=True,
                        help="カンマ区切りのソースファイル／ディレクトリパス")
    parser.add_argument("--existing-excel", default="",
                        help="既存 Excel ファイルパス（省略時は新規扱い）")
    parser.add_argument("--feature-group", default="",
                        help="詳細設計の機能グループID。機能グループの定義・usecases.md の UC の節・"
                             "設計書に載るオブジェクト（related_objects・ソースに名前が出るもの・前回の設計書に載ったもの）"
                             "の項目と翻訳もハッシュに入れる（--project-dir が必要）")
    args = parser.parse_args()
    if args.feature_group and not args.project_dir:
        parser.error("--feature-group には --project-dir が必要")

    paths = [str(Path(args.project_dir) / p.strip()) for p in args.source_paths.split(",") if p.strip()]
    current_hash = compute_source_hash(paths)
    # 空の入力のハッシュ（ファイル0件・空フォルダ）を渡すと _meta に残り、次回も MATCH になって再生成がスキップされ続ける
    if current_hash == hashlib.sha256().hexdigest():
        print("hash:")
        print("status:NEW")
        sys.exit(1)
    excel_path = args.existing_excel.strip()
    meta = read_meta(excel_path) if excel_path and Path(excel_path).exists() else None
    if args.feature_group:
        extra_paths, extra_text = _group_inputs(args.project_dir, args.feature_group, meta, paths)
        h = hashlib.sha256(compute_source_hash(paths + extra_paths).encode("ascii"))
        h.update(extra_text.encode("utf-8"))
        current_hash = h.hexdigest()
    print(f"hash:{current_hash}")

    if not excel_path or not Path(excel_path).exists():
        print("status:NEW")
        sys.exit(1)

    stored_hash = meta.get("source_hash") if meta else None
    if stored_hash is None:
        print("status:NO_HASH")
        sys.exit(1)

    if stored_hash == current_hash:
        print("status:MATCH")
        sys.exit(0)
    else:
        print("status:CHANGED")
        sys.exit(1)


if __name__ == "__main__":
    main()
