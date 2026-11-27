"""
並列に動くエージェント（/sf-memory の cat4-apex・flow・lwc）が同じファイルを読み書きするときの排他と差し替え。

- file_lock: 読込から保存までを OS のファイルロックで排他する（ロックファイルは一時フォルダに置く）
- write_text_atomic: 同じフォルダの一時ファイルに書いて差し替える（並列に読む側が空・途中までの中身を読まない）
- update_json: JSON ファイルの1キーを排他して書き換える
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


@contextlib.contextmanager
def file_lock(path: Path, timeout: float = 90.0):
    name = hashlib.md5(str(Path(path).resolve()).encode("utf-8")).hexdigest()
    fd = os.open(Path(tempfile.gettempdir()) / f"sfdoc_{name}.lock", os.O_RDWR | os.O_CREAT)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                if os.name == "nt":
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise RuntimeError(f"ロックを {timeout:.0f} 秒待っても取れない: {path}")
                time.sleep(0.1)
        try:
            yield
        finally:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _retry(fn, timeout: float = 30.0):
    # Windows では他のプロセスが開いている間は差し替えられず、差し替えの途中は開けない
    deadline = time.monotonic() + timeout
    while True:
        try:
            return fn()
        except PermissionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def read_text(path: Path) -> str:
    return _retry(lambda: Path(path).read_text(encoding="utf-8"))


def write_text_atomic(path: Path, text: str) -> None:
    """Path.write_text(text, encoding="utf-8") と同じ中身（改行は OS の既定）を、差し替えで書く。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, path.stat().st_mode & 0o777 if path.exists() else 0o644)  # mkstemp の 0600 のままにしない
        _retry(lambda: os.replace(tmp, path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def update_json(path: Path, key: str, value) -> None:
    path = Path(path)
    with file_lock(path):
        data = json.loads(read_text(path)) if path.exists() else {}
        data[key] = value
        write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2))
