#!/usr/bin/env python3
"""Phase 4 クリーンアップ: tmp_dir / output_dir / project_dir の一時ファイルを削除する。"""
import argparse
import pathlib
import shutil
import sys


def _is_network_path(p: pathlib.Path) -> bool:
    """共有ドライブ・ネットワークパスかどうかを判定する。"""
    s = str(p).replace("\\", "/")
    if s.startswith("//"):
        return True
    if "共有ドライブ" in s or "shared drives" in s.lower():
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="sf-design-writer Phase 4 クリーンアップ")
    parser.add_argument("--tmp-dir", required=True, help="一時フォルダのパス（削除対象）")
    parser.add_argument("--output-dir", required=True, help="出力フォルダのパス（直下のゴミファイルを削除）")
    parser.add_argument("--project-dir", required=True, help="プロジェクトルートのパス（CWD 直下のゴミファイルを削除）")
    args = parser.parse_args()

    try:
        # tmp_dir を削除
        shutil.rmtree(args.tmp_dir, ignore_errors=True)

        # output_dir 直下に残ったゴミファイルを削除（.tmp* / *.json / *_tmp*.py）
        # ネットワークドライブの場合は .tmp* のみスキップ（削除不可のため警告回避）
        out = pathlib.Path(args.output_dir)
        for p in out.glob("*.json"):
            p.unlink(missing_ok=True)
        if not _is_network_path(out):
            for p in out.glob(".tmp*"):
                if p.is_file():
                    p.unlink(missing_ok=True)
                else:
                    shutil.rmtree(p, ignore_errors=True)
        for p in out.glob("*_tmp*.py"):
            p.unlink(missing_ok=True)

        # プロジェクトルート（CWD）に残ったゴミファイルを削除（*_result.txt / *.py / 一時 .json）
        cwd = pathlib.Path(args.project_dir)
        for pat in ["*_result.txt", "*_tmp*.txt", "*_tmp*.json"]:
            for p in cwd.glob(pat):
                p.unlink(missing_ok=True)

        print("クリーンアップ完了")
    except Exception as e:
        print(f"ERROR: クリーンアップ中に例外が発生しました: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
