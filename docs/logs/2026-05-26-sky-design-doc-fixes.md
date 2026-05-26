# 設計書品質問題 — Sky プロジェクト顕在化対応ログ

**日付**: 2026-05-26  
**対象リポジトリ**: claudecode-template（C:\workspace\claude-temp）  
**起因**: Sky プロジェクト（sky_prod）で詳細設計書・概要書の品質問題が突然発生。GF 他プロジェクトでは問題なかった。

---

## Sky で顕在化した理由（調査で確定）

同じ `/sf-memory` コマンドで生成した `docs/` ファイルが、プロジェクトによって形式が異なる:

| ファイル | GF（成功） | Sky（問題発生） | 差の原因 |
|---|---|---|---|
| `docs/flow/swimlanes.json` | name ベース（`lane: "営業事務"`） | id ベース（`lane: "asis_customer"`） | sf-analyst-cat1 の出力形式が sf-org-analyst 実行時のフロー解析結果によって変わる |
| `docs/overview/org-profile.md` 用語集 | 3列（業務用語/SF対応/説明） | 2列（用語/意味） | Sky の用語集は SF 対応列なし（業務ドメインの違い） |
| `force-app/main/default/aura/` | 1件（FilePreview・ほぼ空） | 14件（skyBookingCalendar 等） | Sky は Aura 主体のコンポーネント構成 |

いずれも「データ側のバリエーション」が「コード側の固定前提」を踏んだもので、コードのバグではなくエッジケース非対応。

---

## 修正一覧

### コミット `de87b63`（2026-05-26 以前に適用済み）

| 問題 | 対応ファイル | 変更内容 |
|---|---|---|
| ⑦ swimlane 1箱 | `generate_basic_doc.py` — `_normalize_flow` | lane の id→name 解決マップを構築（id なし構造の GF とも後方互換） |
| ⑧ 用語集説明欄空白 | `generate_basic_doc.py` — `parse_org` | ヘッダー行スキャンで 2列/3列 を自動判定（GF の3列はヘッダー行の「Salesforceオブジェクト」で検出） |
| ⑨ Aura 画面項目空白 | `generate_detail_design.py` — `_parse_aura_fields` + glob | Aura `.cmp` スキャンを追加（`aura_dir.exists()` ガードで GF に no-op） |

加えて ①③（業務フロー1ノード・"処理を担当する" プレースホルダー）の検出用 WARNING を generate_detail_design.py の fallback 発火箇所に追加済み（L3022-3026, L2265-2274）。

### 本コミット（2026-05-26）— テンプレート/エージェント定義のみ変更

| 問題 | 対応ファイル | 変更内容 |
|---|---|---|
| ①③ 抑止 | `templates/sf-detail-design-writer/json-format.md` | `business_flow[]` セクション冒頭に空提出の副作用（「処理を起動する」1ノード化）を明示 |
| ①③ 抑止 | `templates/sf-detail-design-writer/quality-rules.md` | `responsibility` 空文字許可を標準 VF ボイラープレートのみに限定。空提出の副作用（「処理を担当する」機械挿入）を明示 |
| ①③ 抑止 | `templates/sf-detail-design-writer/json-checklist.md` | Phase 3 に `responsibility` 空文字率 50% 超チェックを追加 |
| ⑩ FG ループ途中終了 | `agents/sf-detail-design-writer.md` | Phase 0.3「グループリストの確定（ループ制御）」セクションを追加。1 グループずつ完遂・`{group_id}` 実値置換を明示 |

---

## 既存影響なし確認（GF 後方互換）

**GF データとの互換性検証結果**:

- `_normalize_flow`: GF の name ベース swimlanes では `lane_resolve[name]=name` のみ登録され、`lane_resolve.get(lane_raw, lane_raw)` のフォールバックで `lane_raw=name` がそのまま返る。GF 動作に変化なし。
- `parse_org` 用語集: GF の3列構成はヘッダー行「Salesforceオブジェクト」を検出して `sf_col=1,desc_col=2` が維持される。2列扱いに変わらない。
- `_parse_aura_fields` + glob: GF の Aura ディレクトリには FilePreview のみ（.cmp なし）で実質 no-op。
- テンプレート規定強化: 追加ルールはすべて「空提出パターンを検出して書き直させる」方向。GF のように正しく書けていたケースには発火しない。

**GF Excel Grep 結果**: `C:/work/01_作業/グリーンフィールド/02_詳細設計/` 配下 25 ファイルで「役割を記入してください」「処理を起動する」「処理を担当する」のいずれも一致なし。GF では問題が観測されていないことを確認。

---

## スコープ外項目（この対応では扱わない）

| 問題 | スコープ外の理由 |
|---|---|
| ⑤ 「役割を記入してください」 | GF Excel で観測されておらず、Sky 実物 Excel も手元にないため真因確定不能。`build_detail_design_json.py` は設計フロー上で実行されることがない（`generate_feature_list.py:352` の `load_obj_labels` import のみ）。Sky Excel で観測されたら再着手。 |
| ⑥ システム構成図物足りない | Sky/GF 両方とも `external_systems[]` のみ（`integrations[]` キー自体なし）。Sky の external_systems は GF より多い（8 vs 5）でむしろ充実。Sky 固有問題ではないと確定。 |
| ②④ 図形サイズ | GF 含む全プロジェクト共通の design choice 問題。`display_width=1120` 固定 / `zoom=0.4` 固定の課題。別タスク化。 |
| 追加 A-F | レポート原文が plan ファイルに保存されていないため追跡不能。ユーザー再提示があれば対応。 |

---

## 検証手順（実施済み）

1. 静的チェック: `python -m py_compile generate_basic_doc.py generate_detail_design.py diagram_gen.py` → exit 0 確認済み
2. GF 単体テスト: swimlanes.json（name ベース）・org-profile.md（3列）・aura なし の各 case で期待動作確認
3. MD ファイルのみの変更（A-1/A-2/A-3/B-1）は構文崩れなし確認
