# -*- coding: utf-8 -*-
"""backlog-xlsx / judge_results.py
test-spec.md の期待結果と証跡ファイルの実際の結果を突き合わせ、
OK/NG を判定して対応記録.xlsx の H 列（実際の結果）を更新する。

Usage:
    python judge_results.py \
      --folder /path/to/xlsx_folder \
      --issue-id GF-350 \
      --spec /path/to/test-spec.md \
      --evidence-dir /path/to/evidence/after \
      --out /path/to/judgment-result.json
"""

import argparse
import glob
import json
import os
import re
import shutil
import sys
from pathlib import Path

from _common import validate_folder


def _next_archive_round(out_path: str) -> int:
    """out_path（judgment-result.json）に対応する既存の .R{N}.json 本数から次の回次番号を返す。"""
    base = os.path.splitext(out_path)[0]
    files = glob.glob(base + ".R*.json")
    nums = [int(m.group(1)) for f in files for m in [re.search(r'\.R(\d+)\.json$', f)] if m]
    return (max(nums) if nums else 0) + 1


def _archive_previous_round(out_path: str) -> None:
    """判定結果を上書きする前に、まだ退避されていない前回の judgment-result.json を
    R{N}.json として退避する（自己防衛）。

    `/test` コマンド Phase A の回次退避は「/test がコマンドの入口から新規に再実行された場合」
    にのみ発動するため、会話の流れで判定だけを直接再実行するショートカットを踏むと発動しない。
    ここで自己防衛することで、どの経路で呼ばれても判定履歴を保護する
    （証跡ディレクトリの退避は auto-evidence-runner 側が証跡採取開始前に行う）。
    """
    if not os.path.isfile(out_path):
        return
    archive_n = _next_archive_round(out_path)
    archived_json = f"{os.path.splitext(out_path)[0]}.R{archive_n}.json"
    if not os.path.isfile(archived_json):
        shutil.copy2(out_path, archived_json)
        print(f"[INFO] 回次退避（自己防衛）: {archived_json}")


# ── test-spec.md パーサ ───────────────────────────────────────────────────────

def parse_test_spec(spec_path: str) -> list:
    """test-spec.md の "No" 列を持つテーブル（テストケース一覧）を dict リストとして返す。
    ファイル中に複数テーブルがある場合は "No" ヘッダーを含む最初のテーブルを対象にする。
    """
    text = Path(spec_path).read_text(encoding="utf-8")
    candidate_headers = []
    candidate_rows = []
    in_table = False

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if in_table:
                if "No" in candidate_headers:
                    return candidate_rows
                candidate_headers = []
                candidate_rows = []
                in_table = False
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.match(r"^[-: ]+$", c) for c in cells):
            in_table = True
            continue
        if not candidate_headers:
            candidate_headers = cells
            in_table = True
        else:
            candidate_rows.append(dict(zip(candidate_headers, cells)))

    if "No" in candidate_headers:
        return candidate_rows
    return []


# ── 証跡ファイル探索 ────────────────────────────────────────────────────────

# 種別別サブディレクトリ（複合種別 "AnonApex + SOQL" 等にも対応）
_SHUBETSU_SUBDIR = {
    "SOQL": "soql",
    "AnonApex": "apex",
    "UI": "screen",
    "メタ確認": "meta",
    "ファイル確認": "meta",
}

# サブディレクトリ → 種別ラベル群（meta は複数ラベルが乗るため list）
_SUBDIR_SHUBETSU_LABELS: dict = {}
for _label, _subdir in _SHUBETSU_SUBDIR.items():
    _SUBDIR_SHUBETSU_LABELS.setdefault(_subdir, []).append(_label)


def find_evidence_files(evidence_dir: str, tc_no: str, shubetsu: str) -> list:
    """証跡ディレクトリから TC-001 に対応する全ファイルを返す（複数証跡・分岐ラベル対応）。"""
    # " + " で分割して各サブディレクトリを収集（重複なし・順序維持）
    subdirs_ordered = []
    seen_subdirs: set = set()
    for part in re.split(r'\s*\+\s*', shubetsu):
        sd = _SHUBETSU_SUBDIR.get(part.strip(), "")
        if sd and sd not in seen_subdirs:
            seen_subdirs.add(sd)
            subdirs_ordered.append(sd)

    search_dirs = [os.path.join(evidence_dir, sd) for sd in subdirs_ordered]
    search_dirs.append(evidence_dir)

    found = []
    seen: set = set()
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            # before / リサイズ済みサムネイルは対象外
            if "_before." in fname or "_resized." in fname:
                continue
            if fname.startswith(tc_no) or fname.startswith(tc_no.replace("TC-", "tc-")):
                fpath = os.path.join(d, fname)
                if fpath not in seen:
                    seen.add(fpath)
                    found.append(fpath)

    # after/ で見つからない場合は sibling の before/ も検索（Before 証跡ケース: TC-016 等）
    if not found:
        before_dir = os.path.join(os.path.dirname(os.path.abspath(evidence_dir)), "before")
        if os.path.isdir(before_dir):
            for fname in sorted(os.listdir(before_dir)):
                if "_resized." in fname:          # サムネイルは除外
                    continue
                if fname.startswith(tc_no) or fname.startswith(tc_no.replace("TC-", "tc-")):
                    fpath = os.path.join(before_dir, fname)
                    if fpath not in seen:
                        seen.add(fpath)
                        found.append(fpath)

    return found


def find_evidence_file(evidence_dir: str, tc_no: str, shubetsu: str) -> str:
    """後方互換: 最初の1ファイルのみ返す。"""
    files = find_evidence_files(evidence_dir, tc_no, shubetsu)
    return files[0] if files else ""


def find_prefix_mismatch_files(evidence_dir: str, tc_no: str) -> list:
    """通常の prefix 一致で証跡が見つからない場合の診断用: TC- 接頭辞の有無違いで
    一致しそうなファイル（証跡採取エージェントが命名規約からズレて出力した疑い）を探す。
    tc_no='TC-001' なら '001' 始まりを、tc_no='001' なら 'TC-001' 始まりを探す。"""
    alt_prefix = tc_no[3:] if tc_no.startswith("TC-") else f"TC-{tc_no}"
    if not alt_prefix:
        return []
    found = []
    for root, _dirs, files in os.walk(evidence_dir):
        for fname in sorted(files):
            if "_before." in fname or "_resized." in fname:
                continue
            if fname.startswith(alt_prefix):
                found.append(os.path.join(root, fname))
    return found


def evidence_fingerprint(evidence_dir: str, tc_no: str, shubetsu: str):
    """TC に対応する全証跡ファイルの最終更新時刻の最大値を返す（差分再実行の stale reuse 検出用）。
    証跡ファイルが1つも無い場合は None を返す。"""
    files = find_evidence_files(evidence_dir, tc_no, shubetsu)
    if not files:
        return None
    try:
        return max(os.path.getmtime(f) for f in files)
    except OSError:
        return None


# ── 判定ロジック ─────────────────────────────────────────────────────────────

def _read_text_evidence(path: str) -> str:
    """UTF-16 LE 自動検出してテキストを読む。"""
    try:
        raw = Path(path).read_bytes()
        if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
            return raw.decode("utf-16", errors="replace")
        elif len(raw) > 1 and raw[1] == 0x00:
            return raw.decode("utf-16-le", errors="replace")
        else:
            return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


# 空撮り検出のしきい値（DOM 可視文字数）。Lightning シェルのメニュー等を含んでもこの程度は残るため、
# これを下回る場合は「画面がほぼ空白のまま撮影された」疑いとして扱う。
_BLANK_DOM_CHAR_THRESHOLD = 300


def _parse_positive_anchor(kiki: str):
    """期待結果からポジティブアンカー形式（test-pattern-map.md 準拠）を抽出する。
    形式: "画面描画確認: {アンカー} が表示 / 非表示確認: {対象} が非表示"
    見つからない場合は (None, None) を返す（アンカー未指定の旧形式 spec）。
    """
    m_anchor = re.search(r"画面描画確認\s*[:：]\s*(.+?)\s*が表示", kiki)
    m_target = re.search(r"非表示確認\s*[:：]\s*(.+?)\s*が非表示", kiki)
    if m_anchor and m_target:
        return m_anchor.group(1).strip(), m_target.group(1).strip()
    return None, None


def _parse_kiki_by_shubetsu(kiki: str) -> dict:
    """期待結果が種別ラベル（UI/SOQL/AnonApex/メタ確認/ファイル確認）ごとに "/" 区切りで
    書き分けられている場合、種別→期待値の dict を返す。
    例: "UI:取引は開始されています / SOQL:3件" → {"UI": "取引は開始されています", "SOQL": "3件"}
    複合種別（例 "UI + SOQL"）の TC で証跡ごとに期待値が異なる場合に使う（test-spec-builder.md 参照）。
    セグメントが1つしかない、またはラベル形式に一致しないセグメントが混じる場合は {} を返し、
    従来どおり kiki 全文を全証跡に共通適用させる（後方互換）。
    """
    segments = [s.strip() for s in kiki.split("/")]
    if len(segments) < 2:
        return {}
    labels = "|".join(re.escape(l) for l in _SHUBETSU_SUBDIR)
    parsed = {}
    for seg in segments:
        m = re.match(rf"^({labels})\s*[:：]\s*(.+)$", seg)
        if not m:
            return {}
        parsed[m.group(1)] = m.group(2).strip()
    return parsed


def _is_blank_dom(text: str) -> bool:
    """DOM スナップショットが空撮り（前提データ未成立等で画面がほぼ空白）の疑いがあるかを判定する。"""
    return len(re.sub(r"\s+", "", text or "")) < _BLANK_DOM_CHAR_THRESHOLD


# Salesforce 標準エラー画面のシグネチャ（日英）。撮っただけで中身を見ずに OK にするのを防ぐ最終ガード。
_SF_ERROR_SIGNATURES = [
    "問題が発生しました",
    "問題が発生しているようです",
    "is malformed",
    "関連リストはレイアウトにありません",
    "権限が不十分です",
    "Insufficient Privileges",
    "このページには到達できません",
    "URL No Longer Exists",
    "予期しないエラーが発生しました",
    "Unexpected Error",
]


def _detect_sf_error(text: str, kiki: str) -> str:
    """DOM/証跡テキストに Salesforce 標準エラー画面のシグネチャが含まれるか検知する。
    期待結果(kiki)自体にそのシグネチャが含まれる場合は、エラーメッセージの表示を
    検証する正当なテスト（バリデーション/権限エラー確認等）とみなし検知しない。
    見つからなければ "" を返す。"""
    if not text:
        return ""
    kiki_l = (kiki or "").lower()
    for sig in _SF_ERROR_SIGNATURES:
        if sig.lower() in kiki_l:
            continue
        if sig.lower() in text.lower():
            return sig
    return ""


def _validate_png(path: str) -> tuple:
    """PNGとして実際にデコード可能か検証する。

    サイズチェックのみでは、Playwright の screenshot を経由せず文字列生成だけで
    「1000バイト以上のダミーファイル」を作っても素通りしてしまう。ここで PIL に
    よる実デコードを通すことで、本物の画像データではないファイル（捏造・破損）を
    機械的に弾く（DOM内容照合と並ぶ「実際に画面操作で撮影されたか」の最終ガード）。
    """
    try:
        from PIL import Image as PILImage
    except ImportError:
        return True, "PIL未導入のため画像検証スキップ"
    try:
        with PILImage.open(path) as img:
            img.verify()
        with PILImage.open(path) as img:
            w, h = img.size
        if w < 50 or h < 50:
            return False, f"画像サイズが異常に小さい ({w}x{h})"
        return True, f"{w}x{h}"
    except Exception as e:
        return False, f"PNGとしてデコード不可（{e}）"


def judge_single_evidence(evidence_path: str, kiki: str, judge_method: str, no: str) -> dict:
    """1証跡ファイルを判定し {"ok": bool|None, "actual": str, "reason": str} を返す。"""

    # スクショ（PNG）: DOM スナップショット (.txt) があれば内容照合、なければ存在判定
    if evidence_path.lower().endswith(".png"):
        size = os.path.getsize(evidence_path)
        if size < 1000:
            return {"ok": False, "actual": f"スクショあり ({size}B・小さすぎる)", "reason": "PNG が不正に小さい"}
        png_valid, png_note = _validate_png(evidence_path)
        if not png_valid:
            return {"ok": False, "actual": f"PNG不正（{png_note}）",
                    "reason": "PNGファイルが正しい画像として開けません。Playwright の screenshot で実際に撮影されたか確認してください",
                    "ng_type": "証跡不正"}
        # 同名の .txt（DOMスナップショット）を探す
        snap_path = re.sub(r'\.png$', '.txt', evidence_path, flags=re.IGNORECASE)
        if os.path.exists(snap_path):
            snap = _read_text_evidence(snap_path)
            # Salesforce エラー画面検知（最優先・最終ガード）: 採取側の「判定: OK」や
            # 期待文字列の照合結果に関わらず、エラー画面は撮れているだけで強制 NG にする。
            sf_err = _detect_sf_error(snap, kiki)
            if sf_err:
                return {"ok": False, "actual": f"画面エラー検出（{sf_err}）",
                        "reason": f"Salesforce のエラー画面が撮影されています（「{sf_err}」を検出）。"
                                   "操作手順・前提データを見直してください",
                        "ng_type": "画面エラー"}
            # 構造化証跡「判定: OK/NG」を最優先で参照
            m_verdict = re.search(r"^判定\s*:\s*(OK|NG)", snap, re.MULTILINE)
            if m_verdict:
                ok = m_verdict.group(1) == "OK"
                m_reason = re.search(r"^判定\s*:.+?[-—]\s*(.+)$", snap, re.MULTILINE)
                reason = m_reason.group(1).strip() if m_reason else ""
                # F-5: 期待結果がある場合は「実際の値:」セクション内で追加照合（採取側OK行を盲信しない）
                if ok and kiki:
                    m_snap_section = re.search(r"実際の値\s*[:：](.+?)(?=判定\s*[:：]|\Z)", snap, re.DOTALL)
                    if m_snap_section and kiki.lower() not in m_snap_section.group(1).lower():
                        ok = False
                        reason = f"採取側はOKとしているが期待値「{kiki[:30]}」が「実際の値:」セクションに見つかりません"
                actual_str = f"画面表示{'OK' if ok else 'NG'}（DOM照合済）" + (" — " + reason[:40] if reason else "")
                return {"ok": ok, "actual": actual_str, "reason": "" if ok else reason}
            # F-2/F-3: kiki による DOM 照合（「実際の値:」セクション優先スコープ）
            if kiki or "含まない" in judge_method or "非表示" in judge_method or "なし確認" in judge_method:
                m_snap_section = re.search(r"実際の値\s*[:：](.+?)(?=判定\s*[:：]|\Z)", snap, re.DOTALL)
                search_scope = m_snap_section.group(1) if m_snap_section else snap
                # F-3: 否定確認（PNG+DOM の場合も適用）。空撮り（前提データ未成立で画面が空白のまま撮影）による
                # 誤 OK を防ぐため、ポジティブアンカー（test-pattern-map.md 準拠）があればアンカー未検出時に NG、
                # アンカー未指定の旧形式 spec では DOM がほぼ空白なら SKIP（要目視）に降格する。
                if "含まない" in judge_method or "非表示" in judge_method or "なし確認" in judge_method:
                    anchor, neg_target = _parse_positive_anchor(kiki)
                    target_str = neg_target if neg_target else kiki
                    if anchor:
                        anchor_present = anchor.lower() in search_scope.lower()
                        if not anchor_present:
                            return {"ok": False,
                                    "actual": "画面表示NG（DOM照合済）— アンカー未検出のため非表示確認は判定不能",
                                    "reason": f"画面描画確認NG: アンカー「{anchor[:30]}」が DOM に見つからず、画面が未描画/空白の疑い"}
                        ok = target_str.lower() not in search_scope.lower() if target_str else True
                        actual_str = f"画面表示{'OK' if ok else 'NG'}（DOM照合済・アンカー確認済）— 「{target_str[:20]}」{'なし(OK)' if ok else 'あり(NG)'}"
                        reason = "" if ok else f"「{target_str[:30]}」が DOM に残存（非表示のはずが表示されている）"
                        return {"ok": ok, "actual": actual_str, "reason": reason}
                    if _is_blank_dom(search_scope):
                        visible_len = len(re.sub(r"\s+", "", search_scope))
                        return {"ok": None, "actual": f"要目視確認（DOM {visible_len}文字・空白疑い）",
                                "reason": "DOM がほぼ空白でありポジティブアンカー未指定のため非表示確認の自動判定は信頼できません（要目視）。test-spec の期待結果にポジティブアンカーを追記してください"}
                    ok = target_str.lower() not in search_scope.lower() if target_str else True
                    actual_str = f"画面表示{'OK' if ok else 'NG'}（DOM照合済）— 「{target_str[:20]}」{'なし(OK)' if ok else 'あり(NG)'}"
                    reason = "" if ok else f"「{target_str[:30]}」が DOM に残存（非表示のはずが表示されている）"
                    return {"ok": ok, "actual": actual_str, "reason": reason}
                ok = kiki.lower() in search_scope.lower() if kiki else True
                actual_str = f"画面表示{'OK' if ok else 'NG'}（DOM照合済）— 「{kiki[:20]}」{'あり' if ok else 'なし'}"
                reason = "" if ok else f"DOM に「{kiki[:30]}」が含まれない（DOM照合失敗）"
                return {"ok": ok, "actual": actual_str, "reason": reason}
            return {"ok": True, "actual": "画面表示OK（DOM照合済）", "reason": ""}
        # F-1: DOM スナップショットなし → 観点の自動確認不可（要目視）。ok: None = SKIP 扱い
        return {"ok": None, "actual": "スクショ取得済（DOM未取得・要目視確認）",
                "reason": "DOM スナップショット（.txt）が採取されていません。ui-evidence-runner の return 値が .txt に Write されているか確認してください"}

    # テキスト証跡（SOQL/Apex ログ / DOM スナップショット .txt）
    content = _read_text_evidence(evidence_path)

    # Salesforce エラー画面検知（最終ガード）。UI の DOM スナップショット .txt が
    # PNG を介さず単独で判定対象になるケース（PNG なし・txt のみ）を含めてここでも検知する。
    sf_err = _detect_sf_error(content, kiki)
    if sf_err:
        return {"ok": False, "actual": f"画面エラー検出（{sf_err}）",
                "reason": f"Salesforce のエラー画面が撮影されています（「{sf_err}」を検出）。"
                           "操作手順・前提データを見直してください",
                "ng_type": "画面エラー"}

    # JSON SOQL 証跡（sf data query --json の出力）: 件数判定
    if content.strip().startswith("{"):
        try:
            json_data = json.loads(content)
            if isinstance(json_data, dict) and "result" in json_data:
                result = json_data["result"]
                total = result.get("totalSize", len(result.get("records", [])))
                m_exp = re.search(r"(\d+)\s*件", kiki)
                exp = int(m_exp.group(1)) if m_exp else 1
                ok = (total >= exp) if "以上" in judge_method else (total == exp if m_exp else total > 0)
                return {"ok": ok, "actual": f"SOQL {total} 件取得", "reason": "" if ok else f"期待 {exp} 件 / 実際 {total} 件"}
        except Exception:
            pass

    # 構造化証跡（auto-evidence-runner 生成）: 「判定: OK/NG —」行を最優先参照
    m_verdict = re.search(r"^判定\s*:\s*(OK|NG)", content, re.MULTILINE)
    if m_verdict:
        ok = m_verdict.group(1) == "OK"
        m_reason = re.search(r"^判定\s*:.+?—\s*(.+)$", content, re.MULTILINE)
        reason = m_reason.group(1).strip() if m_reason else ""
        # F-5: 期待結果がある場合は「実際の値:」セクション内で追加照合（採取側OK行を盲信しない）
        if ok and kiki:
            m_actual_section = re.search(r"実際の値\s*[:：](.+?)(?=判定\s*[:：]|\Z)", content, re.DOTALL)
            if m_actual_section and kiki.lower() not in m_actual_section.group(1).lower():
                ok = False
                reason = f"採取側はOKとしているが期待値「{kiki[:30]}」が「実際の値:」セクションに見つかりません"
        actual_str = "OK — " + reason if ok else "NG — " + reason
        return {"ok": ok, "actual": actual_str, "reason": "" if ok else reason}

    # 件数一致判定 (期待結果が "N 件" 形式)
    m_expected_count = re.search(r"(\d+)\s*件", kiki)
    m_actual_count = re.search(r"件数\s*:\s*(\d+)\s*件", content)
    # sf CLI の "Total number of records retrieved: N." 形式にも対応
    if not m_actual_count:
        m_actual_count = re.search(r"Total number of records retrieved:\s*(\d+)", content, re.IGNORECASE)
    # kiki に "N件" がなくても "完全一致" の judge_method で1件以上取得できていれば OK とみなす
    if not m_expected_count and m_actual_count and ("完全一致" in judge_method or "件数一致" in judge_method):
        act = int(m_actual_count.group(1))
        if act > 0:
            return {"ok": True, "actual": f"SOQL {act} 件取得", "reason": ""}
        return {"ok": False, "actual": "SOQL 0件", "reason": "対象レコードが見つかりません"}
    if m_expected_count and m_actual_count:
        exp = int(m_expected_count.group(1))
        act = int(m_actual_count.group(1))
        # F-4: 件数デフォルトは完全一致。spec に「以上」と明記した場合のみ >= に緩和
        ok = (act >= exp) if "以上" in judge_method else (exp == act)
        actual_str = f"{act} 件"
        reason = "" if ok else f"期待 {exp} 件 / 実際 {act} 件"
        return {"ok": ok, "actual": actual_str, "reason": reason}

    # F-3: 否定確認（含まない/非表示/なし確認）: 期待文字列が証跡に存在しないことを確認。
    # 証跡（実際の値セクション）自体がほぼ空（=処理が動いていない・結果が採れていない）だと
    # 対象文字列も自明に「なし」になり誤 OK になるため、アンカーまたは空白ガードで防ぐ。
    if "含まない" in judge_method or "非表示" in judge_method or "なし確認" in judge_method:
        m_actual_section = re.search(r"実際の値\s*[:：](.+?)(?=判定\s*[:：]|\Z)", content, re.DOTALL)
        search_scope = m_actual_section.group(1) if m_actual_section else content
        anchor, neg_target = _parse_positive_anchor(kiki)
        target_str = neg_target if neg_target else kiki
        if anchor:
            if anchor.lower() not in search_scope.lower():
                return {"ok": False, "actual": "アンカー未検出のため非表示確認は判定不能",
                        "reason": f"アンカー「{anchor[:30]}」が証跡に見つからず、結果が採れていない疑い"}
            ok = target_str.lower() not in search_scope.lower() if target_str else True
            actual_str = f"（アンカー確認済）「{target_str[:30]}」{'あり（NG）' if not ok else 'なし（OK）'}"
            return {"ok": ok, "actual": actual_str,
                    "reason": "" if ok else f"「{target_str[:30]}」が証跡に残存（非表示のはずが表示されている）"}
        if _is_blank_dom(search_scope):
            visible_len = len(re.sub(r"\s+", "", search_scope))
            return {"ok": None, "actual": f"要目視確認（証跡 {visible_len}文字・空白疑い）",
                    "reason": "証跡がほぼ空でありポジティブアンカー未指定のため非表示確認の自動判定は信頼できません（要目視）"}
        ok = target_str.lower() not in search_scope.lower() if target_str else True
        actual_str = f"「{target_str[:30]}」{'あり（NG）' if not ok else 'なし（OK）'}"
        return {"ok": ok, "actual": actual_str,
                "reason": "" if ok else f"「{target_str[:30]}」が証跡に残存（非表示のはずが表示されている）"}

    # 含む判定 (期待結果に含まれるべき文字列): 「実際の値:」行以降のみを検索し期待値行の誤ヒットを防ぐ
    if "含む" in judge_method or "存在" in judge_method:
        m_actual_section = re.search(r"実際の値\s*[:：](.+?)(?=判定\s*[:：]|\Z)", content, re.DOTALL)
        search_scope = m_actual_section.group(1) if m_actual_section else content
        ok = kiki.lower() in search_scope.lower() if kiki else True
        actual_str = f"「{kiki[:30]}」{'あり' if ok else 'なし'}"
        return {"ok": ok, "actual": actual_str, "reason": "" if ok else f"「{kiki[:30]}」が証跡に含まれない"}

    # auto-evidence-runner 独自フォーマット（成功: True + NG項目数=0 形式）
    if re.search(r"^成功\s*:\s*True", content, re.MULTILINE):
        if re.search(r"(FATAL_ERROR|System\.\w+Exception)", content):
            m_err = re.search(r"((?:FATAL_ERROR|System\.\w+Exception).{0,80})", content)
            reason = m_err.group(1)[:80] if m_err else "AnonApex 実行エラー"
            return {"ok": False, "actual": "AnonApex 実行エラー", "reason": reason}
        m_ng_zero = re.search(r"NG項目数=(\d+)\s*/\s*(\d+)\s*\(PASS\)", content)
        m_ng_fail = re.search(r"NG項目数=([1-9]\d*)\s*/\s*(\d+)", content)
        if m_ng_zero:
            return {"ok": True, "actual": f"AnonApex 実行成功 / 全{m_ng_zero.group(2)}項目確認 PASS", "reason": ""}
        if m_ng_fail:
            ng_c = int(m_ng_fail.group(1))
            return {"ok": False, "actual": f"AnonApex 実行成功 / NG項目 {ng_c}件",
                    "reason": f"NG項目数={ng_c}（一部項目が期待値と不一致）"}
        return {"ok": True, "actual": "AnonApex 実行成功", "reason": ""}

    # Anonymous Apex 実行成功: "Executed successfully." を正として判定
    if re.search(r"Executed successfully\.", content, re.IGNORECASE):
        if not re.search(r"(Error:|FATAL_ERROR|System\.\w+Exception)", content):
            return {"ok": True, "actual": "AnonApex 実行成功", "reason": ""}
    if re.search(r"(FATAL_ERROR|System\.\w+Exception)", content):
        m_err = re.search(r"((?:FATAL_ERROR|System\.\w+Exception).{0,80})", content)
        reason = m_err.group(1)[:80] if m_err else "AnonApex 実行エラー"
        return {"ok": False, "actual": "AnonApex 実行エラー", "reason": reason}

    # デフォルト: 判定パターン未一致は「要確認」（NG扱い）— 証跡があるだけで OK にしない
    return {"ok": False, "actual": "証跡あり（判定パターン未一致）",
            "reason": "判定方法を機械可読な値（含む/件数一致/完全一致/含まない/前後比較等）にしてください",
            "ng_type": "要確認"}


def _judge_transition(tc: dict, after_txts: list, evidence_dir: str) -> dict:
    """F-7: 状態遷移前後比較判定（判定方法に「前後比較」を含むケース専用）。
    before/{No}_*.txt と after/{soql|apex|screen}/{No}_*.txt を突き合わせる。
    期待結果の形式: 「before:初期値 / after:変更後値」（例: before:未送信 / after:送信済）"""
    no = tc.get("No", "")
    kiki = tc.get("期待結果", "").strip()

    # 期待結果を before: / after: で分解
    m_before_exp = re.search(r"(?:before|変更前)\s*[:：]\s*(.+?)(?:\s*/\s*(?:after|変更後)\s*[:：]|$)",
                             kiki, re.IGNORECASE)
    m_after_exp  = re.search(r"(?:after|変更後)\s*[:：]\s*(.+)", kiki, re.IGNORECASE)
    exp_before = m_before_exp.group(1).strip() if m_before_exp else ""
    exp_after  = m_after_exp.group(1).strip()  if m_after_exp  else kiki

    # before .txt を収集（before/ ディレクトリ）
    before_dir = os.path.join(os.path.dirname(os.path.abspath(evidence_dir)), "before")
    before_txts = []
    if os.path.isdir(before_dir):
        for fname in sorted(os.listdir(before_dir)):
            if "_resized." in fname:
                continue
            if (fname.startswith(no) or fname.startswith(no.replace("TC-", "tc-"))) \
                    and fname.lower().endswith(".txt"):
                before_txts.append(os.path.join(before_dir, fname))

    # after DOM .txt を確認
    after_ok = False
    after_actual = ""
    for fpath in after_txts:
        content = _read_text_evidence(fpath)
        m_sec = re.search(r"実際の値\s*[:：](.+?)(?=判定\s*[:：]|\Z)", content, re.DOTALL)
        scope = m_sec.group(1) if m_sec else content
        if exp_after and exp_after.lower() in scope.lower():
            after_ok = True
            after_actual = f"after:「{exp_after[:20]}」あり"
            break
    if not after_txts:
        after_actual = "after DOM 証跡なし"
    elif not after_ok:
        after_actual = f"after:「{exp_after[:20]}」なし"

    # before DOM .txt を確認（.txt が無い場合は PNG のみ＝参考のみ・判定は after のみで行う）
    before_ok = True
    before_actual = ""
    if before_txts and exp_before:
        before_ok = False
        for fpath in before_txts:
            content = _read_text_evidence(fpath)
            if exp_before.lower() in content.lower():
                before_ok = True
                before_actual = f"before:「{exp_before[:20]}」確認済"
                break
        if not before_ok:
            before_actual = f"before:「{exp_before[:20]}」なし"
    elif not before_txts:
        before_actual = "before DOM 未取得（PNG のみ・参考）"

    ok = after_ok and before_ok
    actual_parts = [p for p in [before_actual, after_actual] if p]
    actual = " / ".join(actual_parts) if actual_parts else "証跡不足"
    reason = ""
    if not after_ok:
        reason = f"after に「{exp_after[:30]}」が見つかりません（状態遷移が未確認）"
    elif not before_ok:
        reason = f"before に「{exp_before[:30]}」が見つかりません（初期状態が未確認）"
    return {"ok": ok, "actual": actual, "reason": reason}


def judge_case(tc: dict, evidence_path: str, evidence_dir: str = "") -> dict:
    """1テストケースを判定し {"ok": bool, "actual": str, "reason": str} を返す。
    複数証跡（分岐ラベル付き）がある場合は全証跡を AND 評価する。"""
    no = tc.get("No", "")
    kiki = tc.get("期待結果", "").strip()
    judge_method = tc.get("判定方法", "").strip()
    auto = tc.get("自動化可否", "自動").strip()
    shubetsu = tc.get("種別", tc.get("実行種別", "")).strip()

    # 要手動ケースは判定スキップ
    if "要手動" in auto:
        return {"ok": None, "actual": "要手動確認", "reason": "自動化不可・ユーザー手動確認"}

    # 複数証跡を収集（evidence_dir が渡されていれば全ファイルを探す）
    if evidence_dir:
        all_files = find_evidence_files(evidence_dir, no, shubetsu)
    elif evidence_path and os.path.exists(evidence_path):
        all_files = [evidence_path]
    else:
        all_files = []

    # .txt DOMスナップショットは PNG 判定の補助として使うため、単独では PNG のサブ証跡扱い
    # PNG の判定内で snap.txt を読むため、ここでは PNG のみを判定対象とし txt 単独は除外しない
    if not all_files:
        mismatch = find_prefix_mismatch_files(evidence_dir, no) if evidence_dir else []
        if mismatch:
            sample = os.path.basename(mismatch[0])
            return {"ok": False, "actual": "",
                    "reason": f"証跡ファイルの命名が No 列（{no}）とプレフィックス不一致の疑い（例: {sample}）。"
                               "証跡採取エージェントの命名規約（{No}_接頭辞、TC- を剥がしたり付け足したりしない）を確認してください",
                    "ng_type": "命名不一致"}
        return {"ok": False, "actual": "", "reason": f"証跡ファイルが見つかりません (No: {no})", "ng_type": "未実行"}

    # F-7: 状態遷移前後比較（before/after DOM テキストを突き合わせる）
    if "前後比較" in judge_method and evidence_dir:
        after_txts = [f for f in all_files if f.lower().endswith(".txt")]
        return _judge_transition(tc, after_txts, evidence_dir)

    # PNG は内部で同名の .txt（DOM スナップショット）を参照して判定するため、
    # そのペア txt は除外する。ただしそれ以外の txt（複合種別 "UI + SOQL" 等で
    # PNG と共存する SOQL/AnonApex 証跡）は取りこぼさず判定対象に加える
    # （旧: PNG があれば txt を丸ごと除外しており、共存する他種別の証跡が無評価のまま
    # AND 判定から漏れていた）
    png_files = [f for f in all_files if f.lower().endswith(".png")]
    txt_files = [f for f in all_files if f.lower().endswith(".txt")]
    paired_txt = {re.sub(r'\.png$', '.txt', p, flags=re.IGNORECASE) for p in png_files}
    extra_txt_files = [f for f in txt_files if f not in paired_txt]
    judge_targets = png_files + extra_txt_files

    # 複合種別で証跡ごとに期待値が異なる場合（例: "UI:xxx / SOQL:yyy"）は種別別に振り分ける。
    # 通常の単一期待結果（分岐ラベル "→" 形式含む）は {} が返り、従来どおり kiki 全文を共通適用する。
    kiki_by_shubetsu = _parse_kiki_by_shubetsu(kiki)

    results = []
    for fpath in judge_targets:
        kiki_for_file = kiki
        if kiki_by_shubetsu:
            dirname = os.path.basename(os.path.dirname(fpath))
            candidate_labels = _SUBDIR_SHUBETSU_LABELS.get(dirname, [])
            matched = next((kiki_by_shubetsu[l] for l in candidate_labels if l in kiki_by_shubetsu), None)
            # 種別ラベルが特定できない/kiki 側に該当ラベルが無い証跡は、無関係な他種別の
            # 期待値を誤適用しないよう空文字（＝判定ヘッダのみで判定）にフォールバックする
            kiki_for_file = matched if matched is not None else ""
        r = judge_single_evidence(fpath, kiki_for_file, judge_method, no)
        results.append(r)

    if not results:
        return {"ok": False, "actual": "", "reason": f"判定可能な証跡ファイルがありません (No: {no})"}

    # AND 評価: 全分岐 OK で OK（NG > SKIP > OK の優先順位）
    ng_results   = [r for r in results if r.get("ok") is False]
    skip_results = [r for r in results if r.get("ok") is None]
    ok_results   = [r for r in results if r.get("ok") is True]

    if ng_results:
        # 最初の NG の理由を採用（ng_type も伝播）
        ng = ng_results[0]
        actuals = " / ".join(r["actual"] for r in results)
        return {"ok": False, "actual": actuals, "reason": ng["reason"], "ng_type": ng.get("ng_type", "")}

    if skip_results:
        # ok: None（DOM未取得・要目視等）は SKIP として伝播
        actuals = " / ".join(r["actual"] for r in skip_results)
        return {"ok": None, "actual": actuals, "reason": skip_results[0].get("reason", "")}

    # 全件 OK
    actuals = " / ".join(r["actual"] for r in ok_results)
    return {"ok": True, "actual": actuals, "reason": ""}


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="テストケースの OK/NG 判定と xlsx H 列更新")
    parser.add_argument("--folder", required=True, help="xlsx 出力フォルダ")
    parser.add_argument("--issue-id", required=True, dest="issue_id")
    parser.add_argument("--spec", required=True, help="test-spec.md のパス")
    parser.add_argument("--evidence-dir", required=True, dest="evidence_dir",
                        help="証跡ファイルの after/ ディレクトリ")
    parser.add_argument("--out", default="", help="判定結果 JSON の出力パス（省略時は stdout）")
    parser.add_argument("--prev", default="", dest="prev_json",
                        help="前回判定 JSON（差分再実行時に前回 OK を流用する）")
    args = parser.parse_args()

    args.folder = validate_folder(args.folder)
    test_cases = parse_test_spec(args.spec)
    if not test_cases:
        print("[WARN] test-spec.md にテストケースが見つかりませんでした。")
        sys.exit(0)

    # 前回判定の読み込み（差分再実行用）
    prev_results = {}
    if args.prev_json and os.path.exists(args.prev_json):
        try:
            prev_data = json.loads(Path(args.prev_json).read_text(encoding="utf-8"))
            for r in prev_data.get("results", []):
                if r.get("status") == "OK":
                    prev_results[r["no"]] = r
            print(f"[INFO] 前回判定を読み込み: OK={len(prev_results)} 件を流用")
        except Exception as e:
            print(f"[WARN] 前回判定 JSON の読み込み失敗: {e}（全件再実行）")

    results = []
    ng_list = []
    skip_list = []

    for tc in test_cases:
        no = tc.get("No", "")
        shubetsu = tc.get("種別", tc.get("実行種別", "")).strip()
        current_fp = evidence_fingerprint(args.evidence_dir, no, shubetsu)

        # 差分再実行: 前回 OK の TC は流用。ただし証跡ファイルが前回判定後に更新されている場合は
        # NG → OK の化け（stale reuse）を防ぐため流用せず再判定する。
        if no in prev_results:
            prev = prev_results[no]
            prev_fp = prev.get("evidence_mtime")
            if prev_fp is not None and current_fp is not None and current_fp <= prev_fp:
                results.append(prev)
                print(f"[REUSE] {no}: {tc.get('観点', '')} → 前回OK流用 ({prev.get('actual', '')})")
                continue
            else:
                print(f"[RE-JUDGE] {no}: {tc.get('観点', '')} → 証跡ファイルが前回判定後に更新されているため再判定します")

        evidence_path = find_evidence_file(args.evidence_dir, no, shubetsu)
        judgment = judge_case(tc, evidence_path, evidence_dir=args.evidence_dir)

        ok = judgment["ok"]
        actual = judgment["actual"]
        reason = judgment["reason"]
        ng_type = judgment.get("ng_type", "")

        if ok is None:
            status = "SKIP"
            skip_list.append(no)
            xlsx_value = "要手動確認"
        elif ok:
            status = "OK"
            xlsx_value = f"OK"
        else:
            status = "NG"
            ng_list.append({"no": no, "label": tc.get("観点", ""), "reason": reason, "ng_type": ng_type})
            xlsx_value = f"NG: {reason}" if reason else "NG"

        results.append({
            "no": no,
            "label": tc.get("観点", ""),
            "status": status,
            "actual": actual,
            "reason": reason,
            "ng_type": ng_type if status == "NG" else "",
            "evidence": evidence_path,
            "evidence_mtime": current_fp,
        })

        # xlsx H 列更新: テスト・検証シートは廃止済みのため行わない（エビデンスはエビデンス.xlsx に集約）

        icon = {"OK": "[OK]", "NG": "[NG]", "SKIP": "[--]"}[status]
        print(f"{icon} {no}: {tc.get('観点', '')} → {actual}" + (f" ({reason})" if reason else ""))

    # サマリー
    ok_count = sum(1 for r in results if r["status"] == "OK")
    ng_count = len(ng_list)
    skip_count = len(skip_list)
    print(f"\n判定サマリー: OK={ok_count} / NG={ng_count} / 要手動={skip_count} / 合計={len(results)}")

    output = {
        "ok": ok_count,
        "ng": ng_count,
        "skip": skip_count,
        "total": len(results),
        "ng_list": ng_list,
        "skip_list": skip_list,
        "results": results,
    }

    if args.out:
        _archive_previous_round(args.out)
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] 判定結果を保存: {args.out}")
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))

    # NG があれば exit 1
    if ng_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
