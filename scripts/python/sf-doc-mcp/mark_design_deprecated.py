"""
deprecated=true になったコンポーネントの設計書 MD に注記バナーと
「実装状態」セルの **[廃止]** 化を一括適用するスクリプト。
deprecated=false に戻った（force-app に戻った）機能の設計書からは、このスクリプトが付けた
バナーと **[廃止]** を外し、「実装状態」を廃止にする前の値（記録が無ければ「実装済み」）に戻す。

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

# 設計書を探すフォルダは verify_cat4_completeness.py と同じ scan_features.py の定義を使う（DRY）
from scan_features import design_doc_ids, design_folders


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
# 廃止にする前の「実装状態」の値は、戻すときのためにセルの中のコメントに残す
STATUS_SAVED = "<!-- sf-memory:status-before-deprecated: {} -->"


def _to_deprecated(m: re.Match, save: bool = True) -> str:
    before = m.group(2).strip()
    saved = f" {STATUS_SAVED.format(before)}" if save and before and "-->" not in before else ""
    return f"{m.group(1)} **[廃止]**{saved} {m.group(3)}"


# apply_deprecated が入れたバナー（日付だけ可変の全文一致。行頭のときだけ・前の空行は空行のときだけ消す。直後に人が引用行を足したものは一致させない）と、書き換えた「実装状態」セル
_BANNER_PRE, _BANNER_POST = BANNER_TEMPLATE.split("{scan_date}")
BANNER_BLOCK_PATTERN = re.compile(
    r"(?:(?<=\n)\n)?(?<![^\n])" + re.escape(_BANNER_PRE.format(marker=BANNER_MARKER)) + r"[^）\n]*"
    + re.escape(_BANNER_POST) + r"(?!>)\n?"
)
STATUS_DEPRECATED_PATTERN = re.compile(
    r"^(\|\s*実装状態\s*\|)\s*\*\*\[廃止\]\*\*\s*(?:<!-- sf-memory:status-before-deprecated: (.*?) -->\s*)?(\|\s*)$",
    re.MULTILINE,
)
# バナーが無くても、前の値の記録が付いたセルはこのスクリプトが書いたもの
STATUS_SAVED_PATTERN = re.compile(
    r"^(\|\s*実装状態\s*\|)\s*\*\*\[廃止\]\*\*\s*<!-- sf-memory:status-before-deprecated: (.*?) -->\s*(\|\s*)$",
    re.MULTILINE,
)
STATUS_LEFT_PATTERN = re.compile(r"^\|\s*実装状態\s*\|.*廃止", re.MULTILINE)


def _read_md(md_path: Path) -> tuple[str, tuple[str, str]]:
    """BOM を除き改行を LF にそろえた本文と、書き戻すときの形（BOM の有無・元のファイルに多い方の改行）を返す"""
    with open(md_path, encoding="utf-8", newline="") as f:
        raw = f.read()
    bom = "\ufeff" if raw.startswith("\ufeff") else ""
    raw = raw[len(bom):]
    crlf = raw.count("\r\n")
    return raw.replace("\r\n", "\n"), (bom, "\r\n" if crlf > raw.count("\n") - crlf else "\n")


def _write_md(md_path: Path, text: str, form: tuple[str, str]) -> None:
    bom, newline = form
    with open(md_path, "w", encoding="utf-8", newline="") as f:
        f.write(bom + text.replace("\n", newline))


def find_design_md(project_dir: Path, ftype: str, feat_id: str, api_name: str) -> Path | None:
    """feature_ids.yml のエントリに対応する設計書 MD を、design_folders のフォルダの順に探して返す。

    種別のフォルダの外では、同じ kind の別のフォルダにある古い番号の設計書（同じ ID の別のコンポーネント）に
    注記を付けないよう、本文に api_name が出てくるものだけ採る。
    """
    folders = design_folders(ftype)
    for folder in folders:
        md = _find_in_folder(project_dir / "docs" / "design" / folder, feat_id, api_name)
        if md and (folder == folders[0] or api_name in md.read_text(encoding="utf-8", errors="ignore")):
            return md
    return None


def _find_in_folder(sub: Path, feat_id: str, api_name: str) -> Path | None:
    """検索戦略:
    1. 「【{feat_id}】*.md」の glob で厳密に検索
    2. 複合ファイル（【F-002・F-003】等）の feat_id 包含も拾う
    """
    if not sub.exists():
        return None

    # 厳密なプレフィックス検索
    candidates = list(sub.glob(f"【{feat_id}】*.md"))
    if len(candidates) == 1:
        return candidates[0]

    if not candidates:
        for md in sub.glob("【*】*.md"):
            if feat_id in design_doc_ids(md):
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
    text, form = _read_md(md_path)
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
    # 前の値を残すのはバナーを付けたときだけ（付いた後に書き換えられた値を「前の値」にしない）
    replaced_text, n = STATUS_ROW_PATTERN.subn(lambda m: _to_deprecated(m, result["banner_added"]), new_text)
    if n > 0:
        result["status_replaced"] = True
        new_text = replaced_text
    elif "実装状態" not in new_text:
        result["status_no_match"] = True

    if not dry_run and new_text != text:
        _write_md(md_path, new_text, form)

    return result


def restore_deprecated(md_path: Path, dry_run: bool) -> tuple[str, bool]:
    """apply_deprecated が付けたバナーと「実装状態」の **[廃止]** を外し、「実装状態」を廃止にする前の値に戻す。
    バナーが無くても、前の値の記録が付いたセルは戻す（バナーだけ手で外された場合）。
    戻り値: (状態, 実装状態に「廃止」が残ったか)。状態は "restored"（外した）/ "restored_default"（前の値の記録が無く
            「実装済み」にした）/ "none"（バナーも記録も無い）/ "edited"（バナーの文が定型と違うため触らない）
    """
    text, form = _read_md(md_path)
    if BANNER_MARKER in text:
        new_text, n = BANNER_BLOCK_PATTERN.subn("", text, count=1)
        if n == 0:
            return "edited", False
        pattern = STATUS_DEPRECATED_PATTERN
    elif STATUS_SAVED_PATTERN.search(text):
        new_text, pattern = text, STATUS_SAVED_PATTERN
    else:
        return "none", bool(STATUS_DEPRECATED_PATTERN.search(text))
    defaulted = []

    def _back(m: re.Match) -> str:
        if m.group(2) is None:
            defaulted.append(True)
        return f"{m.group(1)} {m.group(2) or '実装済み'} {m.group(3)}"

    left = bool(STATUS_LEFT_PATTERN.search(pattern.sub("", new_text)))  # 戻す行の値そのものに「廃止」があっても数えない
    new_text = pattern.sub(_back, new_text)
    if not dry_run:
        _write_md(md_path, new_text, form)
    return ("restored_default" if defaulted else "restored"), left


def main() -> None:
    parser = argparse.ArgumentParser(
        description="deprecated=true のコンポーネント設計書 MD に廃止注記を追加し、有効に戻った機能の設計書から外す"
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
    active_ids = {e.get("id") for e in ledger.get("features", []) if not e.get("deprecated")}

    stats = {
        "total": len(deprecated_entries),
        "updated": 0,
        "already": 0,
        "missing_md": 0,
        "shared": 0,
        "warning": 0,
        "restored": 0,
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

        # 複合ファイルは、載っている機能がすべて deprecated になるまで注記しない
        if design_doc_ids(md) & active_ids:
            stats["shared"] += 1
            print(
                f"  [skip] 複合ファイルの他の機能が有効: {feat_id} ({ftype}) {md.name}",
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

    # deprecated=false に戻った機能の設計書から、付けたバナーと **[廃止]** を外す（複合ファイルは1つでも有効なら外す）
    seen: set[Path] = set()
    for entry in ledger.get("features", []):
        if entry.get("deprecated"):
            continue
        feat_id, ftype, api_name = entry.get("id", ""), entry.get("type", ""), entry.get("api_name", "")
        md = find_design_md(project_dir, ftype, feat_id, api_name)
        if md is None or md in seen:
            continue
        seen.add(md)
        state, status_left = restore_deprecated(md, args.dry_run)
        if status_left:
            stats["warning"] += 1
            print(
                f"  [WARN] 機能が有効に戻ったが、実装状態に「廃止」が残っています（手で直す）: {feat_id} {md}",
                file=sys.stderr,
            )
        if state in ("restored", "restored_default"):
            stats["restored"] += 1
            if args.dry_run:
                print(f"  [dry-run] {md.name}: 廃止バナーと実装状態の **[廃止]** を外す予定")
            if state == "restored_default":
                print(
                    f"  [INFO] 機能が有効に戻ったので廃止バナーを外し、実装状態を「実装済み」にした（廃止にする前の値の記録なし）: {feat_id} {md}",
                    file=sys.stderr,
                )
        elif state == "edited":
            stats["warning"] += 1
            print(
                f"  [WARN] 機能が有効に戻ったが、廃止バナーの文が定型と違うため外していません（バナーと実装状態の **[廃止]** を手で外す）: {feat_id} {md}",
                file=sys.stderr,
            )

    dry_label = " (dry-run)" if args.dry_run else ""
    print(
        f"[mark_design_deprecated] deprecated={stats['total']} "
        f"updated={stats['updated']} already={stats['already']} "
        f"missing_md={stats['missing_md']} shared={stats['shared']} warning={stats['warning']} restored={stats['restored']}"
        f"{dry_label}"
    )


if __name__ == "__main__":
    main()
