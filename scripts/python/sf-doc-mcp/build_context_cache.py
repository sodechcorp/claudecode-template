"""
build_context_cache.py — cat1 完了後に呼ぶ。
docs/ の主要ファイルから Glossary / UC / FR インデックスを抽出して
docs/.sf/_context_cache.json に保存する。cat2-5 はここを参照して前段 Read を省略する。
Usage: python build_context_cache.py {project_dir}
"""
import json, re, sys
from pathlib import Path


def _extract_glossary(text: str) -> dict:
    rows = {}
    for line in text.splitlines():
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 2 and not set(parts[0]).issubset({"-", " "}):
            rows[parts[0]] = parts[1]
    return rows


def main():
    project_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    docs = project_dir / "docs"
    cache_dir = docs / ".sf"
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache: dict = {}

    org_profile = docs / "overview" / "org-profile.md"
    if org_profile.exists():
        text = org_profile.read_text(encoding="utf-8")
        cache["glossary"] = _extract_glossary(text)

    usecases = docs / "flow" / "usecases.md"
    if usecases.exists():
        text = usecases.read_text(encoding="utf-8")
        cache["uc_ids"] = sorted(set(re.findall(r'\b(UC-\d{3})\b', text)))
        cache["related_objects"] = sorted(set(re.findall(r'\b([A-Z][A-Za-z0-9]+__c)\b', text)))

    requirements = docs / "requirements" / "requirements.md"
    if requirements.exists():
        text = requirements.read_text(encoding="utf-8")
        cache["fr_ids"] = sorted(set(re.findall(r'\b(FR-\d{3})\b', text)))
        cache["br_ids"] = sorted(set(re.findall(r'\b(BR-\d{3})\b', text)))

    out = cache_dir / "_context_cache.json"
    out.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[context_cache] glossary:{len(cache.get('glossary', {}))} "
        f"UC:{len(cache.get('uc_ids', []))} FR:{len(cache.get('fr_ids', []))} "
        f"→ {out}"
    )


if __name__ == "__main__":
    main()
