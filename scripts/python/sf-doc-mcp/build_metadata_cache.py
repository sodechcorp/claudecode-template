"""
build_metadata_cache.py — cat1 が sf CLI クエリを実行した直後に呼ぶ。
sf data query ... --json の stdout を stdin 経由で受け取り、
docs/.sf/_metadata_cache.json にキー別に蓄積する。
cat4-apex/cat4-flow/cat4-lwc/cat5 は 5分以内のキャッシュがあれば再クエリしない。
Usage: sf data query "SELECT ..." --json | python build_metadata_cache.py {project_dir} --key apex_classes
"""
import argparse, datetime, json, sys
from pathlib import Path

CACHE_TTL_SECONDS = 300  # 5 minutes


def is_fresh(cache: dict) -> bool:
    cached_at = cache.get("cached_at", "")
    if not cached_at:
        return False
    try:
        delta = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(cached_at.rstrip("Z"))
        return delta.total_seconds() < CACHE_TTL_SECONDS
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir")
    parser.add_argument("--key", required=True, help="cache key (e.g. apex_classes)")
    args = parser.parse_args()

    cache_path = Path(args.project_dir) / "docs" / ".sf" / "_metadata_cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    sf_output = json.load(sys.stdin)
    records = (
        sf_output.get("result", {}).get("records", [])
        or sf_output.get("records", [])
    )

    cache: dict = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    cache[args.key] = records
    cache["cached_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[metadata_cache] {args.key}: {len(records)} records → {cache_path}")


if __name__ == "__main__":
    main()
