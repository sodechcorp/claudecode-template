"""保守ポータル（support-desk）の MCP が、この案件で設定されているかだけを返す。

使い方（プロジェクトのルートで）:
    python scripts/python/issue-source/portal_configured.py
    （試験用: --home <フォルダ> で ~/.claude.json の代わりに <フォルダ>/.claude.json を見る）

出力は1語だけ:
    configured  … 設定がある（つながるかは呼ぶ側が mcp__support_desk__get_customers で確かめる）
    none        … 設定がない（課題は Backlog から読む。聞かない）

見る場所（Claude Code が MCP を読む場所と同じ）:
    1. プロジェクトの .mcp.json の mcpServers.support_desk
    2. ~/.claude.json の mcpServers.support_desk（ユーザーの設定）と
       projects[<このフォルダ>].mcpServers.support_desk（このフォルダだけの設定）。
       CLAUDE_CONFIG_DIR があれば、その下の .claude.json も見る

.mcp.json などには Backlog の API キーなどの秘密が入っているので、中身は一切出力しない
（キーの有無だけを見る）。読めない・壊れているファイルは「設定なし」として扱う。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SERVER = "support_desk"


def _load(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _has_server(section: object) -> bool:
    return isinstance(section, dict) and isinstance(section.get("mcpServers"), dict) and SERVER in section["mcpServers"]


def _same_dir(a: str, b: Path) -> bool:
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(str(b)))
    except (TypeError, ValueError):
        return False


def configured(project_dir: Path, user_files: list[Path]) -> bool:
    if _has_server(_load(project_dir / ".mcp.json")):
        return True
    for path in user_files:
        user = _load(path)
        if _has_server(user):
            return True
        projects = user.get("projects")
        if isinstance(projects, dict):
            for key, value in projects.items():
                if _same_dir(key, project_dir) and _has_server(value):
                    return True
    return False


def main(argv: list[str]) -> int:
    args = argv[1:]
    home = Path.home()
    if "--home" in args:
        i = args.index("--home")
        home = Path(args[i + 1])
        del args[i:i + 2]
        user_files = [home / ".claude.json"]
    else:
        user_files = [home / ".claude.json"]
        if os.environ.get("CLAUDE_CONFIG_DIR"):
            user_files.append(Path(os.environ["CLAUDE_CONFIG_DIR"]) / ".claude.json")
    project_dir = Path(args[0]) if args else Path.cwd()
    print("configured" if configured(project_dir.resolve(), user_files) else "none")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
