#!/usr/bin/env python3
"""BOM (UTF-8 with BOM: EF BB BF) 混入ファイル検出ツール。

背景:
  エージェント/コマンド定義（.claude/agents/*.md, .claude/commands/*.md）は
  先頭の YAML frontmatter（`---` で始まる）をパーサーが読んで登録する。
  ファイル先頭に UTF-8 BOM が付くと `---` の前に不可視バイトが挟まり、
  frontmatter が解析できず「エラーも警告も出ないままサイレントに
  未登録になる」（呼び出すまで気づけない）。

用途:
  1. テンプレート本体へのコミット前チェック（開発者が手動実行）
       python3 scripts/check_bom.py
  2. upgrade.sh の適用前検証（取得したテンプレートに対して自動実行）

使い方:
  python3 scripts/check_bom.py [対象ディレクトリ...]   # 省略時は .claude scripts

BOM付きファイルが見つかった場合、一覧を stderr に出力して exit 1。
無ければ何も出力せず exit 0。
"""
import os
import sys

# Windows の素の端末（cmd.exe 等）では stdout/stderr が既定で cp932 になり、
# 日本語メッセージが文字化けする。upgrade.sh からだけでなく開発者が単体で
# 実行することも想定するため、ここで明示的に utf-8 化する。
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

TARGET_EXTS = {".md", ".json", ".py", ".js", ".sh", ".ps1"}
SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv"}
BOM = b"\xef\xbb\xbf"


def find_bom_files(root):
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1].lower() not in TARGET_EXTS:
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, "rb") as f:
                    if f.read(3) == BOM:
                        hits.append(path)
            except OSError:
                continue
    return hits


def main():
    targets = sys.argv[1:] or [".claude", "scripts"]
    all_hits = []
    for t in targets:
        if os.path.isdir(t):
            all_hits.extend(find_bom_files(t))

    if all_hits:
        print(
            "BOM (UTF-8 with BOM) 付きファイルが見つかりました。"
            "YAML frontmatter の解析に失敗し、エージェント/コマンドとして"
            "登録されなくなる可能性があります:",
            file=sys.stderr,
        )
        for h in sorted(all_hits):
            print(f"  BOM: {h}", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "修正例（PowerShell）: "
            "$b=[IO.File]::ReadAllBytes($p); "
            "[IO.File]::WriteAllText($p, "
            "[Text.Encoding]::UTF8.GetString($b,3,$b.Length-3), "
            "(New-Object Text.UTF8Encoding($false)))",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
