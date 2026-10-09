"""
ソースファイルのハッシュを計算し、既存 Excel の _meta に保存されたハッシュと比較する。

Usage:
  python source_hash_checker.py \
    --project-dir "path/to/project" \
    --source-paths "file1.cls,file2.cls" \
    --existing-excel "path/to/design.xlsx"

Output (stdout):
  hash:XXXXXXXX...    # 計算した SHA256 ハッシュ（ハッシュする中身が無ければ空）
  status:MATCH        # または CHANGED / NEW / NO_HASH

Exit code:
  0: ハッシュ一致 → LLM スキップ可能
  1: 不一致 / Excel なし / ハッシュ未記録 / ソースなし → LLM 実行が必要
"""
import argparse
import hashlib
import sys
from pathlib import Path

from meta_store import compute_source_hash, get_stored_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", default="",
                        help="相対パスの基準（feature_list.json の source_file は案件のルートからの相対パス）")
    parser.add_argument("--source-paths", required=True,
                        help="カンマ区切りのソースファイル／ディレクトリパス")
    parser.add_argument("--existing-excel", default="",
                        help="既存 Excel ファイルパス（省略時は新規扱い）")
    args = parser.parse_args()

    paths = [str(Path(args.project_dir) / p.strip()) for p in args.source_paths.split(",") if p.strip()]
    current_hash = compute_source_hash(paths)
    # 空の入力のハッシュ（ファイル0件・空フォルダ）を渡すと _meta に残り、次回も MATCH になって再生成がスキップされ続ける
    if current_hash == hashlib.sha256().hexdigest():
        print("hash:")
        print("status:NEW")
        sys.exit(1)
    print(f"hash:{current_hash}")

    excel_path = args.existing_excel.strip()
    if not excel_path or not Path(excel_path).exists():
        print("status:NEW")
        sys.exit(1)

    stored_hash = get_stored_hash(excel_path)
    if stored_hash is None:
        print("status:NO_HASH")
        sys.exit(1)

    if stored_hash == current_hash:
        print("status:MATCH")
        sys.exit(0)
    else:
        print("status:CHANGED")
        sys.exit(1)


if __name__ == "__main__":
    main()
