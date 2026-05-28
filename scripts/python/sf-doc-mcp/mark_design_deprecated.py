"""
deprecated=true になったコンポーネントの設計書 MD に注記バナーと
「実装状態」セルの **[廃止]** 化を一括適用するスクリプト。

- 設計書ファイルは削除しない（手動追記・設計判断の根拠を保持）
- 冪等: BANNER_MARKER の有無で二重追記を防止
- 「実装状態」セルは正規表現の負の先読みで二重置換を防止

Usage:
    python mark_design_deprecated.py --project-dir <PATH> [--dry-run] [--scan-timestamp YYYY-MM-DD]
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

import yaml

# scan_features.py の _TYPE_TO_DESIGN_FOLDER を再利用（DRY）
from scan_features import _TYPE_TO_DESIGN_FOLDER


BANNER_MARKER = "<!-- sf-memory:deprecated-banner -->"
BANNER_TEMPLATE = (
    "{marker}\n"
    "> **Deprecated**: この機能は `feature_ids.yml` で `deprecated=true` です"
    "（最終スキャン: {scan_date}）。実装は組織から削除済みのため、"
    "本設計書は履歴目的で保持しています。\n"
)

# 既に **[廃止]** を含む行を負の先読みで除外して二重置換を防ぐ
STATUS_ROW_PATTERN = re.compile(
    r"^(\|\s*実装状態\s*\|)\s*(?!.*\*\*\[廃止\]\*\*)([^|]+?)(\|\s*)$",
    re.MULTILINE,
)
STATUS_ROW_REPLACEMENT = r"\1 **[廃止]** \3"


def find_design_md(project_dir: Path, ftype: str, feat_id: str, api_name: str) -> Path | None:
    """feature_ids.yml のエントリに対応する設計書 MD を探して返す。

    検索戦略:
    1. _TYPE_TO_DESIGN_FOLDER でサブフォルダを特定
    2. 「【{feat_id}】*.md」の glob で厳密に検索
    3. 結合ファイル「【CMP-002〜CMP-003】...」の feat_id 包含も拾う
    """
    folder = _TYPE_TO_DESIGN_FOLDER.get(ftype)
    if folder is None:
        return None
    sub = project_dir / "docs" / "design" / folder
    if not sub.exists():
        return None

    # 厳密なプレフィックス検索
    candidates = list(sub.glob(f"【{feat_id}】*.md"))
    if len(candidates) == 1:
        return candidates[0]

    if not candidates:
        # 結合ファイル「【CMP-002〜CMP-003】...」形式も拾う
        for md in sub.glob("【*】*.md"):
            stem = md.stem
            # 「【」から「】」の間を取り出す
            m = re.match(r"^【([^】]+)】", stem)
            if m:
                raw_ids = re.split(r"[、,〜~]", m.group(1))
                ids = [i.strip() for i in raw_ids]
                if feat_id in ids:
                    return md
        return None

    # 複数候補時は api_name を正規化して最も近いものを選ぶ
    def normalize(s: str) -> str:
        return re.sub(r"[-_\s]", "", s.lower())

    target = normalize(api_name)
    for md in candidates:
        stem_tail = md.stem.split("】", 1)[-1]
        if normalize(stem_tail) == target:
            return md
    return candidates[0]


def apply_deprecated(md_path: Path, scan_date: str, dry_run: bool) -> dict:
    """設計書 MD に deprecated バナーと実装状態 **[廃止]** を適用する。

    戻り値:
        banner_added: バナーを新規追記したか
        status_replaced: 「実装状態」セルを書き換えたか
        already_marked: 既にバナーマーカーが存在したか
        status_no_match: 「実装状態」行が見つからなかったか（テンプレ非準拠 MD の可能性）
    """
    text = md_path.read_text(encoding="utf-8")
    result = {
        "banner_added": False,
        "status_replaced": False,
        "already_marked": False,
        "status_no_match": False,
    }
    new_text = text

    # 1. バナー追記（冪等性: BANNER_MARKER の有無で判定）
    if BANNER_MARKER in text:
        result["already_marked"] = True
    else:
        banner = BANNER_TEMPLATE.format(marker=BANNER_MARKER, scan_date=scan_date)
        # H1 の直後に挿入。H1 が無ければ先頭。
        m = re.search(r"^(#\s+.+?\n)", new_text, re.MULTILINE)
        if m:
            insert_at = m.end()
            new_text = new_text[:insert_at] + "\n" + banner + "\n" + new_text[insert_at:]
        else:
            new_text = banner + "\n" + new_text
        result["banner_added"] = True

    # 2. 「実装状態」セルを **[廃止]** に書き換え
    replaced_text, n = STATUS_ROW_PATTERN.subn(STATUS_ROW_REPLACEMENT, new_text)
    if n > 0:
        result["status_replaced"] = True
        new_text = replaced_text
    elif "実装状態" not in new_text:
        result["status_no_match"] = True

    if not dry_run and new_text != text:
        md_path.write_text(new_text, encoding="utf-8")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="deprecated=true のコンポーネント設計書 MD に廃止注記を追加する"
    )
    parser.add_argument("--project-dir", required=True, help="プロジェクトルートパス")
    parser.add_argument("--dry-run", action="store_true", help="差分検出のみ（ファイル書き換えなし）")
    parser.add_argument("--scan-timestamp", help="バナーに書き込む最終スキャン日付 YYYY-MM-DD")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    ledger_path = project_dir / "docs" / ".sf" / "feature_ids.yml"
    if not ledger_path.exists():
        print(f"[ERROR] feature_ids.yml が見つかりません: {ledger_path}", file=sys.stderr)
        sys.exit(1)

    # 最終スキャン日付: 引数 > feature_ids.yml の mtime > 当日
    if args.scan_timestamp:
        scan_date = args.scan_timestamp
    else:
        try:
            scan_date = datetime.datetime.fromtimestamp(
                ledger_path.stat().st_mtime
            ).strftime("%Y-%m-%d")
        except OSError:
            scan_date = datetime.date.today().isoformat()

    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8")) or {}
    deprecated_entries = [e for e in ledger.get("features", []) if e.get("deprecated")]

    stats = {
        "total": len(deprecated_entries),
        "updated": 0,
        "already": 0,
        "missing_md": 0,
        "warning": 0,
    }
    updated_files: list[str] = []

    for entry in deprecated_entries:
        feat_id = entry.get("id", "")
        ftype = entry.get("type", "")
        api_name = entry.get("api_name", "")

        md = find_design_md(project_dir, ftype, feat_id, api_name)
        if md is None:
            stats["missing_md"] += 1
            print(
                f"  [skip] 設計書 MD なし: {feat_id} ({ftype}) {api_name}",
                file=sys.stderr,
            )
            continue

        r = apply_deprecated(md, scan_date, args.dry_run)

        if r["status_no_match"]:
            stats["warning"] += 1
            print(
                f"  [WARN] 「実装状態」行が見つかりません（テンプレ非準拠の手書き MD の可能性）: {md}",
                file=sys.stderr,
            )

        if r["already_marked"] and not r["status_replaced"]:
            stats["already"] += 1
        else:
            stats["updated"] += 1
            updated_files.append(md.as_posix())
            if args.dry_run:
                banner_msg = "バナー追加予定" if r["banner_added"] else "バナー追加不要"
                status_msg = "実装状態→[廃止] 予定" if r["status_replaced"] else "実装状態行なし"
                print(f"  [dry-run] {md.name}: {banner_msg} / {status_msg}")

    dry_label = " (dry-run)" if args.dry_run else ""
    print(
        f"[mark_design_deprecated] deprecated={stats['total']} "
        f"updated={stats['updated']} already={stats['already']} "
        f"missing_md={stats['missing_md']} warning={stats['warning']}"
        f"{dry_label}"
    )


if __name__ == "__main__":
    main()
