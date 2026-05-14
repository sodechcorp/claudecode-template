# -*- coding: utf-8 -*-
"""
backlog-xlsx / update_records.py
対応記録.xlsx を更新するスクリプト

Usage (タイムライン行を追加):
    python update_records.py --folder FOLDER --issue-id ID timeline \
      --phase "調査" --source "Claude" --content "〇〇を調査: 原因は△△"

Usage (セルを直接更新):
    python update_records.py --folder FOLDER --issue-id ID cell \
      --sheet "対応方針" --row 10 --col 1 --value "採用理由の説明"

Usage (チェックリスト更新):
    python update_records.py --folder FOLDER --issue-id ID checklist \
      --sheet "対応内容" --section "影響確認チェックリスト" --indices "1,2,3"

Usage (バックアップ情報):
    python update_records.py --folder FOLDER --issue-id ID backup-info \
      --git-hash abc1234 --stash "backlog-GF-340" --rollback "git revert abc1234"

Usage (Before/After 追記):
    python update_records.py --folder FOLDER --issue-id ID before-after \
      --file "force-app/.../X.cls" --before "変更前コード" --after "変更後コード"
"""

import argparse
import copy
import datetime
import os
import re
import sys

from _common import validate_folder, _stripe_fill

try:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
except ImportError:
    print("[ERROR] openpyxl がインストールされていません。`pip install openpyxl` を実行してください。")
    sys.exit(1)

WRAP = Alignment(wrap_text=True, vertical="top")


def find_next_empty_row(ws, col=1, start_row=1):
    """指定列で最初の空行を返す（start_row から下方向に検索）"""
    r = start_row
    while ws.cell(row=r, column=col).value is not None:
        r += 1
    return r


def find_header_row(ws, keywords, start_row=1):
    """キーワードをいずれか含む最初の行番号を返す。見つからなければ None。"""
    for row in ws.iter_rows(min_row=start_row):
        for cell in row:
            if cell.value and any(kw in str(cell.value) for kw in keywords):
                return cell.row
    return None


def find_label_row(ws, label, col=1, start_row=1):
    """col 列で label に部分一致する行を返す。"""
    for r in range(start_row, ws.max_row + 1):
        v = ws.cell(r, col).value
        if v and label in str(v).strip():
            return r
    return None


def _copy_font(src_font):
    """フォントオブジェクトを独立コピーして返す。"""
    return Font(
        name=src_font.name or "游ゴシック",
        size=src_font.size or 10,
        bold=src_font.bold,
        italic=src_font.italic,
        underline=src_font.underline,
        color=copy.copy(src_font.color) if src_font.color else None,
    )


def cmd_timeline(args, wb):
    """サマリー・経緯シートのタイムラインに1行追加する"""
    sheet_name = "サマリー・経緯"
    if sheet_name not in wb.sheetnames:
        print(f"[ERROR] シート '{sheet_name}' が見つかりません。")
        sys.exit(1)
    ws = wb[sheet_name]

    # タイムラインセクションヘッダーを検索（判断保留事項の "No" と区別するため）
    tl_section_row = find_header_row(ws, ("■ 対応経緯タイムライン",))
    if tl_section_row is None:
        print("[ERROR] タイムラインセクション（■ 対応経緯タイムライン）が見つかりません。")
        sys.exit(1)

    # 列ヘッダー行（No / 日時 / 担当 / フェーズ / 内容 / 理由）
    col_header_row = tl_section_row + 1
    data_start = col_header_row + 1

    # 既存の最大 No 値を取得（位置ベースではなく実 No ベース）
    max_no = 0
    for r in range(data_start, ws.max_row + 2):
        v = ws.cell(r, 1).value
        if isinstance(v, int) and v > 0:
            max_no = max(max_no, v)
        elif isinstance(v, str) and v.strip().isdigit():
            max_no = max(max_no, int(v.strip()))
    no = max_no + 1

    # 次の空行を取得
    next_row = find_next_empty_row(ws, col=1, start_row=data_start)

    # 重複検出: 直前の非空行と phase + content が一致する場合はスキップ
    if not getattr(args, "force", False):
        for r in range(next_row - 1, data_start - 1, -1):
            if ws.cell(r, 1).value is not None:
                existing_phase = str(ws.cell(r, 4).value or "").strip()
                existing_content = str(ws.cell(r, 5).value or "").strip()
                if existing_phase == str(args.phase).strip() and existing_content == str(args.content).strip():
                    print(f"[SKIP] 重複: phase={args.phase}, content={args.content[:30]}... （--force で強制追記）")
                    return
                break

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    fill = _stripe_fill(no - 1)

    # データ開始行からフォントを継承
    src_font = ws.cell(data_start, 1).font
    row_font = _copy_font(src_font)

    for col, value in enumerate([no, now, args.source, args.phase, args.content, args.reason or ""], start=1):
        cell = ws.cell(row=next_row, column=col, value=value)
        cell.alignment = WRAP
        cell.fill = fill
        cell.font = row_font

    print(f"タイムライン追加: No={no} / 行{next_row} / {now} / {args.phase} / {args.content[:30]}...")


def cmd_cell(args, wb):
    """指定したシート・行・列のセルを更新する"""
    if args.sheet not in wb.sheetnames:
        print(f"[ERROR] シート '{args.sheet}' が見つかりません。利用可能: {wb.sheetnames}")
        sys.exit(1)
    ws = wb[args.sheet]
    cell = ws.cell(row=args.row, column=args.col)
    if cell.value and not getattr(args, "force", False):
        print(f"[WARN] 既存値あり: {cell.value!r} → --force を指定しないと上書きしません")
        return
    cell.value = args.value
    cell.alignment = WRAP
    print(f"セル更新: {args.sheet}!({args.row},{args.col}) = {str(args.value)[:40]}...")


def cmd_checklist(args, wb):
    """指定セクションのチェックリスト(☐)を☑に変更する"""
    if args.sheet not in wb.sheetnames:
        print(f"[ERROR] シート '{args.sheet}' が見つかりません。")
        sys.exit(1)
    ws = wb[args.sheet]

    section_row = find_header_row(ws, (args.section,))
    if section_row is None:
        print(f"[ERROR] セクション '{args.section}' が見つかりません。")
        sys.exit(1)

    indices = set()
    for s in args.indices.split(","):
        s = s.strip()
        if s.isdigit():
            indices.add(int(s))

    # セクションヘッダー以降でチェックボックス行を走査
    check_rows = []
    for r in range(section_row + 1, ws.max_row + 1):
        v = str(ws.cell(r, 1).value or "").strip()
        if v in ("☐", "☑"):
            check_rows.append(r)
        elif v.startswith("■") and r > section_row + 1:
            break  # 次のセクションへ

    updated = 0
    for i, row in enumerate(check_rows, start=1):
        if i in indices:
            current = str(ws.cell(row, 1).value or "").strip()
            if current == "☐" or getattr(args, "force", False):
                ws.cell(row, 1).value = "☑"
                updated += 1
            else:
                print(f"[SKIP] 行{row}: 既に '{current}'")

    print(f"[OK] {args.section}: {updated}/{len(indices)} 件を☑に更新しました")


def cmd_backup_info(args, wb):
    """対応内容シートのバックアップ情報（Git hash / stash名 / 巻き戻し方法）を書き込む"""
    sheet_name = "対応内容"
    if sheet_name not in wb.sheetnames:
        print(f"[ERROR] シート '{sheet_name}' が見つかりません。")
        sys.exit(1)
    ws = wb[sheet_name]

    label_map = {
        "Git hash": args.git_hash,
        "stash": args.stash,
        "巻き戻し": args.rollback,
    }

    written = 0
    for label, value in label_map.items():
        row = find_label_row(ws, label)
        if row is None:
            print(f"[WARN] '{label}' ラベル行が見つかりません（スキップ）")
            continue
        cell = ws.cell(row, 2)
        if cell.value and not getattr(args, "force", False):
            print(f"[SKIP] 行{row} '{label}': 既存値あり → --force で上書き")
            continue
        cell.value = value
        cell.alignment = WRAP
        written += 1
        print(f"[OK] 行{row} '{label}' → {str(value)[:40]}")

    print(f"[OK] バックアップ情報: {written}/{len(label_map)} 件書き込みました")


def cmd_before_after(args, wb):
    """対応内容シートの Before/After セクションにファイルの変更前後を追記する"""
    sheet_name = "対応内容"
    if sheet_name not in wb.sheetnames:
        print(f"[ERROR] シート '{sheet_name}' が見つかりません。")
        sys.exit(1)
    ws = wb[sheet_name]

    ba_header = find_header_row(ws, ("■ Before / After", "Before / After"))
    if ba_header is None:
        print("[ERROR] ■ Before / After セクションが見つかりません。")
        sys.exit(1)

    # Before/After セクションの次の空行を探す
    next_row = find_next_empty_row(ws, col=1, start_row=ba_header + 1)

    def _write_cell_1(row, text, bold=False):
        """テンプレートの A:D マージ行にも対応した col 1 書き込み。"""
        c = ws.cell(row, 1, value=text)
        c.alignment = WRAP
        c.font = Font(name="游ゴシック", size=10, bold=bold)

    # ファイル名行 / Before行 / After行 をすべて col 1 に書き込む
    # （テンプレートの Before/After 行は A:D マージ済みのため col 2 以降は MergedCell）
    _write_cell_1(next_row,     f"【{args.file}】",        bold=True)
    _write_cell_1(next_row + 1, f"Before: {args.before}",  bold=False)
    _write_cell_1(next_row + 2, f"After:  {args.after}",   bold=False)

    print(f"[OK] Before/After 追記: 行{next_row}〜{next_row + 2} / {args.file}")




def _extract_validation_summary(text):
    """validation-report.md から実装前検証の概要サマリー文字列を抽出する。"""
    trivial_match = re.search(r"自明ケース判定[:：]\s*該当[（(]([^）)]+)[）)]?", text)
    if trivial_match:
        return f"実装前確認済み（自明ケース: {trivial_match.group(1).strip()[:40]}）"

    step_results = {}
    for step_num in range(1, 5):
        step_match = re.search(
            rf"#{2,3}\s+Step\s+{step_num}[：:\s].*?\n(.*?)(?=\n#{2,3}\s+|\Z)",
            text, re.DOTALL
        )
        if step_match:
            body = step_match.group(1)
            if re.search(r"skip|スキップ", body, re.IGNORECASE):
                step_results[step_num] = "SKIP"
            elif re.search(r"\bNG\b|要修正|問題あり|要戻り", body, re.IGNORECASE):
                step_results[step_num] = "NG"
            else:
                step_results[step_num] = "OK"

    if step_results:
        ng_steps = [str(k) for k, v in step_results.items() if v == "NG"]
        skip_steps = [str(k) for k, v in step_results.items() if v == "SKIP"]
        ok_steps = [str(k) for k, v in step_results.items() if v == "OK"]
        parts = []
        if ok_steps:
            parts.append(f"OK: Step{','.join(ok_steps)}")
        if skip_steps:
            parts.append(f"SKIP: Step{','.join(skip_steps)}")
        if ng_steps:
            parts.append(f"NG: Step{','.join(ng_steps)}")
        return "実装前確認済み（" + " / ".join(parts) + "）"

    verdict_match = re.search(r"#{2,3}\s+総合判定\n+\*+([^\n*]+)\*+", text)
    if verdict_match:
        return f"実装前確認済み: {verdict_match.group(1).strip()}"

    return "実装前確認済み（validation-report.md 参照）"


def cmd_test_precheck(args, wb):
    """validation-report.md の確認結果をテスト・検証シートの「実装前」行に反映する。"""
    sheet_name = "テスト・検証"
    if sheet_name not in wb.sheetnames:
        # 旧名称にフォールバック（移行期対応）
        if "テスト・検証記録" in wb.sheetnames:
            sheet_name = "テスト・検証記録"
        else:
            print(f"[ERROR] シート '{sheet_name}' が見つかりません。")
            sys.exit(1)

    if not os.path.exists(args.report):
        print(f"[ERROR] validation-report.md が見つかりません: {args.report}")
        sys.exit(1)

    with open(args.report, encoding="utf-8") as f:
        validation_text = f.read()

    summary = _extract_validation_summary(validation_text)
    ws = wb[sheet_name]

    header_row = None
    for row in ws.iter_rows(min_row=1, max_row=30):
        for cell in row:
            if cell.value == "No":
                next_cell = ws.cell(cell.row, cell.column + 1)
                if next_cell.value in ("タイミング", "区分", "確認観点"):
                    header_row = cell.row
                    break
        if header_row:
            break

    if not header_row:
        print("[WARN] テスト・検証シートのヘッダー行が見つかりませんでした。")
        return

    max_rows = getattr(args, "max_rows", 1000)
    updated = 0
    for r in range(header_row + 1, header_row + max_rows + 1):
        no_val = ws.cell(r, 1).value
        timing_val = ws.cell(r, 2).value
        if no_val is None and timing_val is None:
            break
        if str(timing_val or "").strip() == "実装前":
            result_cell = ws.cell(r, 6)
            verdict_cell = ws.cell(r, 7)
            if not result_cell.value or getattr(args, "force", False):
                result_cell.value = summary
                result_cell.alignment = WRAP
                fill = _stripe_fill(updated)
                result_cell.fill = fill
            if not verdict_cell.value or getattr(args, "force", False):
                verdict_cell.value = "OK"
                verdict_cell.alignment = WRAP
            updated += 1

    print(f"[OK] 実装前テスト行 {updated} 件に validation-report.md の結果を反映しました")


def cmd_pending(args, wb):
    """残対応・懸念・保留シートに1行追加する。"""
    sheet_name = "残対応・懸念・保留"
    if sheet_name not in wb.sheetnames:
        print(f"[ERROR] シート '{sheet_name}' が見つかりません。")
        sys.exit(1)
    ws = wb[sheet_name]

    # ■ 残対応・懸念事項一覧 のデータ開始行を動的特定
    data_start = None
    for row in ws.iter_rows(min_col=1, max_col=1):
        cell = row[0]
        if cell.value and "■ 残対応" in str(cell.value):
            data_start = cell.row + 2  # ヘッダー行 + 列ヘッダ行
            break
    if data_start is None:
        data_start = 4  # fallback

    # 最終 No を特定して次の行番号を決める
    last_row = data_start
    max_no = 0
    for r in range(data_start, ws.max_row + 1):
        val = ws.cell(r, 1).value
        if val is None and ws.cell(r, 2).value is None:
            break
        last_row = r
        try:
            no = int(str(val or "").strip())
            if no > max_no:
                max_no = no
        except ValueError:
            pass

    # 重複チェック: 同じ内容が既に存在するか
    if not getattr(args, "force", False):
        for r in range(data_start, last_row + 1):
            existing = ws.cell(r, 3).value
            if existing and str(existing).strip() == str(args.content).strip():
                print(f"[SKIP] 同じ内容が既に存在します (r{r}): {args.content[:40]}")
                return

    new_row = last_row + 1
    new_no = max_no + 1
    fill = _stripe_fill(new_no - 1)
    ws.cell(new_row, 1, value=new_no).alignment = WRAP
    ws.cell(new_row, 2, value=args.kind).alignment = WRAP
    ws.cell(new_row, 3, value=args.content).alignment = WRAP
    ws.cell(new_row, 4, value=getattr(args, "related", "") or "").alignment = WRAP
    ws.cell(new_row, 5, value=args.status).alignment = WRAP
    ws.cell(new_row, 6, value=getattr(args, "next_action", "") or "").alignment = WRAP
    for col in range(1, 7):
        c = ws.cell(new_row, col)
        c.fill = fill

    print(f"[OK] 残対応・懸念・保留 r{new_row} に追記: [{args.kind}] {args.content[:40]}")


TIMELINE_PHASES = ["調査", "対応方針", "実装方針", "実装前検証", "実装", "テスト", "最終検証", "リリース", "お客様確認"]


def main():
    parser = argparse.ArgumentParser(description="対応記録.xlsx を更新する")
    parser.add_argument("--folder",   required=True, help="保存先フォルダパス")
    parser.add_argument("--issue-id", required=True, dest="issue_id", help="課題ID (例: GF-327)")

    sub = parser.add_subparsers(dest="command", required=True)

    # タイムライン追加
    p_tl = sub.add_parser("timeline", help="タイムラインに行を追加する")
    p_tl.add_argument("--phase",   required=True, choices=TIMELINE_PHASES,
                      help="フェーズ名（固定値: " + "/".join(TIMELINE_PHASES) + "）")
    p_tl.add_argument("--source",  default="Claude", help="発生元 (例: Claude, ユーザ)")
    p_tl.add_argument("--content", required=True, help="内容・決定事項")
    p_tl.add_argument("--reason",  default="", help="変更・判断の理由（任意）")
    p_tl.add_argument("--force",   action="store_true", help="重複・既存値があっても上書きする")

    # セル直接更新
    p_cell = sub.add_parser("cell", help="特定セルを直接更新する")
    p_cell.add_argument("--sheet", required=True, help="シート名")
    p_cell.add_argument("--row",   required=True, type=int, help="行番号")
    p_cell.add_argument("--col",   required=True, type=int, help="列番号")
    p_cell.add_argument("--value", required=True, help="書き込む値")
    p_cell.add_argument("--force", action="store_true", help="既存値があっても上書きする")

    # テスト実装前結果反映
    p_precheck = sub.add_parser("test-precheck", help="validation-report.md の実装前確認結果をテスト行に反映する")
    p_precheck.add_argument("--report",    required=True, help="validation-report.md のパス")
    p_precheck.add_argument("--max-rows",  type=int, default=1000, dest="max_rows",
                            help="ヘッダー行から走査する最大行数（デフォルト: 1000）")
    p_precheck.add_argument("--force",     action="store_true", help="既存値があっても上書きする")

    # チェックリスト更新
    p_cl = sub.add_parser("checklist", help="チェックリスト(☐)を☑に変更する")
    p_cl.add_argument("--sheet",   required=True, help="シート名")
    p_cl.add_argument("--section", required=True, help="セクション見出し（部分一致）")
    p_cl.add_argument("--indices", required=True, help="1-base 番号をカンマ区切りで (例: '1,2,3')")
    p_cl.add_argument("--force",   action="store_true", help="既に☑の行も対象にする")

    # バックアップ情報
    p_bi = sub.add_parser("backup-info", help="対応内容シートにバックアップ情報を書き込む")
    p_bi.add_argument("--git-hash", required=True, dest="git_hash", help="Git commit hash (例: abc1234)")
    p_bi.add_argument("--stash",    required=True, help="git stash 名 (例: backlog-GF-340)")
    p_bi.add_argument("--rollback", required=True, help="巻き戻し方法 (例: git revert abc1234)")
    p_bi.add_argument("--force",    action="store_true", help="既存値があっても上書きする")

    # Before/After 追記
    p_ba = sub.add_parser("before-after", help="対応内容シートの Before/After セクションに変更前後を追記する")
    p_ba.add_argument("--file",   required=True, help="ファイルパス")
    p_ba.add_argument("--before", required=True, help="変更前コード / 設定値")
    p_ba.add_argument("--after",  required=True, help="変更後コード / 設定値")
    p_ba.add_argument("--force",  action="store_true")

    # 残対応・懸念・保留 追記
    p_pd = sub.add_parser("pending", help="残対応・懸念・保留シートに1行追加する")
    p_pd.add_argument("--kind",        required=True,
                      choices=["懸念", "許容した影響", "後回しの残対応", "保留", "次課題提案"],
                      help="種別")
    p_pd.add_argument("--content",     required=True, help="内容")
    p_pd.add_argument("--status",      required=True,
                      choices=["未対応", "許容済", "保留", "提案", "完了"],
                      help="ステータス")
    p_pd.add_argument("--next-action", default="", dest="next_action", help="次アクション（任意）")
    p_pd.add_argument("--related",     default="", help="関連（Q番号・課題ID等、任意）")
    p_pd.add_argument("--force",       action="store_true", help="重複内容があっても追加する")

    args = parser.parse_args()
    args.folder = validate_folder(args.folder)

    xlsx_path = os.path.join(args.folder, f"{args.issue_id}_対応記録.xlsx")
    if not os.path.exists(xlsx_path):
        print(f"[ERROR] ファイルが見つかりません: {xlsx_path}")
        sys.exit(1)

    try:
        wb = openpyxl.load_workbook(xlsx_path)
    except Exception as e:
        print(f"[ERROR] xlsx の読み込みに失敗しました: {xlsx_path}\n{e}")
        sys.exit(1)

    if args.command == "timeline":
        cmd_timeline(args, wb)
    elif args.command == "cell":
        cmd_cell(args, wb)
    elif args.command == "test-precheck":
        cmd_test_precheck(args, wb)
    elif args.command == "checklist":
        cmd_checklist(args, wb)
    elif args.command == "backup-info":
        cmd_backup_info(args, wb)
    elif args.command == "before-after":
        cmd_before_after(args, wb)
    elif args.command == "pending":
        cmd_pending(args, wb)

    try:
        wb.save(xlsx_path)
    except PermissionError as e:
        print(f"[ERROR] xlsx の保存に失敗しました（ファイルが開かれている可能性があります）: {xlsx_path}\n{e}")
        sys.exit(1)
    print(f"保存完了: {xlsx_path}")


if __name__ == "__main__":
    main()
