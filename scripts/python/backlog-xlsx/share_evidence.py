# -*- coding: utf-8 -*-
"""backlog-xlsx / share_evidence.py
/test が docs/logs/{issueID}/ に残した証跡を、チームの共有フォルダへコピーする。

対応記録.xlsx の廃止（2026-09-18）で /test の出力先は docs/logs/{issueID}/ に固定され、共有フォルダへの
保存も一緒に無くなっていた。docs/logs/ は git 管理外で本人の PC にしか残らないため、次の2つを写す:
  - {issueID}_エビデンス.xlsx（after の証跡〔スクショ・SOQL・DOM の一致行〕と過去回次は埋め込み済み）
  - evidence/before/ の中身（実装前・操作前の画面と DOM・データ。generate_evidence_xlsx.py は
    "_before." を含むファイルと after/ 以外を xlsx に入れないため、写さないと共有されない）
evidence/after/・after_R*（xlsx に埋め込み済み）と before_R*（前回の before の写し）は写さない。

保存先: docs/.backlog_config.yml の report_dir（課題フォルダの親。対応記録.xlsx のころと同じキー）配下の
  1. {issueID}_ で始まる既存フォルダ（件名が変わった課題・対応記録.xlsx を置いていたフォルダを使い回す。
     複数あれば {issueID}_{件名} と一致するもの、無ければ更新日時が新しいもの）
  2. 無ければ {issueID}_{件名}（件名は investigation.md の「- **件名**:」行。取れなければ {issueID}）
before は {課題フォルダ}/evidence/before/ に置く（対応記録.xlsx のころと同じ位置）。
共有フォルダへは上書きのみで、共有フォルダにしか無いファイルは消さない。内容が同じファイルは書き込まない。
共有フォルダのエビデンス.xlsx（ローカルと内容が違うとき）は、前回この PC から保存した版（docs/logs/{issueID}/
.share-evidence.json にハッシュと「生成したままの版か」を記録。生成したままの版のハッシュは generate_evidence_xlsx.py
が .evidence-generated.json に残す）と比べて扱いを決める:
  - 前回保存した版のままで、それが生成したままの版 → そのまま上書きする（/test の再実行だけで BK/ を増やさない。
    openpyxl の保存結果は中身が同じでも毎回変わり、前の回次は新しい xlsx に入っているため）
  - 共有フォルダだけが前回の保存の後に変わり、ローカルは前回保存した版のまま（F-1・Phase G だけのやり直し等）
    → 上書きしない（共有フォルダで手で貼ったスクショ・別の PC から保存した新しい版を古い版で戻さない）
  - それ以外（共有フォルダもローカルも変わった・前回保存した版に手が加わっていた・記録が無い／読めない）→ 上書き前の
    ものを {課題フォルダ}/BK/{issueID}_エビデンス_{YYYYMMDD_HHMMSS}.xlsx に残してから上書きする（BK/ に同じ
    内容のものが既にあれば残さない）
共有ドライブへの書き込みは確認不要（shared-folder-protection.md）。

Usage:
    python share_evidence.py --project-dir C:/path/to/project --issue-id GF-350 resolve
    python share_evidence.py --project-dir C:/path/to/project --issue-id GF-350 copy
    python share_evidence.py --project-dir C:/path/to/project --issue-id GF-350 set-report-dir --path "G:/共有ドライブ/…/04_保守課題"

resolve の出力（key=value。書き込みはしない）:
    SHARE_STATUS=ok | unset（report_dir 未設定）| missing（report_dir のフォルダが無い）
    REPORT_DIR / SHARE_FOLDER_NAME（課題フォルダ名。unset・missing でも出す）/ SHARE_FILE /
    SOURCE / SOURCE_EXISTS
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

_SUBJECT_RE = re.compile(r"^- \*\*件名\*\*:[ \t]*(\S[^\n]*?)[ \t]*$", re.MULTILINE)
_EXCLUDED_MARKERS = ("_resized.",)  # 貼付用の縮小版（元画像と同じ内容）


def _config_path(project_dir: str) -> Path:
    return Path(project_dir) / "docs" / ".backlog_config.yml"


def _load_config(project_dir: str) -> dict:
    p = _config_path(project_dir)
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise SystemExit(f"[ERROR] {p} を読めません（YAML の書式を直してください）: {e}")


def _subject_sanitized(log_dir: Path) -> str:
    invest = log_dir / "investigation.md"
    if not invest.exists():
        return ""
    m = _SUBJECT_RE.search(invest.read_text(encoding="utf-8"))
    if not m:
        return ""
    # 調査中に「→ 〜」で注記が足された件名は注記の前までを使う
    subject = m.group(1).split(" → ")[0]
    # 対応記録.xlsx のころ（xlsx-setup.md）と同じ禁則文字の置換。末尾の空白・ピリオドは Windows が落とすため除く
    return re.sub(r'[/\\:*?"<>|]', "_", subject).rstrip(". ")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _same_content(a: Path, b: Path) -> bool:
    return b.is_file() and a.stat().st_size == b.stat().st_size and _sha256(a) == _sha256(b)


def _before_files(log_dir: Path) -> list:
    before = log_dir / "evidence" / "before"
    if not before.is_dir():
        return []
    return sorted(p for p in before.rglob("*")
                  if p.is_file() and not any(m in p.name for m in _EXCLUDED_MARKERS))


def _resolve(project_dir: str, issue_id: str) -> dict:
    log_dir = Path(project_dir) / "docs" / "logs" / issue_id
    source = log_dir / f"{issue_id}_エビデンス.xlsx"
    subject = _subject_sanitized(log_dir)
    wanted = f"{issue_id}_{subject}" if subject else issue_id
    befores = _before_files(log_dir)
    info = {"status": "unset", "report_dir": "", "folder_name": wanted, "share_file": "",
            "before_files": len(befores), "writes": [], "up_to_date": False, "log_dir": log_dir,
            "xlsx_action": "", "backup_reason": "",
            "source": str(source), "source_exists": source.is_file()}
    report_dir = str(_load_config(project_dir).get("report_dir") or "").strip()
    info["report_dir"] = report_dir
    if not report_dir:
        return info
    base = Path(report_dir)
    if not base.is_dir():
        info["status"] = "missing"
        return info

    candidates = [d for d in base.iterdir()
                  if d.is_dir() and (d.name == issue_id or d.name.startswith(f"{issue_id}_"))]
    exact = [d for d in candidates if d.name == wanted]
    if exact:
        share_dir = exact[0]
    elif candidates:
        share_dir = max(candidates, key=lambda d: d.stat().st_mtime)
    else:
        share_dir = base / wanted

    share_file = share_dir / source.name
    pairs = [(source, share_file)] if info["source_exists"] else []
    before_src = log_dir / "evidence" / "before"
    pairs += [(p, share_dir / "evidence" / "before" / p.relative_to(before_src)) for p in befores]
    writes = [(s, d) for s, d in pairs if not _same_content(s, d)]
    xlsx_action, backup_reason = "", ""
    if (source, share_file) in writes and share_file.is_file():
        xlsx_action, backup_reason = _decide_overwrite(log_dir, source, share_file)
        if xlsx_action == "keep":
            writes.remove((source, share_file))
    info.update(status="ok", folder_name=share_dir.name, share_file=str(share_file), writes=writes,
                up_to_date=info["source_exists"] and not writes,
                xlsx_action=xlsx_action, backup_reason=backup_reason)
    return info


def _state_path(log_dir: Path) -> Path:
    return log_dir / ".share-evidence.json"


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _decide_overwrite(log_dir: Path, source: Path, share_file: Path):
    """ローカルと内容が違う共有フォルダのエビデンス.xlsx の扱い（overwrite / keep / backup）と退避の理由を返す。"""
    state = _load_json(_state_path(log_dir))
    # 比べるのは内容（ハッシュ）だけ。保存先のパスは見ない（課題フォルダの名前が変わっても同じ判定にする）
    base = state.get("sha256")
    if not base:
        return "backup", "前回この PC から保存した記録が無いため"
    if _sha256(share_file) == base:
        if state.get("generated") is True:
            return "overwrite", ""
        return "backup", "前回この PC から保存したのが手を加えた版だったため"
    if _sha256(source) == base:
        return "keep", ""
    return "backup", "前回この PC から保存した後に共有フォルダで変わっていたため"


def _record_copy(log_dir: Path, share_file: Path, source: Path) -> None:
    """共有フォルダのエビデンス.xlsx がローカルと同じになった時点のハッシュと、それが生成したままの版かを記録する。"""
    digest = _sha256(source)
    gen = _load_json(log_dir / ".evidence-generated.json")
    generated = gen.get("file") == source.name and gen.get("sha256") == digest
    try:
        _state_path(log_dir).write_text(
            json.dumps({"share_file": str(share_file), "sha256": digest, "generated": generated},
                       ensure_ascii=False),
            encoding="utf-8")
    except OSError as e:
        # 記録が無いと次回は上書き前に退避する（安全側）ので止めない
        print(f"[WARN] 保存の記録を書けませんでした（次回は上書き前に BK/ へ退避します）: {e}")


def _backup_share_file(share_file: Path) -> Path:
    """上書き前の共有フォルダのエビデンス.xlsx を BK/ に残し、その場所を返す。
    BK/ に同じ内容のものがあれば（上書きに失敗した回の再試行等）新しく残さず、そのファイルを返す。"""
    bk_dir = share_file.parent / "BK"
    try:
        if bk_dir.is_dir():
            for p in sorted(bk_dir.glob(f"{share_file.stem}_*{share_file.suffix}")):
                if _same_content(share_file, p):
                    return p
        bk_dir.mkdir(exist_ok=True)
        stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
        dest = bk_dir / f"{share_file.stem}_{stamp}{share_file.suffix}"
        n = 2
        while dest.exists():  # 同じ秒の退避で前の退避を上書きしない
            dest = bk_dir / f"{share_file.stem}_{stamp}_{n}{share_file.suffix}"
            n += 1
        shutil.copyfile(share_file, dest)
    except OSError as e:
        # PermissionError のまま上げると呼び出し側が「Excel で開いている可能性」と案内するため包み直す
        raise OSError(f"BK/ への退避に失敗しました: {e}") from e
    if not _same_content(share_file, dest):
        raise OSError(f"BK/ への退避後の内容が一致しません: {dest}")
    return dest


def cmd_resolve(args) -> int:
    info = _resolve(args.project_dir, args.issue_id)
    print(f"SHARE_STATUS={info['status']}")
    print(f"REPORT_DIR={info['report_dir']}")
    print(f"SHARE_FOLDER_NAME={info['folder_name']}")
    print(f"SHARE_FILE={info['share_file']}")
    print(f"SOURCE={info['source']}")
    print(f"SOURCE_EXISTS={str(info['source_exists']).lower()}")
    return 0


def cmd_copy(args) -> int:
    info = _resolve(args.project_dir, args.issue_id)
    if info["status"] == "unset":
        print(f"[ERROR] {_config_path(args.project_dir)} に report_dir がありません。set-report-dir で保存先を設定してください。")
        return 1
    if info["status"] == "missing":
        print(f"[ERROR] report_dir のフォルダが見つかりません: {info['report_dir']}（共有ドライブの再編等。set-report-dir で設定し直してください）")
        return 1
    if not info["source_exists"]:
        print(f"[ERROR] エビデンス.xlsx がありません: {info['source']}（/test Phase E で生成されます）")
        return 1

    share_file = Path(info["share_file"])
    source, log_dir = Path(info["source"]), info["log_dir"]
    kept = info["xlsx_action"] == "keep"
    kept_note = ("エビデンス.xlsx は共有フォルダの版を残しました（前回この PC から保存した後に共有フォルダで変わっていて、"
                 "ローカルは前回保存した版のままのため上書きしない）")
    if info["up_to_date"]:
        if kept:
            print(f"保存済み: {share_file}（evidence/before/ は変更なし・before 全 {info['before_files']} 件。{kept_note}）")
        else:
            _record_copy(log_dir, share_file, source)
            print(f"保存済み: {share_file}（共有フォルダの内容と同じため書き込みなし）")
        return 0
    backup = None
    try:
        share_file.parent.mkdir(exist_ok=True)  # report_dir 自体は作らない
        for src, dest in info["writes"]:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest == share_file and info["xlsx_action"] == "backup":
                backup = _backup_share_file(dest)
            shutil.copyfile(src, dest)
            if not _same_content(src, dest):
                print(f"[ERROR] コピー後の内容がローカルと一致しません: {dest}")
                return 1
    except PermissionError as e:
        print(f"[ERROR] 共有フォルダへの書き込みに失敗しました（共有フォルダのエビデンス.xlsx を Excel で開いている可能性）: {e}")
        return 1
    except OSError as e:
        print(f"[ERROR] 共有フォルダへの書き込みに失敗しました: {e}")
        return 1
    finally:
        if backup:  # 上書きに失敗した回も退避先を出す
            print(f"上書き前のエビデンス.xlsx を退避: {backup}（{info['backup_reason']}）")

    n_before = sum(1 for _, d in info["writes"] if d != share_file)
    if kept:
        print(f"保存完了: {share_file.parent}（evidence/before/ に {n_before} 件書き込み・before 全 "
              f"{info['before_files']} 件。{kept_note}）")
        return 0
    _record_copy(log_dir, share_file, source)
    print(f"保存完了: {share_file}（{share_file.stat().st_size / 1024 / 1024:.1f}MB。"
          f"evidence/before/ に {n_before} 件書き込み・before 全 {info['before_files']} 件）")
    return 0


def cmd_set_report_dir(args) -> int:
    value = (args.path or "").strip().strip('"').strip("'")
    if not value or "{" in value or "}" in value:
        print(f"[ERROR] フォルダのパスを指定してください: {value!r}")
        return 1
    p = Path(value)
    if not p.is_absolute():
        print(f"[ERROR] 絶対パスで指定してください: {value}")
        return 1
    if not p.is_dir():
        print(f"[ERROR] フォルダが見つかりません: {value}（課題フォルダの親になる既存フォルダを指定してください）")
        return 1
    # 課題フォルダ（{issueID}_件名）自体を親として登録する取り違えを止める。同じプロジェクトキーの課題に絞り、
    # 「FY-2026_保守課題」のような正しい親フォルダは拒否しない
    project_key = args.issue_id.rsplit("-", 1)[0]
    if (p.name == args.issue_id or p.name.startswith(f"{args.issue_id}_")
            or re.match(rf"^{re.escape(project_key)}-\d+(?:_|$)", p.name)):
        print(f"[ERROR] 課題フォルダが指定されています: {value}（課題フォルダではなく、その親のフォルダを指定してください）")
        return 1

    cfg_path = _config_path(args.project_dir)
    cfg = _load_config(args.project_dir)
    cfg["report_dir"] = value.replace("\\", "/")
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=10**9),
        encoding="utf-8",
    )
    print(f"report_dir を保存しました: {cfg['report_dir']}（{cfg_path}）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="エビデンス.xlsx と evidence/before/ を共有フォルダへコピーする")
    ap.add_argument("--project-dir", required=True, dest="project_dir")
    ap.add_argument("--issue-id", required=True, dest="issue_id")
    ap.add_argument("action", choices=["resolve", "copy", "set-report-dir"])
    ap.add_argument("--path", default="", help="set-report-dir で保存する report_dir（課題フォルダの親）")
    args = ap.parse_args()
    if "{" in args.project_dir or "{" in args.issue_id:
        raise SystemExit(f"[FATAL] placeholder not resolved: {args.project_dir!r} / {args.issue_id!r}")

    handler = {"resolve": cmd_resolve, "copy": cmd_copy, "set-report-dir": cmd_set_report_dir}[args.action]
    sys.exit(handler(args))


if __name__ == "__main__":
    main()
