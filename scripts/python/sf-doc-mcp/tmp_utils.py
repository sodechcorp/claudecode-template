"""一時ファイル/ディレクトリの作成先をプロジェクトの docs/.tmp/ に固定する共通ユーティリティ。

使い方:
  1. エントリポイント（main）の出力先確定直後に set_project_tmp_dir(out_dir) を呼ぶ
  2. 各所の tempfile 呼び出しに dir=get_project_tmp_dir() を追加
  3. 終了時のクリーンアップは atexit で自動実行される

設計メモ:
  - docs/ 配下でも直下でもなく docs/.tmp/ に集約する（プロジェクトフォルダ直下にゴミを作らない）
  - out_dir がネットワーク/共有ドライブの場合は OS の TEMP 配下に使う
    （共有ドライブへの削除は hook によりハードブロックされるため）
  - .tmp/ 削除は「空の時だけ」実行。中身が残っていれば他プロセスや前回残骸の可能性があるため残す
"""

from __future__ import annotations

import atexit
import sys
import tempfile
from pathlib import Path
from typing import Optional

_project_tmp_dir: Optional[Path] = None
_atexit_registered: bool = False


def _is_network_path(p: Path) -> bool:
    """共有ドライブ・ネットワークパスかどうかを判定する。

    G:\\共有ドライブ や UNC パス（\\\\server\\...）が対象。
    """
    s = str(p).replace("\\", "/")
    # UNC パス
    if s.startswith("//"):
        return True
    # 既知の共有ドライブキーワード
    if "共有ドライブ" in s or "shared drives" in s.lower():
        return True
    return False


def set_project_tmp_dir(out_dir) -> Path:
    """out_dir の祖先から最初に見つかる docs/ 配下に .tmp/ を作る。

    out_dir がネットワーク/共有ドライブの場合は OS の TEMP 配下に作る
    （共有ドライブへの削除は hook によりハードブロックされるため）。
    docs/ が祖先に存在しなければ、out_dir そのものの中に .tmp/ を作る。
    初回呼び出し時に atexit でクリーンアップを登録する（重複登録しない）。
    """
    global _project_tmp_dir, _atexit_registered
    p = Path(out_dir).resolve()

    # ネットワーク/共有ドライブの場合はローカル TEMP を使う
    if _is_network_path(p):
        tmp = Path(tempfile.gettempdir()) / "sf-design" / ".tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        _project_tmp_dir = tmp
        if not _atexit_registered:
            atexit.register(cleanup_project_tmp_dir)
            _atexit_registered = True
        return tmp

    tmp: Optional[Path] = None
    for ancestor in [p] + list(p.parents):
        if ancestor.name == "docs":
            tmp = ancestor / ".tmp"
            break
    if tmp is None:
        target = p if p.is_dir() else p.parent
        tmp = target / ".tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    _project_tmp_dir = tmp
    if not _atexit_registered:
        atexit.register(cleanup_project_tmp_dir)
        _atexit_registered = True
    return tmp


def get_project_tmp_dir() -> Optional[str]:
    """tempfile の dir= 引数に渡す文字列を返す。

    未設定の場合は None を返し、tempfile は OS 標準 TEMP にフォールバックする。
    """
    return str(_project_tmp_dir) if _project_tmp_dir else None


def cleanup_project_tmp_dir() -> None:
    """.tmp/ が空なら削除。中身が残っていればログを出して残す（誤爆防止）。"""
    global _project_tmp_dir
    if not _project_tmp_dir or not _project_tmp_dir.exists():
        return
    try:
        _project_tmp_dir.rmdir()
    except OSError:
        try:
            remaining = list(_project_tmp_dir.iterdir())
        except Exception:
            remaining = []
        print(
            f"[INFO] {_project_tmp_dir} に一時ファイルが残っています"
            f"（{len(remaining)}件）。手動で確認・削除してください。",
            file=sys.stderr,
        )
