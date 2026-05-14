# /backlog À la carte option 仕組み

`/backlog` コマンドは「ベース処理（最小限・全課題必須）」と「オプション 62 個（必要時のみ実行）」の組み合わせで動作する。重い処理・細かいチェックを **必要な時だけ呼ぶ** ことで、軽い課題は軽く・重い課題は徹底的に対応できるようにしている。

このファイルは、各 backlog 系エージェント（investigator / planner / validator / implementer / tester / releaser）の **Step 0** から共通参照される。

---

## ディレクトリ構成

```
.claude/templates/backlog/
├── _README.md                    # このファイル（仕組み説明・Step 0 共通ロジック）
├── _index-phase1.md              # Phase 1 用判定情報（21 オプション）
├── _index-phase2.md              # Phase 2 用判定情報（7 オプション）
├── _index-phase3.md              # Phase 3 用判定情報（8 オプション）
├── _index-phase3-5.md            # Phase 3.5 用判定情報（5 オプション）
├── _index-phase4.md              # Phase 4 用判定情報（5 オプション）
├── _index-phase5.md              # Phase 5 用判定情報（8 オプション）
├── _index-phase5-5.md            # Phase 5.5 用判定情報（4 オプション）
├── _index-phase6.md              # Phase 6 用判定情報（3 オプション）
├── _index-cross.md               # 横断系判定情報（2 オプション・全 Phase 参照）
├── xlsx-setup.md                 # Phase 1.5 対応記録ファイル作成手順
├── deploy-skip-judgment.md       # デプロイ適否の判定基準
├── resume-phase-routing.md       # 途中フェーズからの再開ルーティング
├── test-fail-routing.md          # Phase 5 NG 時の戻り先テーブル
├── customer-signoff.md           # お客様確認サインの種別別ルール
└── options/                      # 各オプションの実行手順（62 ファイル）
    ├── option-{name}.md
    └── ...
```

---

## Step 0: オプション判定の共通ロジック

各エージェントは処理開始時に **Step 0** を実行する。Step 0 は 2 段構造で、必要に応じて Step 0a → Step 0b の順で進める。

### Step 0a: SFコンテキスト読込（sf-context-loader 経由）

`sf-context-loader` を呼び出して関連コンテキストを取得する。

> 共通手順: [.claude/templates/common/sf-context-load-phase0.md](../common/sf-context-load-phase0.md)

**Step 0a を持つエージェント**:
- backlog-validator / backlog-implementer / backlog-tester / backlog-releaser

**Step 0a を持たないエージェント**:
- backlog-investigator / backlog-planner（`docs/` を直接全件読みするため不要）

### Step 0b: 関連オプションの判定（全エージェント必須）

1. **このフェーズ用の `_index-phase{N}.md` を Read**（Phase 1 なら `_index-phase1.md`、Phase 3.5 なら `_index-phase3-5.md`）
2. **Phase 5 (tester) のみ `_index-cross.md` を Read**（横断系オプション・他 Phase では評価しない）
3. 各オプションについて以下の 3 分岐で判定:

   | 判定 | 条件 | 挙動 |
   |---|---|---|
   | **実行** | `auto-execute-when` のいずれかにマッチ | そのまま実行（ユーザー確認なし） |
   | **スキップ** | `auto-skip-when` のいずれかに明確マッチ | **黙ってスキップ**（成果物末尾にスキップ理由を 1 行記録するのみ・ユーザー確認なし） |
   | **判断不能** | どちらにもマッチしない / グレー | **実行に倒す**（ユーザー確認なし） |

4. **実行決定したオプションのみ** `options/option-{name}.md` を Read して実行
5. 各オプションの結果を成果物（`investigation.md` / `approach-plan.md` / `validation-report.md` / `test-report.md` 等）に統合
6. スキップしたオプションは成果物末尾に「スキップ理由」付きで記録

### 重要原則

- **迷ったら実行**: グレー判定はスキップではなく実行に倒す（取り逃しを防ぐ）
- **オプション判定でユーザーに確認しない**: 実行もスキップも黙って実施。スキップ判定は成果物末尾に理由を 1 行記録するのみ。判定の正誤はユーザーが成果物を見て指摘できる
- **ユーザー確認はフェーズ末の業務判断のみ**: 過去データの扱い・業務ルール解釈・受入条件・適用範囲の確認に限る。実装側で判別できる事項（テストクラス追加・命名・grep して確認するだけの調査・既存パターン踏襲・カバレッジ要件）は確認に出さない
- **option カタログの選択は意味のあるシグナルに基づく**: `auto-execute-when` / `auto-skip-when` は「課題内容・変更対象・規模」から評価可能な条件のみ

### 典型的自明ケース定義（共通参照）

以下に該当する課題は「典型的自明ケース」として、関連オプションは `auto-skip-when` で skip する。各オプションの `auto-skip-when` は「典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）」と記述すれば該当条件を継承する。

**該当条件（以下を全て満たす）**:

- 変更範囲: 1 ファイル・3 行以下
- 変更種別が以下のいずれか:
  - typo / 誤字脱字修正
  - ラベル変更（field-meta.xml の `<label>` のみ・コードロジック影響なし）
  - コメント変更のみ
  - 単純な定数値 1 値変更（既存ロジック構造維持）
  - 単一行設定変更（入力規則 active 切替等）
  - LWC 文字列リテラル変更（i18n / 表示文言のみ・behavior 影響なし）
- 副作用検証: 副作用 grep で参照元の追加影響なし
- テスト影響: 既存テストが全 PASS のまま（API 名変更を含まない）

**該当しない例**:

- 数式項目の式変更・入力規則の式変更（ロジック変更扱い）
- API 名変更・型変更
- 複数ファイル横断変更

---

## オプションの 4 パターン分類

各オプションは判定パターンに基づいて以下のいずれかに分類される。`_index-phase{N}.md` の各エントリには `category: A|B|C|D` を付与する。

| パターン | 判定挙動 | 該当オプション例 |
|---|---|---|
| **A. 常時実行** | `auto-skip-when` 空、ほぼ無条件で実行 | option-symptom-reverification / option-multi-cause-hypothesis / option-counter-evidence-search / option-final-verifier / option-acceptance-criteria-recheck |
| **B. コード変更の有無で判定** | コード実体に影響しない変更（コメント・ラベル等）はスキップ確認 | option-reverse-grep / option-similar-impl-search / option-unit-test-creation / option-bulk-processing-check / option-soql-governor-limit-check |
| **C. 課題種別/ワード検出で判定** | 種別「バグ」「追加要望」や特定ワード（権限・データ・移行・パフォーマンス 等）でトリガ | option-permission-fls-check / option-sharing-rule-check / option-data-migration-plan / option-data-volume-analysis / option-performance-test |
| **D. 規模・影響範囲で判定** | 影響範囲広・全社影響・重要バグ時のみ実行 | option-second-opinion / option-stakeholder-notification / option-staged-deployment-plan / option-feature-flag-design / option-security-audit |

---

## blind 系オプション（subagent 化必須）

「先入観なし」が要件の 3 オプションは parent context に履歴が残ると blind 性が崩れるため、**サブエージェントとして独立実行** する。実行手順内で `Task` ツールから対応 subagent を起動する。

| オプション | 対応 subagent | 役割 |
|---|---|---|
| option-second-opinion | `backlog-blind-second-opinion` | parent の調査結果を見ずに原因仮説を独立に立てる |
| option-final-verifier | `backlog-blind-final-verifier` | 実装の経緯を知らず課題本文と実挙動だけで blind 解決判定 |
| option-validator-blind | `backlog-blind-validator` | implementation-plan を見ずに別案を独立に書いて比較 |

それ以外の 59 オプションは parent 内実行で OK（blind 性が要件でないため）。

---

## メンテルール

### option を新規追加する時

1. `options/option-{name}.md` を作成（実行手順のみ・判定情報は持たない）
2. 該当 Phase の `_index-phase{N}.md` にエントリ追加（name / description / auto-execute-when / auto-skip-when / ask-user-prompt / category / estimated-cost）
3. 横断系の場合は `_index-cross.md` に追加

### option の判定条件を変更する時

1. **`_index-phase{N}.md` のみを編集する**（option-*.md 側は実行手順のみで判定情報を持たないため）

### option を廃止する時

1. `options/option-{name}.md` を削除
2. 該当 `_index-phase{N}.md` からエントリ削除
3. 既存の backlog-* エージェントから option 名への直接参照があれば更新（通常は _index 経由なので参照なし）

### _index 自動生成スクリプトについて

現状は **手動メンテ**。62 個のオプションが揃って判定パターンが安定したら、`scripts/python/backlog-options/build_index.py` などの自動生成スクリプトを後付けで導入する。先に自動化すると判定情報のフォーマット制約が増えて柔軟性が落ちるため、現段階では手動を選択している。

---

## 既存ベース処理（option 化しないもの）

以下はベース処理として残し、option カタログから除外する:

- 課題本文＋全コメント読解（種別判定含む）
- docs/ 業務文脈抽出（主要 dir Read のみ）
- 関連コード起点コンポーネント特定 + 順方向追跡
- フィールド API 名確認（field-meta.xml）
- 業務要件不確実点の洗い出し
- 最低限のテストシナリオ設計
- 修正方針 1 案の策定（推奨案 A のみ・案 B/C は option-alternative-approaches）
- 実装計画策定（処理構造・データ設計・最低限の SOQL）
- 実装本体（FLS / CRUD / with sharing / API 名再照合 / docs 更新）
- 最低限の Apex テスト実行
- 合同 UI 確認（ユーザクロステスト）
- After エビデンス取得
- 接続先確認・リリース手順書作成
- 対応記録ファイル作成（簡易/詳細選択は AskUserQuestion で現状維持）
- エビデンスファイル作成（簡易/詳細選択は AskUserQuestion で現状維持）

詳細は各エージェント定義（`backlog-investigator.md` 等）を参照。

---

## Q 番号統一フロー（業務要件の不確実点）

Q 番号は **investigator が起点で生成し、後続エージェントが参照・回答・引き継ぐ** 業務要件マーカー。以下の規約で運用する。

### 表記
- 形式: `Q1.` `Q2.` ...（連番・半角・ピリオド付き）。`Q.` 単独や `Q:` は不可
- 並び順: 必ず昇順
- 不確実点が無い場合: 「Q なし」と明記（空欄禁止）

### エージェント別の責務

| Phase | エージェント | 責務 |
|---|---|---|
| 1 | investigator | Step F で Q を起票し investigation.md の「業務要件の不確実点」セクションに昇順で列挙 |
| 2 | planner (Phase A) | 各 Q に仮説を当て、対応方針案ごとに「前提となる Q」を明記。確定時に Q 答えを `approach-plan.md` 末尾に記録 |
| 3 | planner (Phase B) | Phase B-1 冒頭で `approach-plan.md` の Q 答えを読み込み、未確定 Q があれば再確認。`implementation-plan.md` の前提条件セクションに Q 答えを転記 |
| 3.5 | validator | `implementation-plan.md` の Q 答えが投入される前提と矛盾しないか Step 4（cross-review）で確認。矛盾があれば Phase 3 戻り |
| 5 | tester | Q 答えに依存するシナリオを test-report.md のシナリオ表で明示（「前提: Q1 答え=○○」） |
| blind 系 | blind-second-opinion / blind-validator | blind 性確保のため Q は受け取らない（投入禁止） |

### Q を起票する基準

investigator は以下を満たすときのみ Q を起票する:
- 業務側の判断がないと対応方針が分岐する（仮説では確定できない）
- docs / 課題コメント / 類似実装で答えが見つからない
- 「念のため確認したい」程度の事項は Q にしない（過剰な確認を生むため）

---

## Phase 末尾の確認プロトコル（共通仕様）

各 Phase 終了時、エージェントは以下のテキストブロックを出力してユーザの確認を待つ。AskUserQuestion は使わず、テキスト会話形式とする（`feedback_backlog_conversational_flow.md` 参照）。

### 出力テンプレート

```
【Phase {N} 完了サマリー】
（3〜5 行で成果物の本質・主な発見・次フェーズへの引き渡し要点を要約）

【確認事項】
（以下のいずれか）
- 特に確認事項はありません
- ① …
- ② …
- ③ …
（最大 3 件・Q 番号を含む場合は昇順）

【次へ】
Phase {N+1} に進んでよろしいですか？（または Phase X に戻る必要がありますか？）
```

### 確認事項の選定基準

- **書いてよい**: 業務判断が分かれる点・スコープ判断・Q 答えと方針の整合性・実装で新規発見した影響・エビデンス未取得項目の扱い
- **書かない**: テストクラス追加要否・命名・既存パターン踏襲・カバレッジ要件（実装側で判断する事項）・「採用案を確定してください」（次へ確認で兼ねる）
- **件数**: 0〜3 件。無理に挙げない。0 件なら「特に確認事項はありません」と明記
- **粒度**: 抽象的な文言（「念のため〇〇」「適切か確認」）は禁止。具体的な選択肢か質問形式に書く

### 文言統一

- 0 件時の文言: **「特に確認事項はありません」**（validator の「全ステップ異常なし」は validation-report.md 総合判定欄にのみ記載し、Phase 末尾の確認事項表記は「特に確認事項はありません」に統一）
- 確認列挙の番号: `①` `②` `③`（半角 1. 2. 3. ではない）
- 「次へ」表現: 「Phase {N+1} に進んでよろしいですか？」（「進みますか」「進んでいい？」等は不可）

---

## §対応記録 xlsx 責務分担表

各 Phase ・エージェントが対応記録 xlsx に書き込む内容の全体マップ。`update_records.py` コマンドは `{xlsx_folder}` が設定されている場合のみ実行する。

| シート | セクション / セル | 担当 Phase / エージェント | コマンド |
|---|---|---|---|
| サマリー・経緯 | 課題ID/件名/優先度/種別/ステータス/背景 (B3-B8) | Phase 3 / create_records.py | 一括生成 |
| サマリー・経緯 | 最終対応サマリー (B9) | Phase 6 / releaser | `cell --row 9 --col 2` |
| サマリー・経緯 | 採用方針/主要変更/ロールバック手順 (B11-B13) | Phase 3 / create_records.py | 一括生成 |
| サマリー・経緯 | 判断保留事項 | Phase 3 / create_records.py | 一括生成 |
| サマリー・経緯 | タイムライン No1-3 | Phase 3 / create_records.py | 一括生成 |
| サマリー・経緯 | タイムライン No4〜 | Phase 3.5/4/5/6 / 各エージェント | `timeline --phase X` |
| 対応方針 | 方針比較テーブル / 実施前確認事項 | Phase 3 / create_records.py | 一括生成 |
| 調査・影響範囲 | コード根拠テーブル | Phase 3 / create_records.py | 一括生成 |
| 対応内容 | バックアップ情報 (B3-B5) | Phase 4 開始時（実装着手前）/ implementer | `backup-info` |
| 対応内容 | 変更ファイル一覧 | Phase 3 / create_records.py | 一括生成 |
| 対応内容 | Before / After | Phase 4 / implementer | `before-after` |
| 対応内容 | 影響確認チェックリスト | Phase 4 / implementer | `checklist --sheet 対応内容` |
| テスト・検証記録 | テスト項目（タイミング=実装前 行の実際の結果 F列・判定 G列） | Phase 3.5 / validator | `test-precheck` |
| テスト・検証記録 | テスト項目（タイミング=実装後 行の実際の結果 F列・判定 G列） | Phase 5 / tester | `cell --col 6/7`（実装後行のみ） |
| リリース・ロールバック | リリース対象一覧 | Phase 3 / create_records.py | 一括生成 |
| リリース・ロールバック | デプロイ手順 | Phase 6 / releaser | `cell` |
| リリース・ロールバック | 注意事項・リスク | Phase 3 / create_records.py | 一括生成 |
| リリース・ロールバック | ロールバック手順 | Phase 6 / releaser | `cell` |

> **注**: リリース実施記録セクションは patch_template_v6 でテンプレから削除済み（人間がデプロイ実施するため Claude 非関与）。
>
> **注**: xlsx・MD 成果物の全ての値書き込み欄は §人が読む欄の日本語・表示ラベル規約に従うこと（ファイル名列・コード根拠テーブル等の例外を除く）。

---

## § 人が読む欄の日本語・表示ラベル規約

xlsx・MD 成果物の **人が読む欄**（概要・メリット・デメリット・採用方針・懸念事項・注意事項・リスク・調査結果サマリー等）は次のルールに従う:

- **オブジェクト・項目はオブジェクトラベル / 項目ラベルで書く**。API 名（`__c` 末尾の英語名）は補助として括弧書きで添えてよい
  - OK 例: 「渡航者マスタの『犯罪歴』項目（CriminalHistory__c）を新設して、preCheckModal で選択肢を保存する」
  - NG 例: 「`BusinessTraveler__c` に `CriminalHistory__c` を新設して `preCheckModal.js` で保存する」
- **日本語の自然な文章で書く**。英語の固有名詞をそのまま並べた箇条書きは禁止
  - OK 例: 「『はい』を選択しても判定結果は OK のまま進める」
  - NG 例: 「`PreCheckResult__c` is OK のまま push」
- **コンポーネント名はそのまま使ってよい**（Apex クラス・LWC・トリガー・Flow の名前は識別子なので英語のまま）
  - OK 例: 「PreCheckController.getInitData の SELECT 句に犯罪歴項目を追加」
- **判断ポイント・受入条件・テスト項目** など機械的に解釈する欄も同じ規約（人が読む欄を兼ねるため）
- **例外（このルール対象外）**: コード根拠テーブル（コード行コピー）・関連コンポーネント一覧（ファイル名列）・自動取得値・SOQL 句

**判定基準（迷ったら）**: 「3 ヶ月後の別担当者が、コードを見ずにこの 1 セルを読んで何の話か理解できるか」が分かれ目。「No」なら表示ラベル化が必要。

> オブジェクト・項目の表示ラベルは `docs/catalog/{Object}.md` または `docs/overview/org-profile.md` の用語集を参照。docs/ にも記載がなければ、`{ラベル不明}（API名: XXX__c）` の形式で暫定記入し、確認後に修正する。

> **方針比較テーブルは特にコンパクト性が求められる**（概要 60 字・メリット/デメリット 30 字・工数 20 字以内）。詳細は `backlog-planner.md §対応方針` を参照。
