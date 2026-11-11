# -*- coding: utf-8 -*-
"""backlog-xlsx / cleanup_evidence.py
証跡スクリーンショット（PNG）のうち、エビデンス.xlsx に実体埋め込み済みのものだけを削除する。

generate_evidence_xlsx.py は openpyxl の add_image() で PNG を xlsx 内部に実体埋め込みする
（外部参照ではなく複製）。ただし同スクリプトは "_before." / "_resized." を含むファイル名、
および TC 番号を正規化できないファイルを**証跡シートから除外**する（build_evidence_index /
find_evidence_files 参照）。これらは xlsx に一度も入らないため、削除すると証跡が完全に失われる
（実装前スクショ等、多くは再撮影不可能）。

**削除対象は「xlsx に実際に埋め込まれたことを検証できた PNG」のみ**。安全側に倒すため:
  - ファイル名に "_before." / "_resized." を含むものは最初から削除候補にしない
  - それでも、xlsx 内の埋め込み画像数（xl/media/ 配下）が削除候補数を下回る場合は
    「未知の除外条件があるかもしれない」とみなし、丸ごと削除を見送る（--force でも省略しない）
例外: --spec を渡し、test-spec.md にエビデンスの印（観点の末尾が「（エビデンス）」）がある場合、
次を全て満たす PNG は xlsx に貼らない機械照合用のため、埋め込みの確認なしで削除候補にする（画面の文字の
.txt は残る）。埋め込み数と比べるのはそれ以外の PNG だけ（generate_evidence_xlsx.py が貼る条件の裏返し）:
  - エビデンス以外の TC（spec にある No）の PNG
  - 同名の画面の文字（.txt）があり空でない（無い・空ならスクショが唯一の記録）
  - その PNG の回（evidence/after は judgment-result.json、evidence/after_R{n} は judgment-result.R{n}.json）で、
    その TC が NG でも AI 判定（ai_judged。スクショを読んで判定した）でもない
判定結果を読めない回（--judgment なしの --force 等）の PNG は例外にせず、従来どおり埋め込み数と比べる。
DOM テキスト（.txt）・ハイライト実績（.json）・investigation.md 等のログ本体は対象外。

安全ガード（すべて満たさない場合は削除せず理由を表示して終了する。1・4 は --force でも省略しない。
2・3 は --force で無視可＝バックフィル用途）:
  1. {issueID}_エビデンス.xlsx が存在する
  2. judgment-result.json が存在し ng == 0 かつ ai_pending == 0（全件OK。要手動・対象外は許容）
  3. エビデンス.xlsx の mtime が evidence 配下の全 PNG の最新 mtime より新しい
     （xlsx が現在の evidence 状態を反映済み＝取りこぼしがないことの確認）
  4. xlsx 内の埋め込み画像数 >= 削除候補 PNG 数（実際に格納されたことの直接検証。
     上記の例外に当たる機械照合用の PNG は数えない）

差分再実行モードへの影響: /test は前回 OK の TC を再撮影しない設計のため、削除後に /test を
再実行すると証跡ファイル不在で偽 NG になる。削除完了時に {evidence_dir}/.png-cleaned を書き込み、
次回 /test を全量再実行へ倒す（test.md Phase C 冒頭参照。マーカーは全量採取の完了後に消す）。

Usage（/test 完了報告からの案内・通常の完了後クリーンアップ）:
    python cleanup_evidence.py \\
      --folder /path/to/xlsx_folder \\
      --issue-id GF-350 \\
      --evidence-dir /path/to/docs/logs/GF-350/evidence \\
      --judgment /path/to/docs/logs/GF-350/judgment-result.json \\
      --spec /path/to/docs/logs/GF-350/test-spec.md

Usage（過去に完了した課題の一括バックフィル。judgment-result.json 不在・xlsx 生成が
古いテンプレ版等で NG/新しさガードが判定できない場合に、それらのみ無視して削除する。
埋め込み実数チェック（安全ガード4）は --force でも省略しない）:
    python cleanup_evidence.py \\
      --folder /path/to/xlsx_folder --issue-id GF-350 \\
      --evidence-dir /path/to/docs/logs/GF-350/evidence --judgment "" --force
"""

import argparse
import glob
import json
import os
import re
import sys
import zipfile

from _common import parse_test_spec, validate_folder

_EXCLUDED_MARKERS = ("_before.", "_resized.")  # generate_evidence_xlsx.py の除外条件と一致させる


def _fmt_mb(n_bytes: int) -> str:
    return f"{n_bytes / 1024 / 1024:.1f}MB"


def _tc_num(text: str) -> int:
    """"TC-004" / "TC-04" / "tc-4" → 4（generate_evidence_xlsx.py の _tc_normalize と同じ）。読めなければ -1。"""
    m = re.match(r"(?:[Tt][Cc])-0*(\d+)", text.strip())
    return int(m.group(1)) if m else -1


def _machine_only_tc_nums(spec_path: str) -> set:
    """xlsx にスクショを貼らない（機械照合用の）TC の番号。エビデンスの印が無い spec・読めない spec は空。"""
    try:
        rows = parse_test_spec(spec_path)
    except (OSError, UnicodeDecodeError):
        return set()
    is_ev = {_tc_num(r.get("No", "")): bool(re.search(r"[（(]エビデンス[）)]", r.get("観点") or "")) for r in rows}
    is_ev.pop(-1, None)
    if not any(is_ev.values()):
        return set()
    return {n for n, ev in is_ev.items() if not ev}


def _screenshot_judged_by_round(judgment_path: str) -> dict:
    """回ごとに、NG か AI 判定（ai_judged）だった TC の番号（その回の xlsx の証跡シートにスクショが貼られる）。
    キーは証跡の回のフォルダ名（今の回 = "after"・退避済み = "after_R{n}"。judgment-result.R{n}.json と対）。
    読めない回はキーに入れない（その回の PNG は埋め込みの確認の対象のまま）。"""
    if not judgment_path or not os.path.isfile(judgment_path):
        return {}
    base = os.path.splitext(judgment_path)[0]
    rounds = {"after": judgment_path}
    for path in glob.glob(glob.escape(base) + ".R*.json"):
        m = re.search(r"\.R(\d+)\.json$", path)
        if m:
            rounds[f"after_R{m.group(1)}"] = path
    by_round = {}
    for round_dir, path in rounds.items():
        try:
            with open(path, encoding="utf-8") as f:
                results = json.load(f).get("results", [])
            by_round[round_dir] = {_tc_num(r.get("no", "")) for r in results
                                   if r.get("status") == "NG" or r.get("ai_judged")}
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    return by_round


def _has_dom_text(png_path: str) -> bool:
    """PNG と同名の画面の文字（.txt）があり、空でないか。"""
    txt = os.path.splitext(png_path)[0] + ".txt"
    try:
        with open(txt, "rb") as f:
            return f.read().strip(b"\x00\r\n\t \xff\xfe") != b""
    except OSError:
        return False


def _count_embedded_images(xlsx_path: str) -> int:
    """xlsx 内に実際に埋め込まれている画像数（xl/media/ 配下のファイル数）を数える。"""
    with zipfile.ZipFile(xlsx_path) as z:
        return sum(1 for n in z.namelist() if n.startswith("xl/media/"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True, help="xlsx_folder（エビデンス.xlsx の出力先。既定 docs/logs/{issueID}）")
    ap.add_argument("--issue-id", required=True)
    ap.add_argument("--evidence-dir", required=True, help="docs/logs/{issueID}/evidence（before/after/after_R* を含む親フォルダ）")
    ap.add_argument("--judgment", default="", help="judgment-result.json のパス（最新回次）。--force 時は省略可")
    ap.add_argument("--spec", default="", help="test-spec.md のパス。エビデンス以外の TC の PNG（xlsx に貼らない機械照合用）を埋め込み確認なしで削除候補にする")
    ap.add_argument("--force", action="store_true", help="NG件数・xlsx新しさガードを無視して削除する（バックフィル用途。埋め込み実数チェックは無視しない）")
    ap.add_argument("--dry-run", action="store_true", help="削除せず対象一覧・件数のみ表示する")
    args = ap.parse_args()

    folder = validate_folder(args.folder)
    evidence_dir = args.evidence_dir
    if "{" in evidence_dir or "}" in evidence_dir:
        raise SystemExit(f"[FATAL] placeholder not resolved: {evidence_dir!r}")
    if os.path.basename(os.path.normpath(evidence_dir)) != "evidence":
        raise SystemExit(
            f"[FATAL] --evidence-dir は evidence/ ディレクトリそのものを指定してください: {evidence_dir!r}\n"
            "        （親ディレクトリ誤指定による意図しない再帰削除を防ぐためのガード）"
        )

    xlsx_path = os.path.join(folder, f"{args.issue_id}_エビデンス.xlsx")
    if not os.path.isfile(xlsx_path):
        print(f"[SKIP] エビデンス.xlsx が見つかりません: {xlsx_path}")
        print("       証跡が xlsx に格納されていることを確認できないため削除しません。")
        sys.exit(0)

    if not args.force:
        if not args.judgment or not os.path.isfile(args.judgment):
            print(f"[SKIP] judgment-result.json が見つかりません: {args.judgment!r}")
            print("       NG=0（全件OK）を確認できないため削除しません（過去分の一括削除は --force を使用）。")
            sys.exit(0)
        try:
            with open(args.judgment, encoding="utf-8") as f:
                judgment = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[SKIP] judgment-result.json の読み込みに失敗しました: {e}")
            sys.exit(0)
        ng = judgment.get("ng", -1)
        if ng != 0:
            print(f"[SKIP] NG={ng} 件が残っています。全件OKになってから実行してください（--force で無視可）。")
            sys.exit(0)
        if judgment.get("ai_pending", 0):
            print(f"[SKIP] AI判定待ちが {judgment['ai_pending']} 件残っています。/test Phase D-2 で判定してから実行してください（--force で無視可）。")
            sys.exit(0)

    if not os.path.isdir(evidence_dir):
        print(f"[INFO] evidence ディレクトリがありません: {evidence_dir}")
        sys.exit(0)

    all_png = sorted(glob.glob(os.path.join(evidence_dir, "**", "*.png"), recursive=True))
    # xlsx の証跡シートから除外される命名規則（before/resized）は最初から候補にしない。
    # 実装前スクショ等、再撮影不可能な証跡を誤って消さないための一次防御。
    excluded = [p for p in all_png if any(m in os.path.basename(p) for m in _EXCLUDED_MARKERS)]
    png_files = [p for p in all_png if p not in excluded]

    if excluded:
        print(f"[INFO] xlsx 証跡シートの対象外命名（_before./_resized.）のため {len(excluded)} 件を削除候補から除外しました（残す）。")

    if not png_files:
        print("[INFO] 削除対象の PNG はありません。")
        sys.exit(0)

    if not args.force:
        xlsx_mtime = os.path.getmtime(xlsx_path)
        newer = [p for p in png_files if os.path.getmtime(p) > xlsx_mtime]
        if newer:
            print(f"[SKIP] エビデンス.xlsx より新しい PNG が {len(newer)} 件あります。"
                  " xlsx が最新の evidence 状態を反映していない可能性があるため削除しません。")
            print("       /test を再実行して xlsx を最新化してから実行してください（--force で無視可）。")
            for p in newer[:5]:
                print(f"  - {p}")
            sys.exit(0)

    # 安全ガード4（--force でも省略しない）: xlsx に実際に埋め込まれた数を直接検証する。
    # mtime やファイル名パターンだけでは「本当に格納されたか」は保証できない
    # （Pillow 未インストール時・PIL 例外時は画像なしで xlsx が正常終了することがある）。
    try:
        embedded = _count_embedded_images(xlsx_path)
    except (zipfile.BadZipFile, OSError) as e:
        print(f"[SKIP] エビデンス.xlsx の読み込みに失敗しました: {e}")
        sys.exit(0)
    machine_nums = _machine_only_tc_nums(args.spec) if args.spec else set()
    judged_by_round = _screenshot_judged_by_round(args.judgment) if machine_nums else {}

    def _is_machine_only(p: str) -> bool:
        # 判定結果を読めない回の PNG は、NG・AI 判定で貼られたものを見分けられないので例外にしない
        round_dir = os.path.relpath(p, evidence_dir).replace("\\", "/").split("/")[0]
        num = _tc_num(os.path.basename(p).split("_")[0])
        return (round_dir in judged_by_round and num in machine_nums
                and num not in judged_by_round[round_dir] and _has_dom_text(p))

    machine_only = [p for p in png_files if _is_machine_only(p)]
    must_embed = [p for p in png_files if p not in machine_only]
    if machine_only:
        print(f"[INFO] エビデンス以外の画面テストの PNG {len(machine_only)} 件は xlsx に貼らない機械照合用のため、"
              "埋め込みの確認なしで削除候補にします（画面の文字の .txt は残します）。")
    if embedded < len(must_embed):
        print(f"[SKIP] xlsx 内の埋め込み画像は {embedded} 件、削除候補 PNG は {len(must_embed)} 件で数が一致しません。")
        print("       xlsx に格納されていない証跡が含まれる可能性があるため削除しません"
              "（Pillow 未インストール等での貼付失敗が考えられます）。")
        sys.exit(0)

    total_size = sum(os.path.getsize(p) for p in png_files)
    print(f"[INFO] 削除対象: {len(png_files)} 件 / {_fmt_mb(total_size)}（xlsx 埋め込み画像 {embedded} 件で充足確認済み）")
    print(f"       証跡は保存済みです: {xlsx_path}")

    if args.dry_run:
        print("[DRY-RUN] 実際には削除していません。")
        sys.exit(0)

    deleted = 0
    failed = 0
    for p in png_files:
        try:
            os.remove(p)
            deleted += 1
        except OSError as e:
            failed += 1
            print(f"[WARN] 削除失敗: {p} ({e})")

    deleted_size = total_size if failed == 0 else sum(
        os.path.getsize(p) for p in png_files if not os.path.exists(p)
    )
    print(f"[DONE] {deleted} 件削除（約 {_fmt_mb(deleted_size)}）。" + (f" 失敗 {failed} 件。" if failed else ""))

    # 差分再実行モード対策: 次回 /test は今回削除した分を「前回OK」として再利用できないため、
    # マーカーを残し test.md Phase C 冒頭で検知させて全量再実行に倒す（消すのは全量採取の完了後）。
    if deleted:
        marker = os.path.join(evidence_dir, ".png-cleaned")
        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write("cleanup_evidence.py により証跡PNGを削除済み。次回 /test は全量再実行してください。\n")
        except OSError as e:
            print(f"[WARN] マーカーファイルの作成に失敗しました（{marker}）: {e}")
            print("       次回 /test 実行時は手動で --full を指定してください。")


if __name__ == "__main__":
    main()
