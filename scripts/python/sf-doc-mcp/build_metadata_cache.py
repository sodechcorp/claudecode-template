"""
build_metadata_cache.py — sf CLI クエリを実行した直後に呼ぶ（cat1・cat4-apex・cat4-flow・cat4-lwc）。
sf data query ... --json の stdout を stdin 経由で受け取り、
docs/.sf/_metadata_cache.json にキー別に蓄積し、キーごとの書き込み時刻を cached_at_by_key に残す。
cat4-apex/cat4-flow/cat4-lwc/cat5 は cached_at_by_key が 5分以内のキーは再クエリしない。
クエリが失敗した出力（status が 0 以外・result が無い）はそのキーを消して exit 1（0件として書かない）。
cat4-apex/flow/lwc は並列に同じファイルへ書くため、読み込みから書き込みまでを OS のファイルロックで排他する。
Usage: sf data query "SELECT ..." --json | python build_metadata_cache.py {project_dir} --key apex_classes
"""
import argparse, datetime, hashlib, json, os, sys, tempfile
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


def _lock(fd: int) -> None:
    if os.name == "nt":
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_EX)


def _unlock(fd: int) -> None:
    if os.name == "nt":
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir")
    parser.add_argument("--key", required=True, help="cache key (e.g. apex_classes)")
    args = parser.parse_args()

    cache_path = Path(args.project_dir) / "docs" / ".sf" / "_metadata_cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        sf_output = json.load(sys.stdin)
    except ValueError:
        sf_output = None
    if not isinstance(sf_output, dict):
        sf_output = {}
    ok = sf_output.get("status", 0) == 0 and isinstance(sf_output.get("result"), dict)

    lock_name = hashlib.md5(str(cache_path.resolve()).encode("utf-8")).hexdigest()
    lock_fd = os.open(Path(tempfile.gettempdir()) / f"metadata_cache_{lock_name}.lock", os.O_RDWR | os.O_CREAT)
    _lock(lock_fd)
    try:
        cache: dict = {}
        if cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                cache = {}

        cache.pop("cached_at", None)
        cached_at_by_key = cache.setdefault("cached_at_by_key", {})
        if ok:
            records = sf_output["result"].get("records", [])
            cache[args.key] = records
            cached_at_by_key[args.key] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        else:
            cache.pop(args.key, None)
            cached_at_by_key.pop(args.key, None)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        _unlock(lock_fd)
        os.close(lock_fd)

    if not ok:
        detail = f"{sf_output.get('name', '')}: {sf_output['message']}" if sf_output.get("message") else "sf の出力に result（object）が無い"
        print(f"[metadata_cache] {args.key}: クエリ失敗のためキャッシュしない（{detail}）", file=sys.stderr)
        sys.exit(1)
    print(f"[metadata_cache] {args.key}: {len(records)} records → {cache_path}")


if __name__ == "__main__":
    main()
