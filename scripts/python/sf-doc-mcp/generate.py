# -*- coding: utf-8 -*-
"""オブジェクト項目定義書を生成する CLI エントリーポイント"""

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from connector import SalesforceConnector
from fetcher import MetadataFetcher
from meta_store import read_meta, strip_meta
from version_manager import VersionManager, increment_version
from writer import DefinitionWriter


def _resolve_sf() -> str:
    """sf CLI の実行パスを Windows / Linux 両対応で解決する。
    Windows の Python 3.13 では PATHEXT を参照しない subprocess の挙動で sf.cmd が
    解決できない問題があるため、明示的に .cmd / .exe を優先して which する。"""
    candidates = ("sf.cmd", "sf.exe", "sf") if platform.system() == "Windows" else ("sf",)
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return "sf"  # 最終フォールバック（既存挙動を維持）


def connect_via_sf_cli(alias: str) -> SalesforceConnector:
    """SF CLI のアクセストークンで接続する"""
    result = subprocess.run(
        [_resolve_sf(), "org", "display", "--target-org", alias, "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    raw = result.stdout
    json_start = raw.find("{")
    if json_start == -1:
        raise ConnectionError(f"SF CLI からの応答が不正です: {raw[:200]}")
    data = json.loads(raw[json_start:])
    if data.get("status") != 0:
        raise ConnectionError(f"SF CLI エラー: {data.get('message', data)}")
    r = data["result"]
    return SalesforceConnector.from_session(
        session_id=r["accessToken"],
        instance_url=r["instanceUrl"],
        username=r.get("username", alias),
    )


def resolve_objects(sf, raw_inputs: list[str]) -> list[str]:
    """API名またはラベル名からAPI名に解決する（大文字小文字・全角スペース無視）"""
    # 区切り文字を統一して分割
    joined = " ".join(raw_inputs)
    tokens = [t.strip() for t in re.split(r"[,\s　、]+", joined) if t.strip()]
    if not tokens:
        return []

    sobjects = sf.describe()["sobjects"]
    name_map  = {o["name"].lower(): o["name"] for o in sobjects}
    label_map = {o["label"].lower(): o["name"] for o in sobjects}

    resolved = []
    unresolved = []
    for token in tokens:
        key = token.lower()
        if key in name_map:
            resolved.append(name_map[key])
        elif key in label_map:
            api = label_map[key]
            print(f"  ラベル解決: '{token}' → {api}")
            resolved.append(api)
        else:
            # 部分一致（ラベル優先、次にAPI名）
            label_hits = [o for o in sobjects if key in o["label"].lower()]
            name_hits  = [o for o in sobjects if key in o["name"].lower()]
            hits = label_hits or name_hits

            if len(hits) == 1:
                print(f"  部分一致: '{token}' → {hits[0]['name']}")
                resolved.append(hits[0]["name"])
            elif len(hits) > 1:
                # 入力がラベル全体に占める割合が最大のものを推定（最も近い候補）
                best = max(hits, key=lambda o: len(key) / len(o["label"].lower()))
                ratio = len(key) / len(best["label"].lower())
                candidates = [o["name"] for o in hits]
                if ratio >= 0.6:
                    print(f"  推定一致: '{token}' → {best['name']}（候補: {candidates}）")
                else:
                    print(f"  推定一致（低確度）: '{token}' → {best['name']}（候補: {candidates}）", file=sys.stderr)
                resolved.append(best["name"])
            else:
                unresolved.append(token)

    if unresolved:
        print(f"[警告] 解決できなかったオブジェクト: {unresolved}", file=sys.stderr)

    return resolved


def default_sections() -> dict:
    return {
        "fields": True, "object_info": True, "record_types": True,
        "page_layouts": True, "lightning_pages": True, "compact_layouts": True,
        "search_layouts": True, "field_sets": True, "validation_rules": True,
        "lookup_filters": True, "field_usage": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Salesforce オブジェクト項目定義書を生成")
    # 接続方法（どちらか一方を指定）
    conn_group = parser.add_mutually_exclusive_group(required=True)
    conn_group.add_argument("--sf-alias",       help="SF CLI のエイリアス名")
    conn_group.add_argument("--username",        help="Salesforce ユーザー名（メールアドレス）")
    parser.add_argument("--password",            default="", help="パスワード（--username 使用時）")
    parser.add_argument("--security-token",      default="", help="セキュリティトークン（--username 使用時）")
    parser.add_argument("--domain",              default="login", help="ドメイン: login / test（デフォルト: login）")
    parser.add_argument("--objects",             required=True, nargs="+",
                        help="対象オブジェクト（API名またはラベル名、複数可）")
    parser.add_argument("--output-dir",          required=True,  help="出力先フォルダパス")
    parser.add_argument("--author",              required=True,  help="作成者名")
    parser.add_argument("--system-name",         default="",     help="システム名称（表紙）")
    parser.add_argument("--source-file",         default="",     help="更新時: 既存ファイルのパス")
    parser.add_argument("--version-increment",   default="minor", choices=["minor", "major"],
                        help="minor: x.1増加 / major: 1.0増加（赤字リセット）")
    args = parser.parse_args()

    is_major    = (args.version_increment == "major")
    source_file = args.source_file.strip()

    # 接続
    if args.sf_alias:
        print(f"接続中: {args.sf_alias} ...")
        connector = connect_via_sf_cli(args.sf_alias)
    else:
        print(f"接続中: {args.username} ...")
        connector = SalesforceConnector(
            username=args.username,
            password=args.password,
            security_token=args.security_token,
            domain=args.domain,
        ).connect()
    print(f"接続OK: {connector._username}")

    # オブジェクト名解決
    objects = resolve_objects(connector.sf, args.objects)
    if not objects:
        print("[エラー] 有効なオブジェクトが指定されていません", file=sys.stderr)
        sys.exit(1)

    # バージョン管理
    prev_meta = read_meta(source_file) if source_file else None
    if prev_meta:
        current_version = increment_version(prev_meta["version"], args.version_increment)
        history         = prev_meta.get("history", [])
        field_changes   = prev_meta.get("field_changes", {}) if not is_major else {}
        old_objects     = prev_meta.get("objects", {})
        system_name     = args.system_name or prev_meta.get("system_name", "")
        original_author = prev_meta.get("original_author", "")   # 不明な場合は空（更新者で上書きしない）
        original_date   = prev_meta.get("original_date", str(date.today()))
        print(f"更新モード: {prev_meta['version']} → {current_version}" + (" (メジャー)" if is_major else ""))
    else:
        current_version = "1.0"
        history         = []
        field_changes   = {}
        old_objects     = None
        system_name     = args.system_name
        original_author = args.author
        original_date   = str(date.today())
        print("新規作成モード: v1.0")

    # メタデータ取得
    fetcher = MetadataFetcher(connector)
    sections = default_sections()
    metadata_list = []
    for obj_name in objects:
        print(f"取得中: {obj_name} ...")
        try:
            meta_obj = fetcher.fetch_all(obj_name, sections)
            metadata_list.append(meta_obj)
            print(f"  → 項目数: {len(meta_obj.get('fields', []))}")
        except Exception as e:
            print(f"  [警告] {obj_name} の取得失敗: {e}", file=sys.stderr)

    if not metadata_list:
        print("[エラー] メタデータを取得できたオブジェクトがありません", file=sys.stderr)
        sys.exit(1)

    # 差分計算
    vm    = VersionManager(args.author)
    diffs = vm.compare(old_objects, metadata_list)

    # 既存ファイルがあり、minor更新で差分ゼロなら何もしない
    if prev_meta and not is_major and not diffs:
        print("差分なし: 既存ファイルと一致しているため更新をスキップしました")
        sys.exit(0)

    if not is_major:
        for api_name, diff in diffs.items():
            # 新規オブジェクトはタブ色赤のみ。全項目赤字にしない
            if diff.get("new_object"):
                continue
            if api_name not in field_changes:
                field_changes[api_name] = {}
            for change_type in ("added", "modified", "removed"):
                for field_api in diff.get("fields", {}).get(change_type, []):
                    field_changes[api_name].setdefault(field_api, []).append({
                        "version": current_version,
                        "author":  args.author,
                        "change":  change_type,
                    })

    last_no = max((e["no"] for e in history if isinstance(e.get("no"), int)), default=0)
    entries = vm.build_entries(current_version, diffs, metadata_list,
                               start_no=last_no + 1, is_major=is_major)
    history = history + entries

    meta_payload = {
        "version":         current_version,
        "date":            str(date.today()),
        "system_name":     system_name,
        "original_author": original_author,
        "original_date":   original_date,
        "history":         history,
        "field_changes":   field_changes,
        "objects":         {m["object_api_name"]: strip_meta(m) for m in metadata_list},
    }

    # 出力
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    output_path = str(Path(args.output_dir) / f"オブジェクト項目定義書_v{current_version}.xlsx")

    writer = DefinitionWriter(
        output_path,
        system_name=system_name,
        author=args.author,
        original_author=original_author,
        original_date=original_date,
        history=history,
        current_version=current_version,
        diffs=diffs,
        field_changes=field_changes,
        old_objects=old_objects or {},
        is_major=is_major,
        meta_payload=meta_payload,
    )
    writer.write(metadata_list)

    # 旧バージョン削除
    if source_file:
        source_path = Path(source_file)
        if source_path.is_file() and str(source_path.resolve()) != str(Path(output_path).resolve()):
            try:
                source_path.unlink()
                print(f"旧ファイル削除: {source_file}")
            except OSError as e:
                print(f"旧ファイル削除失敗: {e}", file=sys.stderr)

    print(f"\n完了: {output_path}")


if __name__ == "__main__":
    main()
