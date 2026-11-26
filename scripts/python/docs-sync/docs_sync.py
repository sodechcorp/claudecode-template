"""案件の記録（/git-sync と同じ範囲の docs/ とルートの CLAUDE.md）を Git に自動で送る（/git-sync の代わり）。

使い方（プロジェクトのルートで）:
    python scripts/python/docs-sync/docs_sync.py "{何の記録か}"     # 例: "backlog GF-12 の記録"（先頭に / を付けない。Git Bash がパスに書き換える）
    python scripts/python/docs-sync/docs_sync.py --dry-run "{…}"   # 何をするかだけ出す（コミット・取り込み・送信をしない）

すること（force は使わない）:
    1. 対象（下の TARGETS。/git-sync が同期していた範囲と同じで、増やさない。docs/logs/・docs/.sf/・docs/.backlog_config.yml などの
       個人・作業場のファイルは入れない）だけを add・commit する。ほかのファイルは触らない。送り先が無ければコミットもしない
    2. 送り先（今のブランチの upstream）から取り込む（git fetch → git merge。本物の3者マージ）。
       行を積み上げる表（decisions.md・case-index.md・pitfalls.md など）は merge=union で、両方の行を残す
       （.git/info/attributes に書く。リポジトリのファイルは増やさない）
    3. 送る（git push）。ほかの人が先に送って断られたら、もう一度だけ 2 から
止まるとき（勝手に上書きしない。終了コードと1行の理由を出す）:
    0 … 送った／送るものがない
    3 … 取り込みで競合した、または手元の未保存の変更とぶつかった → 取り込みを取りやめて元に戻す（手元のコミットは残る）
    4 … 送らなかった（送り先が無い〔コミットもしない〕・detached HEAD・docs 以外のまだ送っていないコミットがある・送信に失敗した）
    2 … 使い方の誤り・Git のリポジトリでない
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# /git-sync（廃止）の「全文同期型」と「積み上げ同期型」の表と同じ範囲
TARGETS = [
    "CLAUDE.md",
    "docs/_README.md",
    "docs/overview",
    "docs/requirements",
    "docs/flow",
    "docs/catalog",
    "docs/architecture",
    "docs/design",
    "docs/data",
    "docs/decisions.md",
    "docs/knowledge/sf-standard.md",
    "docs/knowledge/case-index.md",
    "docs/knowledge/pitfalls.md",
    "docs/knowledge/cases",
    "docs/knowledge/effort-calibration.md",
    "docs/knowledge/global-calibration.md",
    "docs/knowledge/global-pitfalls.md",
    "docs/knowledge/test-prerequisites.md",
    "docs/knowledge/archive",
]
UNION_FILES = [
    "docs/decisions.md",
    "docs/knowledge/case-index.md",
    "docs/knowledge/pitfalls.md",
    "docs/knowledge/global-pitfalls.md",
    "docs/knowledge/test-prerequisites.md",
    "docs/knowledge/archive/*.md",
]
MARK = "# docs_sync.py: 行を積み上げる表は両方の行を残す"


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", "-c", "core.quotepath=false", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip() or p.stdout.strip()}")
    return p


def in_scope(path: str) -> bool:
    return any(path == t or path.startswith(t + "/") for t in TARGETS)


def ensure_union_attributes() -> None:
    common = Path(git("rev-parse", "--git-common-dir", check=True).stdout.strip())
    attrs = common / "info" / "attributes"
    text = attrs.read_text(encoding="utf-8") if attrs.exists() else ""
    if MARK in text:
        return
    attrs.parent.mkdir(parents=True, exist_ok=True)
    lines = [MARK] + [f"{f} merge=union" for f in UNION_FILES]
    sep = "" if not text or text.endswith("\n") else "\n"
    attrs.write_text(text + sep + "\n".join(lines) + "\n", encoding="utf-8")


def merge_upstream(upstream: str) -> tuple[int, str]:
    """取り込む。競合・ぶつかりは取りやめて元に戻す。"""
    f = git("fetch", "--quiet")
    if f.returncode != 0:
        return 4, f"送り先から取得できませんでした（{f.stderr.strip()[:200]}）。手元のコミットは残っています"
    behind = git("rev-list", "--count", f"HEAD..{upstream}").stdout.strip()
    if behind in ("", "0"):
        return 0, ""
    incoming = [p for p in git("diff", "--name-only", f"HEAD...{upstream}").stdout.splitlines() if p.strip()]
    m = git("merge", "--no-edit", upstream)
    if m.returncode != 0:
        conflicted = [p for p in git("diff", "--name-only", "--diff-filter=U").stdout.splitlines() if p.strip()]
        if git("rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0:
            git("merge", "--abort")
        what = "、".join(conflicted[:10]) if conflicted else (m.stderr.strip().splitlines() or [""])[0][:200]
        return 3, f"ほかの人の変更とぶつかったので取り込みを取りやめました（{what}）。手元のコミットは残っています。解消してから送ってください"
    others = [p for p in incoming if not in_scope(p)]
    note = f"ほかの人の docs 以外の変更も {len(others)} 件取り込みました（例: {others[0]}）" if others else ""
    return 0, note


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = argv[1:]
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    reason = args[0].strip() if args and args[0].strip() else "記録の更新"

    if git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        print("[docs_sync] Git のリポジトリではないので送りません")
        return 2
    top = Path(git("rev-parse", "--show-toplevel", check=True).stdout.strip())
    if Path.cwd().resolve() != top.resolve():
        print(f"[docs_sync] プロジェクトのルート（{top}）で実行してください")
        return 2
    sym = git("symbolic-ref", "-q", "--short", "HEAD")
    branch = sym.stdout.strip()
    if sym.returncode != 0 or not branch:
        print("[docs_sync] detached HEAD のため送りません（ブランチに切り替えてから: git checkout main など）")
        return 4

    existing = [t for t in TARGETS if (top / t).exists()]
    changed = [l[3:] for l in git("status", "--porcelain", "--", *existing).stdout.splitlines() if l.strip()] if existing else []
    up = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    upstream = up.stdout.strip() if up.returncode == 0 else ""

    if dry:
        print(f"[docs_sync] dry-run: ブランチ {branch}・送り先 {upstream or '（無し）'}・コミットする変更 {len(changed)} 件")
        for c in changed[:20]:
            print(f"  {c}")
        return 0

    if not upstream:
        print(f"[docs_sync] 送り先（upstream）が無いので送りません（コミットもしていません。git push -u origin {branch} で送り先を決められます）")
        return 4

    if changed:
        git("add", "-A", "--", *existing, check=True)
        staged = [p for p in git("diff", "--cached", "--name-only").stdout.splitlines() if p.strip()]
        outside = [p for p in staged if not in_scope(p)]
        if outside:
            # 対象の外が先に add されていた（利用者が自分で add したもの）。混ぜずに止める
            git("reset", "-q", "--", *existing)
            print(f"[docs_sync] docs 以外のファイルが add されているので送りません（{outside[0]} など）。コミットしてから、もう一度実行してください")
            return 4
        if staged:
            git("commit", "-q", "-m", f"docs: {reason}（自動の同期）", check=True)

    ensure_union_attributes()
    notes = []
    for attempt in range(2):
        code, note = merge_upstream(upstream)
        if note:
            notes.append(note)
        if code != 0:
            print(f"[docs_sync] {note}")
            return code
        ahead = [l for l in git("log", "--no-merges", "--format=", "--name-only", f"{upstream}..HEAD").stdout.splitlines() if l.strip()]
        if not ahead:
            print("[docs_sync] 送るものはありません" + (f"。{'。'.join(notes)}" if notes else ""))
            return 0
        outside = sorted({p for p in ahead if not in_scope(p)})
        if outside:
            print(f"[docs_sync] docs 以外のまだ送っていないコミットがあるので、自動では送りません（{outside[0]} など）。記録はコミット済みです。確かめてから git push してください")
            return 4
        push = git("push", "--quiet")
        if push.returncode == 0:
            print(f"[docs_sync] 送りました（{branch} → {upstream}）" + (f"。{'。'.join(notes)}" if notes else ""))
            return 0
        if attempt == 0 and ("rejected" in push.stderr or "fetch first" in push.stderr or "non-fast-forward" in push.stderr):
            continue
        print(f"[docs_sync] 送れませんでした（{push.stderr.strip()[:200]}）。記録はコミット済みです")
        return 4
    print("[docs_sync] 送れませんでした（ほかの人が続けて送っています）。記録はコミット済みです。少しおいて、もう一度実行してください")
    return 4


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except RuntimeError as e:
        print(f"[docs_sync] 送れませんでした（{str(e)[:300]}）")
        sys.exit(4)
