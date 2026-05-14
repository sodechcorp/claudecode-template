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
├── _index-phase5-5.md            # Phase 5.5 用判定情報（3 オプション）
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
