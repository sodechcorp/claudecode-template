# -*- coding: utf-8 -*-
"""backlog-xlsx / judge_results.py
test-spec.md の期待結果と証跡ファイルの実際の結果を突き合わせ、
OK/NG を判定する（テスト・検証シートは廃止済みのため xlsx への書き戻しは行わない。証跡はエビデンス.xlsx に集約）。

Usage:
    python judge_results.py \
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

from _common import parse_test_spec


def _next_archive_round(out_path: str) -> int:
    """out_path（judgment-result.json）に対応する既存の .R{N}.json 本数から次の回次番号を返す。"""
    base = os.path.splitext(out_path)[0]
    files = glob.glob(base + ".R*.json")
    nums = [int(m.group(1)) for f in files for m in [re.search(r'\.R(\d+)\.json$', f)] if m]
    return (max(nums) if nums else 0) + 1


def _archive_previous_round(out_path: str) -> None:
    """判定結果を上書きする前に、まだ退避されていない前回の judgment-result.json を
    R{N}.json として退避する（自己防衛）。

    回次退避（前回データのアーカイブ）は Phase A では行わない設計のため（`.claude/commands/test.md` 参照）、
    判定側（judgment-result.json）の退避責務は本関数が単独で担う。会話の流れで判定だけを
    直接再実行するショートカットを踏んでも、ここで自己防衛することで判定履歴を保護する
    （証跡ディレクトリの退避は auto-evidence-runner 側が証跡採取開始前に行う）。
    """
    if not os.path.isfile(out_path):
        return
    archive_n = _next_archive_round(out_path)
    archived_json = f"{os.path.splitext(out_path)[0]}.R{archive_n}.json"
    if not os.path.isfile(archived_json):
        shutil.copy2(out_path, archived_json)
        print(f"[INFO] 回次退避（自己防衛）: {archived_json}")


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


def _tc_prefix_match(fname: str, tc_no: str) -> bool:
    """ファイル名が tc_no（大文字/小文字 TC- 両対応）で始まり、かつ直後が数字でない
    （＝ TC-1 が TC-10 等の別 TC に誤マッチしない）ことを確認する境界チェック付き前方一致。"""
    for prefix in (tc_no, tc_no.replace("TC-", "tc-")):
        if prefix and re.match(rf"^{re.escape(prefix)}(?!\d)", fname):
            return True
    return False


def find_evidence_files(evidence_dir: str, tc_no: str, shubetsu: str, allow_before: bool = False) -> list:
    """証跡ディレクトリから TC-001 に対応する全ファイルを返す（複数証跡・分岐ラベル対応）。
    allow_before=True（前後比較・Phase3 Before 参照の TC）の場合のみ、after/ に無ければ before/ を探す。
    それ以外で before/ に代替すると、操作途中で失敗し after 証跡が無い TC が操作前の画面で判定され偽 OK になる。"""
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
            if _tc_prefix_match(fname, tc_no):
                fpath = os.path.join(d, fname)
                if fpath not in seen:
                    seen.add(fpath)
                    found.append(fpath)

    # after/ で見つからない場合は sibling の before/ も検索（Before 証跡ケース: TC-016 等）
    if not found and allow_before:
        before_dir = os.path.join(os.path.dirname(os.path.abspath(evidence_dir)), "before")
        if os.path.isdir(before_dir):
            for fname in sorted(os.listdir(before_dir)):
                if "_resized." in fname:          # サムネイルは除外
                    continue
                if _tc_prefix_match(fname, tc_no):
                    fpath = os.path.join(before_dir, fname)
                    if fpath not in seen:
                        seen.add(fpath)
                        found.append(fpath)

    return found


def find_evidence_file(evidence_dir: str, tc_no: str, shubetsu: str, allow_before: bool = False) -> str:
    """後方互換: 最初の1ファイルのみ返す。"""
    files = find_evidence_files(evidence_dir, tc_no, shubetsu, allow_before)
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


def evidence_fingerprint(evidence_dir: str, tc_no: str, shubetsu: str, allow_before: bool = False):
    """TC に対応する全証跡ファイルの最終更新時刻の最大値を返す（差分再実行の stale reuse 検出用）。
    証跡ファイルが1つも無い場合は None を返す。"""
    files = find_evidence_files(evidence_dir, tc_no, shubetsu, allow_before)
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


def _kiki_match_keys(kiki: str) -> list:
    """期待結果(kiki)から実際に照合すべきキーワードを抽出する。
    「」『』で値が引用されている場合はその中身のみを照合キーとする
    （周辺の説明文「エラーメッセージ『◯◯』が表示される」等は証跡に
    逐語で出現しないため、放置すると verbose な期待結果が構造的に
    誤NGになる）。引用符が無ければ kiki 全体を単一キーとする
    （従来の逐語一致にフォールバック・後方互換）。
    """
    quoted = re.findall(r"[「『]([^」』]+)[」』]", kiki)
    return quoted if quoted else ([kiki] if kiki else [])


def _kiki_matches(kiki: str, search_scope: str) -> bool:
    """kiki の照合キー（複数なら AND）が search_scope に全て含まれるか判定する。"""
    keys = _kiki_match_keys(kiki)
    if not keys:
        return True
    scope_l = search_scope.lower()
    return all(k.lower() in scope_l for k in keys)


def _unquote(s: str) -> str:
    """照合対象の文字列から引用符（「」『』）を除去する。証跡側には引用符が出現しないため、
    残したまま照合すると否定確認は常に「なし」（偽OK）、アンカーは常に「未検出」（偽NG）になる。"""
    return re.sub(r"[「」『』]", "", s or "").strip()


def _ai_pending(reason: str, actual: str = "AI判定待ち") -> dict:
    """機械判定では信頼できる結論を出せないケース。人間の目視には回さず、/test Phase D-2 で
    AI が証跡と期待値を読んで OK/NG を確定する（apply_ai_judgment.py で反映）。"""
    return {"ok": None, "ai": True, "actual": actual, "reason": reason}


# SOQL 期待値の「項目=値」表記（例: IsLease__c=false）。soql_evidence.py の証跡は
# 「列名 | 値」の表形式のため、逐語の部分一致では照合できない。
_FIELD_PAIR_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\s*[=＝]\s*([^\s,、;；/]+)")


def _field_pairs(kiki: str) -> list:
    return [(f, _unquote(v)) for f, v in _FIELD_PAIR_RE.findall(kiki or "")]


def _parse_soql_table(scope: str):
    """soql_evidence.py の表形式（ヘッダー行 / 区切り行 / データ行）を (headers, rows) に分解する。
    表が見つからなければ None を返す。"""
    lines = (scope or "").splitlines()
    for i in range(len(lines) - 1):
        sep = lines[i + 1].strip()
        if not lines[i].strip() or not re.fullmatch(r"-+(?:-\+-+)*", sep):
            continue
        headers = [h.strip() for h in lines[i].split(" | ")]
        rows = []
        for line in lines[i + 2:]:
            if not line.strip():
                break
            cells = [c.strip() for c in line.split(" | ")]
            if len(cells) != len(headers):
                break
            rows.append(dict(zip(headers, cells)))
        return headers, rows
    return None


def _norm_val(v: str) -> str:
    v = (v or "").strip().lower()
    return "" if v in ("null", "none") else v


def _table_pair_hits(table, pairs):
    """期待値の「項目=値」を全て満たす行を返す。期待値の項目が表に無ければ None（表照合不可）。"""
    headers, rows = table
    by_lower = {h.lower(): h for h in headers}
    usable = [(by_lower[f.lower()], v) for f, v in pairs if f.lower() in by_lower]
    if not pairs or len(usable) != len(pairs):
        return None
    return [r for r in rows if all(_norm_val(r.get(h, "")) == _norm_val(v) for h, v in usable)]


def _parse_positive_anchor(kiki: str):
    """期待結果からポジティブアンカー形式（test-pattern-map.md 準拠）を抽出する。
    形式: "画面描画確認: {アンカー} が表示 / 非表示確認: {対象} が非表示"
    見つからない場合は (None, None) を返す（アンカー未指定の旧形式 spec）。
    """
    m_anchor = re.search(r"画面描画確認\s*[:：]\s*(.+?)\s*が表示", kiki)
    m_target = re.search(r"非表示確認\s*[:：]\s*(.+?)\s*が非表示", kiki)
    if m_anchor and m_target:
        return _unquote(m_anchor.group(1)), _unquote(m_target.group(1))
    return None, None


def _parse_kiki_by_shubetsu(kiki: str) -> dict:
    """期待結果が種別ラベル（UI/SOQL/AnonApex/メタ確認/ファイル確認）ごとに "/" 区切りで
    書き分けられている場合、種別→期待値の dict を返す。
    例: "UI:取引は開始されています / SOQL:3件" → {"UI": "取引は開始されています", "SOQL": "3件"}
    複合種別（例 "UI + SOQL"）の TC で証跡ごとに期待値が異なる場合に使う（test-spec-builder.md 参照）。
    セグメントが1つしかない、またはラベル形式に一致しないセグメントが混じる場合は {} を返し、
    従来どおり kiki 全文を全証跡に共通適用させる（後方互換）。
    """
    labels = "|".join(re.escape(l) for l in _SHUBETSU_SUBDIR)
    # 値に "/" を含む場合（日付 2026/07/18 等）に分割が崩れないよう、前後に空白のある " / " を
    # 優先して区切りとみなし、ラベル形式に一致しない場合のみ従来の "/" 分割を試す
    for splitter in (r"\s+/\s+", r"/"):
        segments = [s.strip() for s in re.split(splitter, kiki)]
        if len(segments) < 2:
            continue
        parsed = {}
        for seg in segments:
            m = re.match(rf"^({labels})\s*[:：]\s*(.+)$", seg)
            if not m:
                parsed = {}
                break
            parsed[m.group(1)] = m.group(2).strip()
        if parsed:
            return parsed
    return {}


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

# ログイン画面（セッション失効でリダイレクトされた場合）特有の複合マーカー（日英）。
# 単一キーワード（例:「ユーザー名」）だけで判定すると Setup の User 詳細/編集画面の
# フィールドラベルとも一致してしまうため、ログインフォーム特有の複数マーカーが
# 揃って出現した場合のみ検知する（グループ内は AND・グループ間は OR）。
# ui-evidence-runner.md 側は採取時に page.url() で URL ベースのセッション失効検知を
# 行うが、judge_results.py は保存済み DOM テキストのみを再検査する独立経路であり
# URL 情報を持たないため、DOM 内の複合マーカーで同じ事象を検知する。
_LOGIN_SCREEN_MARKER_GROUPS = [
    ["ユーザー名", "ログイン情報を保存する", "パスワードをお忘れですか"],
    ["Username", "Remember me", "Forgot Your Password"],
]


def _detect_login_screen(text: str, kiki: str) -> bool:
    """DOM/証跡テキストがログイン画面（セッション失効によるリダイレクト）である
    疑いを検知する。いずれかのマーカーグループが全て出現した場合のみ true を返す。
    期待結果(kiki)自体が該当グループを含む場合は正当なテストとみなし検知しない。"""
    if not text:
        return False
    kiki_l = (kiki or "").lower()
    text_l = text.lower()
    for group in _LOGIN_SCREEN_MARKER_GROUPS:
        if all(m.lower() in kiki_l for m in group):
            continue
        if all(m.lower() in text_l for m in group):
            return True
    return False


def _detect_sf_error(text: str, kiki: str) -> str:
    """DOM/証跡テキストに Salesforce 標準エラー画面のシグネチャが含まれるか検知する。
    期待結果(kiki)自体にそのシグネチャが含まれる場合は、エラーメッセージの表示を
    検証する正当なテスト（バリデーション/権限エラー確認等）とみなし検知しない。
    セッション失効によるログイン画面へのリダイレクトも _detect_login_screen で
    併せて検知する（URL 情報を持たないため DOM 内複合マーカーで判定）。
    見つからなければ "" を返す。"""
    if not text:
        return ""
    kiki_l = (kiki or "").lower()
    for sig in _SF_ERROR_SIGNATURES:
        if sig.lower() in kiki_l:
            continue
        if sig.lower() in text.lower():
            return sig
    if _detect_login_screen(text, kiki):
        return "セッション失効(ログイン画面へ遷移)"
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
            w, h = img.size
            img.verify()
        if w < 50 or h < 50:
            return False, f"画像サイズが異常に小さい ({w}x{h})"
        return True, f"{w}x{h}"
    except Exception as e:
        return False, f"PNGとしてデコード不可（{e}）"


def _expects_no_error(kiki: str, judge_method: str) -> bool:
    """期待結果が「例外なく完了すること」そのものである TC か。"""
    text = f"{kiki} {judge_method}"
    return any(w in text for w in ("例外なし", "エラーなし", "正常終了", "例外が発生しない", "エラーが発生しない"))


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
                    if m_snap_section and not _kiki_matches(kiki, m_snap_section.group(1)):
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
                # アンカー未指定の旧形式 spec では DOM がほぼ空白なら AI 判定に回す。
                if "含まない" in judge_method or "非表示" in judge_method or "なし確認" in judge_method:
                    anchor, neg_target = _parse_positive_anchor(kiki)
                    target_str = neg_target if neg_target else _unquote(kiki)
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
                        return _ai_pending(
                            "DOM がほぼ空白でありポジティブアンカー未指定のため、非表示確認を機械判定できません。"
                            "スクショで画面が正常に描画されているかを確認して判定してください",
                            f"AI判定待ち（DOM {visible_len}文字・空白疑い）")
                    ok = target_str.lower() not in search_scope.lower() if target_str else True
                    actual_str = f"画面表示{'OK' if ok else 'NG'}（DOM照合済）— 「{target_str[:20]}」{'なし(OK)' if ok else 'あり(NG)'}"
                    reason = "" if ok else f"「{target_str[:30]}」が DOM に残存（非表示のはずが表示されている）"
                    return {"ok": ok, "actual": actual_str, "reason": reason}
                ok = _kiki_matches(kiki, search_scope)
                actual_str = f"画面表示{'OK' if ok else 'NG'}（DOM照合済）— 「{kiki[:20]}」{'あり' if ok else 'なし'}"
                reason = "" if ok else f"DOM に「{kiki[:30]}」が含まれない（DOM照合失敗）"
                return {"ok": ok, "actual": actual_str, "reason": reason}
            return {"ok": True, "actual": "画面表示OK（DOM照合済）", "reason": ""}
        # F-1: DOM スナップショットなし → 機械照合できないため AI がスクショを読んで判定する
        return _ai_pending(
            "DOM スナップショット（.txt）が採取されていないため機械照合できません。スクショ画像を読んで期待結果が"
            "表示されているかを判定してください（ui-evidence-runner の saveText 失敗の可能性）",
            "AI判定待ち（DOM未取得・スクショのみ）")

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
                if m_exp:
                    exp = int(m_exp.group(1))
                    ok = (total >= exp) if "以上" in judge_method else (total == exp)
                    return {"ok": ok, "actual": f"SOQL {total} 件取得", "reason": "" if ok else f"期待 {exp} 件 / 実際 {total} 件"}
                if not any(k in judge_method for k in ("含む", "存在", "含まない", "非表示", "なし確認", "完全一致")):
                    return _ai_pending("SOQL 証跡に対する期待件数・照合値の指定がなく機械判定できません。"
                                       "観点と期待結果の意図に照らして取得レコードを判定してください",
                                       f"AI判定待ち（SOQL {total} 件取得・照合条件なし）")
                # 値の照合（含む/含まない/完全一致）は以降のテキスト照合に委ねる
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
            if m_actual_section and not _kiki_matches(kiki, m_actual_section.group(1)):
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
    # 期待件数の指定がない「件数一致」は仕様の不備。取得できただけで OK にすると値の誤りを見逃すため
    # AI 判定に回す（旧: 1件以上取れれば OK にしており偽 OK の原因になっていた）。
    # 期待件数なしの「完全一致」は以降の値照合（含む/完全一致の分岐）で判定する
    if not m_expected_count and m_actual_count and "件数一致" in judge_method:
        act = int(m_actual_count.group(1))
        return _ai_pending("「件数一致」だが期待結果に期待件数（N件）がありません。観点の意図に照らして取得件数・値を判定してください",
                           f"AI判定待ち（SOQL {act} 件取得・期待件数なし）")
    if m_expected_count and m_actual_count:
        exp = int(m_expected_count.group(1))
        act = int(m_actual_count.group(1))
        # F-4: 件数デフォルトは完全一致。spec に「以上」と明記した場合のみ >= に緩和
        ok = (act >= exp) if "以上" in judge_method else (exp == act)
        actual_str = f"{act} 件"
        reason = "" if ok else f"期待 {exp} 件 / 実際 {act} 件"
        return {"ok": ok, "actual": actual_str, "reason": reason}

    # 期待結果が「例外なく完了すること」そのものの匿名 Apex 証跡は、値照合より先に例外の有無で判定する
    # （値照合に回すと「例外なし」という文言自体が証跡に無いため偽 NG になる）
    if _expects_no_error(kiki, judge_method) and re.search(
            r"^成功\s*:\s*True|Executed successfully\.", content, re.MULTILINE | re.IGNORECASE):
        m_err = re.search(r"((?:FATAL_ERROR|System\.\w+Exception).{0,80})", content)
        if m_err:
            return {"ok": False, "actual": "AnonApex 実行エラー", "reason": m_err.group(1)[:80]}
        return {"ok": True, "actual": "AnonApex 実行成功（例外なし）", "reason": ""}

    # 匿名 Apex の自己検証出力（auto-evidence-runner Step 3-1: 同じ匿名 Apex 内で結果を取り直して比較した結果）は
    # 値照合より先に判定する（期待結果の文言そのものは証跡に出ないため、値照合に回すと偽 NG になる）
    m_self = re.search(r"NG項目数=(\d+)\s*/\s*(\d+)", content)
    if m_self:
        m_err = re.search(r"((?:FATAL_ERROR|System\.\w+Exception).{0,80})", content)
        if m_err:
            return {"ok": False, "actual": "AnonApex 実行エラー", "reason": m_err.group(1)[:80]}
        ng_c, total_c = int(m_self.group(1)), int(m_self.group(2))
        if ng_c == 0 and total_c > 0:
            return {"ok": True, "actual": f"AnonApex 自己検証 全{total_c}項目一致", "reason": ""}
        if total_c == 0:
            return _ai_pending("匿名 Apex の自己検証が0項目でした。期待結果に照らして実行ログを判定してください",
                               "AI判定待ち（自己検証0項目）")
        ng_lines = re.findall(r"CHECK\|([^\n]*\|NG)", content)
        detail = ng_lines[0][:80] if ng_lines else f"NG項目数={ng_c}"
        return {"ok": False, "actual": f"AnonApex 自己検証 NG {ng_c}/{total_c}項目",
                "reason": f"期待値と不一致: {detail}"}

    # F-3: 否定確認（含まない/非表示/なし確認）: 期待文字列が証跡に存在しないことを確認。
    # 証跡（実際の値セクション）自体がほぼ空（=処理が動いていない・結果が採れていない）だと
    # 対象文字列も自明に「なし」になり誤 OK になるため、アンカーまたは空白ガードで防ぐ。
    if "含まない" in judge_method or "非表示" in judge_method or "なし確認" in judge_method:
        m_actual_section = re.search(r"実際の値\s*[:：](.+?)(?=判定\s*[:：]|\Z)", content, re.DOTALL)
        search_scope = m_actual_section.group(1) if m_actual_section else content
        anchor, neg_target = _parse_positive_anchor(kiki)
        target_str = neg_target if neg_target else _unquote(kiki)
        table = _parse_soql_table(search_scope)
        neg_pairs = _field_pairs(target_str)
        if table is not None and neg_pairs:
            hits = _table_pair_hits(table, neg_pairs)
            if hits is not None:
                if anchor and anchor.lower() not in search_scope.lower():
                    return {"ok": False, "actual": "アンカー未検出のため非表示確認は判定不能",
                            "reason": f"アンカー「{anchor[:30]}」が証跡に見つからず、結果が採れていない疑い"}
                if not table[1] and not anchor:
                    return _ai_pending("SOQL 結果が0件のため「含まない」が自明に成立しています。"
                                       "クエリ条件・前提データが正しく、0件が期待どおりかを判定してください",
                                       "AI判定待ち（SOQL 0件・否定確認）")
                ok = not hits
                return {"ok": ok, "actual": f"「{target_str[:30]}」に一致する行 {len(hits)} 件",
                        "reason": "" if ok else f"「{target_str[:30]}」に一致する行が {len(hits)} 件残存"}
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
            return _ai_pending("証跡がほぼ空でありポジティブアンカー未指定のため、非表示確認を機械判定できません。"
                               "処理が実行され結果が採れているかを確認して判定してください",
                               f"AI判定待ち（証跡 {visible_len}文字・空白疑い）")
        ok = target_str.lower() not in search_scope.lower() if target_str else True
        actual_str = f"「{target_str[:30]}」{'あり（NG）' if not ok else 'なし（OK）'}"
        return {"ok": ok, "actual": actual_str,
                "reason": "" if ok else f"「{target_str[:30]}」が証跡に残存（非表示のはずが表示されている）"}

    # 含む判定 (期待結果に含まれるべき文字列): 「実際の値:」行以降のみを検索し期待値行の誤ヒットを防ぐ
    if "含む" in judge_method or "存在" in judge_method or "完全一致" in judge_method:
        m_actual_section = re.search(r"実際の値\s*[:：](.+?)(?=判定\s*[:：]|\Z)", content, re.DOTALL)
        search_scope = m_actual_section.group(1) if m_actual_section else content
        table = _parse_soql_table(search_scope)
        pos_pairs = _field_pairs(kiki)
        if table is not None and pos_pairs:
            hits = _table_pair_hits(table, pos_pairs)
            if hits is not None:
                rows = table[1]
                ok = bool(rows) and (len(hits) == len(rows) if "完全一致" in judge_method else bool(hits))
                scope_word = "全行" if "完全一致" in judge_method else "いずれかの行"
                return {"ok": ok, "actual": f"「{kiki[:30]}」一致 {len(hits)}/{len(rows)} 行",
                        "reason": "" if ok else f"{scope_word}で「{kiki[:30]}」を満たしません（一致 {len(hits)}/{len(rows)} 行）"}
        if not kiki:
            return _ai_pending("期待結果が空のため照合できません。観点の意図に照らして証跡を判定してください")
        ok = _kiki_matches(kiki, search_scope)
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
        if _expects_no_error(kiki, judge_method):
            return {"ok": True, "actual": "AnonApex 実行成功（例外なし）", "reason": ""}
        return _ai_pending("匿名 Apex は例外なく終了したが、期待結果を検証するアサーション出力（NG項目数）がありません。"
                           "実行ログの出力値が期待結果を満たすかを判定してください",
                           "AI判定待ち（AnonApex 実行成功・検証出力なし）")

    # Anonymous Apex 実行成功: "Executed successfully." を正として判定
    if re.search(r"Executed successfully\.", content, re.IGNORECASE):
        if not re.search(r"(Error:|FATAL_ERROR|System\.\w+Exception)", content):
            if _expects_no_error(kiki, judge_method):
                return {"ok": True, "actual": "AnonApex 実行成功（例外なし）", "reason": ""}
            return _ai_pending("匿名 Apex は例外なく終了したが、期待結果を検証する出力がありません。"
                               "実行ログの出力値が期待結果を満たすかを判定してください",
                               "AI判定待ち（AnonApex 実行成功・検証出力なし）")
    if re.search(r"(FATAL_ERROR|System\.\w+Exception)", content):
        m_err = re.search(r"((?:FATAL_ERROR|System\.\w+Exception).{0,80})", content)
        reason = m_err.group(1)[:80] if m_err else "AnonApex 実行エラー"
        return {"ok": False, "actual": "AnonApex 実行エラー", "reason": reason}

    # デフォルト: 判定パターン未一致 — 証跡があるだけで OK にせず、AI が期待結果と照らして判定する
    return _ai_pending("判定方法が機械照合パターンに一致しません。観点・期待結果の意図に照らして証跡を判定してください",
                       "AI判定待ち（判定パターン未一致）")


def _strip_trailing_annotation(s: str) -> str:
    """末尾の括弧書き注記（値本体とは別に書き手が添えた補足説明）を除去する。
    例: "2026-07-18（連携先データも含む）" → "2026-07-18"。
    証跡側にはこの補足説明までは出現しないため、除去しないと逐語照合が必ず
    失敗する（偽NG）。値自体が括弧を含む場合（例: "ビザ申請料実費(立替費)"）は
    除去後に残る本体部分がなお有効な照合キーとして機能するため副作用はない。
    除去後に空文字になる場合（値全体が括弧書きだった場合）は元の文字列を返す。"""
    stripped = re.sub(r"(?:\s*[（(][^（）()]*[）)])+\s*$", "", s).strip()
    return stripped if stripped else s


def _judge_transition(tc: dict, after_txts: list, evidence_dir: str) -> dict:
    """F-7: 状態遷移前後比較判定(判定方法に「前後比較」を含むケース専用)。
    before/{No}_*.txt と after/{soql|apex|screen}/{No}_*.txt を突き合わせる。
    期待結果の形式: 「before:初期値 / after:変更後値」（例: before:未送信 / after:送信済）"""
    no = tc.get("No", "")
    kiki = tc.get("期待結果", "").strip()
    # test-spec.md 生成時に LLM がバッククォート等の markdown 記法を付与すると、
    # 証跡テキスト側には出現しないため in 比較が必ず False になり偽NGを生む（C-2）。
    kiki = re.sub(r"`+", "", kiki).strip()

    # 期待結果を before: / after: で分解
    m_before_exp = re.search(r"(?:before|変更前)\s*[:：]\s*(.+?)(?:\s*/\s*(?:after|変更後)\s*[:：]|$)",
                             kiki, re.IGNORECASE)
    m_after_exp  = re.search(r"(?:after|変更後)\s*[:：]\s*(.+)", kiki, re.IGNORECASE)
    exp_before = _strip_trailing_annotation(m_before_exp.group(1).strip()) if m_before_exp else ""
    exp_after  = _strip_trailing_annotation(m_after_exp.group(1).strip())  if m_after_exp  else kiki

    # before .txt を収集（before/ ディレクトリ）
    before_dir = os.path.join(os.path.dirname(os.path.abspath(evidence_dir)), "before")
    before_txts = []
    if os.path.isdir(before_dir):
        for fname in sorted(os.listdir(before_dir)):
            if "_resized." in fname:
                continue
            if _tc_prefix_match(fname, no) and fname.lower().endswith(".txt"):
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


def _allows_before(tc: dict) -> bool:
    """before/ の証跡で判定してよい TC（前後比較・Phase3 Before 参照）か。"""
    return "前後比較" in tc.get("判定方法", "") or "Before参照" in tc.get("証跡取得", "")


def _spec_signature(tc: dict) -> str:
    """差分再実行で前回 OK を流用してよいかの判定用。期待結果・判定方法・種別が変わったら再判定する。"""
    import hashlib
    raw = "\x1f".join(tc.get(k, "").strip() for k in ("期待結果", "判定方法", "種別"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def judge_case(tc: dict, evidence_path: str, evidence_dir: str = "") -> dict:
    """1テストケースを判定し {"ok": bool, "actual": str, "reason": str} を返す。
    複数証跡（分岐ラベル付き）がある場合は全証跡を AND 評価する。"""
    no = tc.get("No", "")
    kiki = tc.get("期待結果", "").strip()
    # test-spec.md 生成時に LLM がバッククォート等の markdown 記法を付与すると、
    # 証跡テキスト側には出現しないため in 比較が必ず False になり偽NGを生む（C-2）。
    kiki = re.sub(r"`+", "", kiki).strip()
    judge_method = tc.get("判定方法", "").strip()
    auto = tc.get("自動化可否", "自動").strip()
    shubetsu = tc.get("種別", tc.get("実行種別", "")).strip()

    # 要手動ケースは判定スキップ
    if "要手動" in auto:
        return {"ok": None, "actual": "要手動確認", "reason": "自動化不可・ユーザー手動確認"}

    # 対象外ケース: spec 上は自動化対象だったが、実行時に判明した正当な理由（前提状態の消失等）で
    # 自動・手動を問わずそもそも検証手段が無いケース。「要手動」（人が後で確認すればいずれ検証
    # できる）とは異なるため NG にも SKIP（要手動確認）にも倒さず、理由付きで独立集計する。
    if "対象外" in auto:
        m_reason = re.search(r"対象外\s*[（(](.+?)[）)]", auto)
        reason = m_reason.group(1).strip() if m_reason else "理由未記載"
        return {"ok": None, "actual": f"対象外（{reason}）", "reason": reason, "status_override": "対象外"}

    # 複数証跡を収集（evidence_dir が渡されていれば全ファイルを探す）
    if evidence_dir:
        all_files = find_evidence_files(evidence_dir, no, shubetsu, _allows_before(tc))
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
            if matched is None:
                # 種別ラベルが特定できない/kiki 側に該当ラベルが無い証跡は、無関係な他種別の
                # 期待値を誤適用せず、かつ空文字フォールバックによる無条件OK化も避ける
                # （C-2: 未検証のまま偽OKになっていた）。AI 判定に回す。
                results.append(_ai_pending(
                    f"証跡 {os.path.basename(fpath)} の種別ラベルを期待結果から特定できません。"
                    "期待結果全体の意図に照らしてこの証跡を判定してください",
                    "AI判定待ち（期待値の割当なし）"))
                continue
            kiki_for_file = matched
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
        # ok: None は AI 判定待ちとして伝播（要手動は judge_case 冒頭で返すためここには来ない）
        actuals = " / ".join(r["actual"] for r in skip_results)
        reasons = " / ".join(r.get("reason", "") for r in skip_results if r.get("reason"))
        return {"ok": None, "ai": True, "actual": actuals, "reason": reasons}

    # 全件 OK
    actuals = " / ".join(r["actual"] for r in ok_results)
    return {"ok": True, "actual": actuals, "reason": ""}


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="テストケースの OK/NG 判定（対応記録.xlsx は廃止済み。証跡はエビデンス.xlsx に集約）")
    parser.add_argument("--issue-id", required=True, dest="issue_id")
    parser.add_argument("--spec", required=True, help="test-spec.md のパス")
    parser.add_argument("--evidence-dir", required=True, dest="evidence_dir",
                        help="証跡ファイルの after/ ディレクトリ")
    parser.add_argument("--out", default="", help="判定結果 JSON の出力パス（省略時は stdout）")
    parser.add_argument("--prev", default="", dest="prev_json",
                        help="前回判定 JSON（差分再実行時に前回 OK を流用する）")
    args = parser.parse_args()

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
    taigaigai_list = []
    ai_list = []

    for tc in test_cases:
        no = tc.get("No", "")
        shubetsu = tc.get("種別", tc.get("実行種別", "")).strip()
        current_fp = evidence_fingerprint(args.evidence_dir, no, shubetsu, _allows_before(tc))
        spec_sig = _spec_signature(tc)

        # 差分再実行: 前回 OK の TC は流用。ただし証跡ファイルが前回判定後に更新されている場合は
        # NG → OK の化け（stale reuse）を防ぐため流用せず再判定する。
        if no in prev_results:
            prev = prev_results[no]
            prev_fp = prev.get("evidence_mtime")
            if prev.get("spec_sig") != spec_sig:
                print(f"[RE-JUDGE] {no}: {tc.get('観点', '')} → 期待結果・判定方法が前回から変わっているため再判定します")
            elif prev_fp is not None and current_fp is not None and current_fp <= prev_fp:
                results.append(prev)
                print(f"[REUSE] {no}: {tc.get('観点', '')} → 前回OK流用 ({prev.get('actual', '')})")
                continue
            else:
                print(f"[RE-JUDGE] {no}: {tc.get('観点', '')} → 証跡ファイルが前回判定後に更新されているため再判定します")

        evidence_path = find_evidence_file(args.evidence_dir, no, shubetsu, _allows_before(tc))
        judgment = judge_case(tc, evidence_path, evidence_dir=args.evidence_dir)

        ok = judgment["ok"]
        actual = judgment["actual"]
        reason = judgment["reason"]
        ng_type = judgment.get("ng_type", "")

        if judgment.get("status_override") == "対象外":
            status = "対象外"
            taigaigai_list.append({"no": no, "label": tc.get("観点", ""), "reason": reason})
            xlsx_value = actual
        elif ok is None and judgment.get("ai"):
            status = "AI判定"
            ai_list.append({
                "no": no,
                "label": tc.get("観点", ""),
                "reason": reason,
                "expected": tc.get("期待結果", ""),
                "judge_method": tc.get("判定方法", ""),
                "shubetsu": shubetsu,
                "evidence_files": find_evidence_files(args.evidence_dir, no, shubetsu, _allows_before(tc)),
            })
            xlsx_value = "AI判定待ち"
        elif ok is None:
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
            "spec_sig": spec_sig,
        })

        # xlsx H 列更新: テスト・検証シートは廃止済みのため行わない（エビデンスはエビデンス.xlsx に集約）

        icon = {"OK": "[OK]", "NG": "[NG]", "SKIP": "[--]", "対象外": "[NA]", "AI判定": "[AI]"}[status]
        print(f"{icon} {no}: {tc.get('観点', '')} → {actual}" + (f" ({reason})" if reason else ""))

    # サマリー
    ok_count = sum(1 for r in results if r["status"] == "OK")
    ng_count = len(ng_list)
    skip_count = len(skip_list)
    taigaigai_count = len(taigaigai_list)
    ai_count = len(ai_list)
    print(f"\n判定サマリー: OK={ok_count} / NG={ng_count} / AI判定待ち={ai_count} / 要手動={skip_count} / 対象外={taigaigai_count} / 合計={len(results)}")
    if ai_count:
        print("[INFO] AI判定待ちの TC があります。/test Phase D-2 で証跡と期待結果を読んで判定し、apply_ai_judgment.py で反映してください")

    output = {
        "ok": ok_count,
        "ng": ng_count,
        "ai_pending": ai_count,
        "skip": skip_count,
        "taigaigai": taigaigai_count,
        "total": len(results),
        "ng_list": ng_list,
        "ai_list": ai_list,
        "skip_list": skip_list,
        "taigaigai_list": taigaigai_list,
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
