# /backlog À la carte option 仕組み

`/backlog` コマンドは「ベース処理（最小限・全課題必須）」と「オプション（必要時のみ実行）」の組み合わせで動作する。重い処理・細かいチェックを **必要な時だけ呼ぶ** ことで、軽い課題は軽く・重い課題は徹底的に対応できるようにしている。

このファイルは、各 backlog 系エージェント（investigator / planner / validator / implementer / tester / releaser）の **Step 0** から共通参照される。

---

## ディレクトリ構成

```
.claude/templates/backlog/
├── _README.md                    # このファイル（仕組み説明・Step 0 共通ロジック）
├── _index-phase1.md              # Phase 1 用判定情報
├── _index-phase3.md              # Phase 3 用判定情報
├── _index-phase3-5.md            # Phase 3.5 用判定情報
├── _index-phase4.md              # Phase 4 用判定情報
├── _index-phase5.md              # Phase 5 用判定情報（横断系オプション含む）
├── _index-phase6.md              # Phase 6 用判定情報
├── _archive-production-release.md # 本番リリース手順書アーカイブ（資産保全のみ・実行時は非参照）
├── _partials/                    # 差分ベース定型チェックの部品（deploy-manifest-base.md 等）
├── phase1-6-sandbox-verification.md # Phase 1.6 詳細手順（backlog.md からバグ系のみ条件付き Read）
├── phase2-inquiry-mode.md        # Phase 2 問い合わせ専用モード詳細手順（backlog.md から条件付き Read）
├── planner-phase-q.md            # backlog-planner Phase Q 詳細手順（backlog-planner.md から条件付き Read）
├── deploy-skip-judgment.md       # デプロイ適否の判定基準
├── resume-phase-routing.md       # 途中フェーズからの再開ルーティング
├── test-fail-routing.md          # Phase 5 NG 時の戻り先テーブル
├── test-pattern-map.md           # 課題種別 → テストパターンマッピング
├── release-checklist-matrix.md   # 本番リリース チェックリスト・マトリクス（前→実行→後）
├── customer-signoff.md           # お客様確認サインの種別別ルール
├── discussion-log-spec.md        # discussion-log.md の記録仕様（各エージェントから参照）
└── options/                      # 各オプションの実行手順
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
- backlog-planner — **knowledge-only モード**（sf-context-loader を `focus_hints: ["knowledge-only"]` で呼び出し、knowledge/ ファイルの選択的読込のみを行う。docs/ 全件読みは別途 Phase B で実施するため重複しない）
- backlog-implementer / backlog-tester / backlog-releaser — **通常モード**（sf-context-loader を標準 focus_hints で呼び出す）
- backlog-validator — **ダイジェスト限定モード**（sf-context-loader は起動しない。二段ネスト回避のため leaf agent 化しており、`context-digest.md` の再利用と直接 Read のみで完結させる。詳細は backlog-validator.md Step 0a 参照）
- backlog-investigator — **呼び出し元（backlog.md）が事前取得**（knowledge-only + 通常モードの両方を Phase 1 開始前に backlog.md が同一メッセージで並列に Task 起動し、結果を渡す。investigator 自身は起動しない。二段ネスト回避のため。詳細は backlog-investigator.md Step 0a 参照）

### Step 0b: 関連オプションの判定（全エージェント必須）

1. **このフェーズ用の `_index-phase{N}.md` を Read**（Phase 1 なら `_index-phase1.md`、Phase 3.5 なら `_index-phase3-5.md`）
2. 各オプションについて以下の 3 分岐で判定:

   | 判定 | 条件 | 挙動 |
   |---|---|---|
   | **実行** | `auto-execute-when` のいずれかにマッチ | そのまま実行（ユーザー確認なし） |
   | **スキップ** | `auto-skip-when` のいずれかに明確マッチ | **黙ってスキップ**（成果物末尾にスキップ理由を 1 行記録するのみ・ユーザー確認なし） |
   | **判断不能** | どちらにもマッチしない / グレー | オプションに `default-when-uncertain: skip` が設定されていれば**黙ってスキップ**（理由「判断不能 + default skip」を成果物末尾に記録）。未設定または `execute` の場合は**実行に倒す**（ユーザー確認なし） |
   | **競合** | `auto-execute-when` と `auto-skip-when` の両方にマッチ | **実行を優先する**（`default-when-uncertain` の設定にかかわらず）。成果物末尾の「採用したオプション」欄に「競合（skip条件「{条件}」もヒットしたが execute 優先）」と 1 行記録する |

3. **実行決定したオプションのみ** `options/option-{name}.md` を Read して実行（実行する位置をエージェント本体が指定している場合はその位置で実行する）
4. 各オプションの結果を成果物（`investigation.md` / `implementation-plan.md` / `validation-report.md` / `test-report.md` 等）に統合
5. スキップしたオプションは成果物末尾に「スキップ理由」付きで記録

### オプション実行ログの書式

各 Phase の成果物 MD の末尾に `## Step 0b オプション判定結果` セクションを設け、配下に `### 採用したオプション` / `### スキップしたオプション` の 2 小見出しを置く。採用したオプションは `- \`option-{name}\`: {実行結果の要約 1 行}`、スキップしたオプションは `- \`option-{name}\`: {auto-skip-when マッチ理由 1 行}` の形式で記録する（`backlog-tester.md` のみ、成果物構成上 `### Step 0b オプション判定結果` → `#### 採用したオプション`/`#### スキップしたオプション` と見出しレベルが 1 段深くなる）。**この書式（見出し文字列・箇条書き形式）は `release-preparer.md` が Phase 1 の option 実行済み判定に Grep で解析するため変更してはならない**。

### 重要原則

- **迷ったら実行**（既定）: グレー判定はスキップではなく実行に倒す（取り逃しを防ぐ）
- **例外: `default-when-uncertain: skip` を明示できるオプション**: (a) `estimated-cost: 重` かつ実行条件がキーワードヒット型のオプション（subagent 起動・全件探索系）、(b) category D（規模・影響範囲限定オプション）のうち `auto-execute-when` が課題内容から確度高く判定できずグレー誤爆リスクが高いもの。いずれも `default-when-uncertain: skip` を明示することで「グレー → スキップ」を選べる。`auto-execute-when` がヒットすれば従来通り実行されるため、明示的な実行シグナルがある時のみ起動する形になる
- **オプション判定でユーザーに確認しない**: 実行もスキップも黙って実施。スキップ判定は成果物末尾に理由を 1 行記録するのみ。判定の正誤はユーザーが成果物を見て指摘できる
- **ユーザー確認はフェーズ末の業務判断のみ**: 過去データの扱い・業務ルール解釈・受入条件・適用範囲の確認に限る。実装側で判別できる事項（テストクラス追加・命名・grep して確認するだけの調査・既存パターン踏襲・カバレッジ要件）は確認に出さない
- **option カタログの選択は意味のあるシグナルに基づく**: `auto-execute-when` / `auto-skip-when` は「課題内容・変更対象・規模」から評価可能な条件のみ

#### ⚠️ バグ非自明における徹底調査ゲート

種別が**バグ**（typo・定数値誤り等、コード上で明白に特定できる自明バグを除く）の場合、以下が上記「迷ったら実行」より優先して適用される:

- **原因特定系オプションは `auto-execute-when` ヒット有無に関わらず実行側へ倒す**: category A（常時実行寄り: option-symptom-reverification / option-multi-cause-hypothesis / option-counter-evidence-search / option-causal-chain-analysis / option-apex-debug-log / option-cross-record-comparison / option-error-message-reverse-lookup / option-assumption-listing）および option-reverse-grep は、明示的なキーワードシグナルがなくても実行する。**ただし手法自体が成立しないことを示す `auto-skip-when` 条件（例: option-error-message-reverse-lookup の「エラー文言の記載がない」、option-cross-record-comparison の「比較対象となる正常レコードが存在しない」）は引き続き適用してスキップする**（「種別が追加要望・その他」由来の条件は本ゲート適用時は元々該当しないため対象外）。**単一原因仮説が高確信度で確定し矛盾する証拠がない場合**: 上記 category A オプションは「新規の反証観点を追加する」実行ではなく「矛盾がないかの確認」に短縮してよい（詳細: backlog-investigator.md §調査原則の早期打ち切り原則）。カタログを機械的に全部フル実行することが本ゲートの目的ではない
- **カタログに無い調査手段も自律的に実行**: オプションは最低限の床。バグ非自明では、カタログ外の調査方法も investigator 自身が発想して実行してよい（「採用したオプション」欄に `adhoc-{名前}` で記録）。ただし高確信度の仮説が既にある場合は件数稼ぎの追加調査をしない（早期打ち切り原則が優先）。3 件を超える場合は同欄に超過理由も 1 行記録する（実行を止める上限ではない。詳細: backlog-investigator.md §調査原則）
- **コスト最適化の適用対象は「追加要望・その他」のみ**: `default-when-uncertain: skip` の軽量化バイアスはバグに適用しない

---

## オプションの 4 パターン分類

各オプションは判定パターンに基づいて以下のいずれかに分類される。`_index-phase{N}.md` の各エントリには `category: A|B|C|D` を付与する。

| パターン | 判定挙動 | 該当オプション例 |
|---|---|---|
| **A. 常時実行** | `auto-skip-when` 空、ほぼ無条件で実行 | option-symptom-reverification / option-multi-cause-hypothesis / option-counter-evidence-search / option-knowledge-extraction |
| **B. コード変更の有無で判定** | コード実体に影響しない変更（コメント・ラベル等）はスキップ確認 | option-reverse-grep / option-similar-impl-search / option-unit-test-creation / option-bulk-processing-check / option-soql-governor-limit-check |
| **C. 課題種別/ワード検出で判定** | 種別「バグ」「追加要望」や特定ワード（権限・データ・移行・パフォーマンス 等）でトリガ | option-permission-fls-check / option-sharing-rule-check / option-data-migration-plan / option-data-volume-analysis / option-performance-test |
| **D. 規模・影響範囲で判定** | 影響範囲広・全社影響・重要バグ時のみ実行 | option-second-opinion / option-staged-deployment-plan / option-feature-flag-design / option-security-audit |

> **`_index-phase{N}.md` の対象外の option**: `option-acceptance-criteria-recheck` は上記 4 パターン分類（`_index-phase{N}.md` の auto-execute-when / auto-skip-when 判定）の対象外。旧 `/backlog` Phase 5.5 で使われていたが、Phase 5.5 廃止後は After エビデンスが確定する `/test` コマンド側に再統合されており、`.claude/commands/test.md` Phase F-1 から毎回直接呼び出される。

---

## blind 系オプション（subagent 化必須）

「先入観なし」が要件の 3 オプションは parent context に履歴が残ると blind 性が崩れるため、**サブエージェントとして独立実行** する。実行手順内で `Task` ツールから対応 subagent を起動する。

| オプション | 対応 subagent | 役割 |
|---|---|---|
| option-second-opinion | `backlog-blind-second-opinion` | parent の調査結果を見ずに原因仮説を独立に立てる |

それ以外のオプションは parent 内実行で OK（blind 性が要件でないため）。

> **`option-validator-blind` は廃止済み（2026-09-18）**: 実装方針案の独立比較（`backlog-blind-validator`）は、人間が対応方針を決める新設計（§承認判定 参照）では二重チェックの意義がなく、Phase 3.5（backlog-validator）による技術的見落とし検出（GF-350・GF-374 で本番差分退行の見落としを実際に検出した実績あり）と重複するため廃止した。

---

## メンテルール

### 本ディレクトリにファイルを追加・削除する時

1. **§ディレクトリ構成**（本ファイル冒頭）の図を更新する

### option を新規追加する時

1. `options/option-{name}.md` を作成（実行手順のみ・判定情報は持たない）
2. 該当 Phase の `_index-phase{N}.md` にエントリ追加（name / description / auto-execute-when / auto-skip-when / category / estimated-cost）
   - `prerequisites`（任意）: 実行前に満たすべき前提条件の一覧。例: 「test-report.md にエビデンスマッピング表が存在し全項目✅取得済」
   - `prerequisite-fail-action`（任意）: 前提条件が満たせない場合の指示（エラー文言 or フォールバック手順）。`prerequisites` がある場合は必ずセットで記述する
3. Phase 5 向けの場合は `_index-phase5.md` に追加（横断系オプションも Phase 5 に統合済み）

### option の判定条件を変更する時

1. **`_index-phase{N}.md` のみを編集する**（option-*.md 側は実行手順のみで判定情報を持たないため）

### option を廃止する時

1. `options/option-{name}.md` を削除
2. 該当 `_index-phase{N}.md` からエントリ削除
3. 既存の backlog-* エージェントから option 名への直接参照があれば更新（通常は _index 経由なので参照なし）

### option 間に実行順序依存がある場合

一部の option は別の option の実行結果を前提とする（例: counter-evidence-search は multi-cause-hypothesis で仮説が立った後に実行する）。この場合:

1. 依存元の option が先に実行されていること
2. **該当 `_index-phase{N}.md` の冒頭に明記する**（例: `# ⚠️ 実行順序依存: option-X を option-Y より先に実行すること`）
3. `option-*.md` 本体にも前提として記述する

依存関係のない option は並列・任意順で OK（明記不要）。

### _index 自動生成スクリプトについて

現状は **手動メンテ**。オプションが揃って判定パターンが安定したら、`scripts/python/backlog-options/build_index.py`（将来案・未実装）などの自動生成スクリプトを後付けで導入する。先に自動化すると判定情報のフォーマット制約が増えて柔軟性が落ちるため、現段階では手動を選択している。

---

## 既存ベース処理（option 化しないもの）

以下はベース処理として残し、option カタログから除外する:

- 課題本文＋全コメント読解（種別判定含む）
- docs/ 業務文脈抽出（主要 dir Read のみ）
- 関連コード起点コンポーネント特定 + 順方向追跡
- フィールド API 名確認（field-meta.xml）
- 業務要件不確実点の洗い出し
- 対応方針の判断材料の提示（推奨1つ、または業務判断が分かれる論点のみ。決定は担当者）
- 実装計画策定（処理構造・データ設計・最低限の SOQL）
- 実装本体（FLS / CRUD / with sharing / API 名再照合 / docs 更新）
- 最低限の Apex テスト実行
- 合同 UI 確認（ユーザクロステスト）
- After エビデンス取得
- 接続先確認・Sandbox デプロイ（Phase 6 は Sandbox リリース専用）

詳細は各エージェント定義（`backlog-investigator.md` 等）を参照。

---

## §調査責務の境界

各 Phase で「何をユーザーに問い、何を自分で確認するか」の線引き。特に Phase 1（investigator）に適用。

| 分類 | 内容 | 判断基準 |
|---|---|---|
| **ユーザーに出してよい（Q 番号 or テキスト依頼）** | (a) 業務判断（対応方針が変わる Q）/ (b) ClaudeCode が本当にアクセスできない外部データ（認証必須リンク・取得できない添付や Backlog に無い資料・sf CLI で接続していない組織の設定） | 自分のツールでは取得不可能か？ |
| **絶対に委ねない（自分で確認）** | 調査方法・着眼点（「ログを見るべきか」「どこを grep するか」）/ Sandbox で再現可能な事象 / コード・メタデータで判明する事実 / Apex ログで判明する実行時挙動 / 類似レコードとの差分 | 自分のツール（Read/Grep/Bash/sf CLI/WebFetch/Backlog MCP）で確認できるか？ |

**判定原則**: 「自分のツールで確認できるか？」を先に問う。できるなら聞かない。聞く前に自分で試した旨と結果を investigation.md に残す。

**investigator が犯しがちな誤り（禁止）**:
- 「ログを確認するよう依頼しますか？」→ 禁止。自分で Apex デバッグログを取得する（option-apex-debug-log）
- 「似たレコードを共有してもらえますか？」→ 禁止。自分で SOQL で抽出・比較する（option-cross-record-comparison）
- 「エラー箇所を特定するための追加情報をください」→ 禁止。エラー文言を自分で逆引き grep する（option-error-message-reverse-lookup）

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
| 2 | main thread（backlog.md Phase 2） | 未回答の Q を推奨付きで担当者に提示し、回答を `approach-plan.md`「### 業務要件への回答」に記録 |
| 3 | planner (Phase B) | Phase B-1 冒頭で `approach-plan.md` の Q 答えを読み込み、未確定 Q があれば再確認。`implementation-plan.md` の前提条件セクションに Q 答えを転記 |
| 3.5 | validator | `implementation-plan.md` の Q 答えが投入される前提と矛盾しないか Step 4（cross-review）で確認。矛盾があれば Phase 3 戻り |
| blind 系 | blind-second-opinion | blind 性確保のため Q は受け取らない（投入禁止） |

> **Phase 4（implementer）・Phase 5（tester）に明示的な Q 番号責務がない理由**: Q 答えは Phase 3（planner Phase B）の時点で `implementation-plan.md` の前提条件セクションに転記済みのため、Phase 4 以降は実装計画を実装・検証する通常フローの中で Q 答えが自然に反映される。個別の Q トレーサビリティ表は持たない。

### Q を起票する基準

investigator は以下を満たすときのみ Q を起票する:
- 業務側の判断がないと対応方針が分岐する（仮説では確定できない）
- docs / 課題コメント / 類似実装で答えが見つからない
- 「念のため確認したい」程度の事項は Q にしない（過剰な確認を生むため）

---

## Phase 末尾の確認プロトコル（共通仕様）

各 Phase 終了時、エージェントは以下のテキストブロックを出力してユーザの確認を待つ。AskUserQuestion は使わず、テキスト会話形式とする（承認判定ルールは本節 §承認判定 参照）。

### 出力テンプレート

```
【Phase {N} 完了サマリー】
（フェーズ別の型に従って書く。詳細は §サマリーの書き方 参照）

【確認事項】
特に確認事項はありません
（業務判断が必要な場合のみ ① ② ③ で列挙・最大 3 件・Q 番号は昇順）

【次へ】
異議がなければこのまま Phase {N+1} に進みます
```

> Phase 1・1.6 は本テンプレートを出さない（結果は Phase 2 の提示にまとめる）。明示承認が要る Phase 2（対応方針の決定）は本テンプレートを使わず、`backlog.md` Phase 2 の提示形式に従う。自動進行を止める条件（`backlog.md`【フェーズ進行】）に該当した場合は、【次へ】の代わりに確認事項への回答を待つ。

### 知見還流トリガーの自己チェック（内部判断・出力テンプレートには影響しない）

上記【次へ】を出力する前に、Claude は出力に含めず内部的に「このセッションは Phase 6 に到達しない可能性が高いか」を自問する（客都合の停滞・Phase 2/3 での長時間往復・ユーザーから継続意思の明確な表示がない等が兆候）。該当すると判断した場合のみ、【次へ】の直後に一言添える:

```
このまま完了に至らない場合は `## §中断時の知見還流（部分還流）` の実施をご検討ください。
```

明確な兆候がない通常進行時は言及しない（毎回付記すると【次へ】の簡潔さを損なうため）。§中断時の知見還流の発火自体は従来どおりユーザーの明示シグナルに委ねる方式を維持し、本チェックは見落とし防止の補助に留める。

### §サマリーの書き方（フェーズ別）

> **書き方の鉄則**（全フェーズ共通）:
>
> - **先頭に結論を1文**。「で、結局どうなの」が最初の1行で分かるように書く。
> - **自然な日本語・人間向け**。メソッド名・SOQL・API名を地の文に並べない。オブジェクト/項目は **§人が読む欄規約** に従いラベルで書き、API名は括弧補助のみ（コンポーネント名＝Apexクラス/LWC名は識別子なのでそのまま可、ただし羅列しない）。
>   - OK 例: 「渡航者マスタに『犯罪歴』項目を新設して、事前チェック画面で選んだ内容を保存するようにします」
>   - NG 例: 「`BusinessTraveler__c` に `CriminalHistory__c` を足して `preCheckModal.js` で保存」
> - **ダラダラ書かない**。技術的詳細は成果物（MD/xlsx）に置き、チャットは要点だけ。
> - **Phase 3 の■項目（後述）にも本原則が及ぶ**。「丁寧に書く」は説明の分かりやすさ・言葉選びを指すのであって、行数を伸ばしてよいという意味ではない。■1項目は3行以内。結論の1文を含めサマリー全体で10行以内。上限は目標ではなく上限なので、判断に不要な前提説明・当たり前の繰り返しは書かず、できるだけ短く収める。
> - **例外（回答系の成果物）**: 上記「要点だけ」はプロセスの途中経過（調査・方針検討等の技術詳細）に対する原則であり、**ユーザーがそのまま送付・投稿に使う完成品**（問い合わせ回答ドラフト等）には適用しない。この種の成果物は要約で済ませず、**ファイル保存に加えてチャットに全文をそのまま提示する**（ファイルを開かせない）。新規コマンド/エージェントで同種の成果物を追加する際もこの例外を踏襲すること。ただし成果物内に**対外送付部分と社内レビュー用部分が併記されている場合**（例: 回答ドラフトの「質問の要約・根拠・[要確認]・補足」）、「全文」は対外送付部分のみを指す。社内レビュー用部分はファイル保存のみに留め、チャットへの再掲は不要（詳細は `backlog.md` Phase 2「問い合わせ」節を参照）。
> - **出力前チェック（必須）**: サマリーを出力する直前に、(1) ■項目数が型どおりか (2) 各■が上限行数以内か (3) メソッド名・SOQL・API名が地の文に出ていないかを自己確認する。超過した場合は削ってから出力する。

**Phase 0・3.5・4・5・6**（調査/対応/実装方針以外）:
3〜5行で成果物の本質・主な発見・次フェーズへの引き渡し要点を要約する（従来どおり）。

---

**Phase 1（調査）・Phase 1.6（Sandbox 検証）・Phase 2（対応方針の決定）**:

Phase 1・1.6 単独のサマリーは出さない（途中は「Sandbox で再現を確認します」等の1行の進捗のみ。仮説・検証結果の中身は書かない。止まる条件に当たった場合は `backlog.md`【フェーズ進行】に従う）。課題の説明（どんな課題か・原因/現状。バグは Sandbox での検証結果を含む）は Phase 2 の提示に1回でまとめる。Phase 2 の提示形式・推奨の決め方は `backlog.md` Phase 2 を正本とする。

---

**Phase 3（実装方針）**:

「どこをどう直すと、最終的にどう動くか」がエンドツーエンドで1読で分かるように書く。

```
【Phase 3 完了サマリー】
（結論1文: 変更の全体感を一言で。例:「〇〇コンポーネントを中心に△件のファイルを修正します。」）

■ 前提（Phase 2 のまとめ・3行以内）: 合意した対応方針を1行で再掲
■ 修正箇所（3行以内）: どのコンポーネント/ファイルをどう直すか（ファイル名のみ可、パス羅列不要）
■ 変わること（3行以内）: 修正によって直接変わる挙動
■ 最終挙動（3行以内）: ユーザー目線で最終的にどう動くか（「〇〇したら△△できるようになります」の形で）
```

### 確認事項の選定基準

> **原則: 迷ったら 0 件。確認事項を埋めるために質問を作るのは禁止。**

- **書いてよい**: 業務判断が分かれる点・スコープ判断・Q 答えと方針の整合性・実装で新規発見した影響
- **書かない**: テストクラス追加要否・命名・既存パターン踏襲・カバレッジ要件（実装側で判断する事項）・「採用案を確定してください」（次へ確認で兼ねる）・抽象的な文言（「念のため〇〇」「適切か確認」「問題ないか確認」）・派生事項（investigation.mdでは「## 派生事項（本対応スコープ外）」節、それ以外のフェーズは CLAUDE.md §ユーザー回答時のスコープ管理の「## 派生事項（質問外）」節で扱う。確認事項に混在させない）・影響範囲調査結果（investigation.md「影響範囲」節の記載内容そのもの。判断が必要な新規発見の影響は上記「書いてよい」の対象なので区別する）
- **件数**: 0〜3 件。0 件が正常。1〜3 件は例外（業務判断が本当に割れる場合のみ）
- **1件あたりの分量**: 各項目は1〜2行以内。構成は『①{何を判断してほしいか}（{選択肢A}/{選択肢B}）』の形にする。推薦がある場合も1文まで
  - OK 例: 「①保守用の一時的な権限緩和を許容しますか（許容する/許容しない）。今回は影響範囲が限定的なため許容を推奨します」
  - NG 例: 「①権限設計について、現状のプロファイル運用を踏まえつつ、今後の拡張性も考慮した上でどのような方針が望ましいか、背景も含めてご意見をいただけますでしょうか」

### 文言統一

- 0 件時の文言: **「特に確認事項はありません」**（validator の validation-report.md 総合判定欄は 0 件時も総合判定の優先順位ルールで確定した4値のいずれか（通常「Phase 4（実装）へ進んでよい」）を記載し、Phase 末尾の確認事項表記は「特に確認事項はありません」に統一）
- 確認列挙の番号: `①` `②` `③`（半角 1. 2. 3. ではない）
- 「次へ」表現: 自動進行は「異議がなければこのまま Phase {N+1} に進みます」。明示承認が要る Phase 2 は「これで進めてよいですか？」（一択の推奨時）または Q への回答を求める形

### 承認判定（厳格化・必須）

> **原則: 対応方針の決定（Phase 2→3）は、担当者の決定が確信できなければ次へ進まない。迷ったら確認を出し直す。**

**明示承認が必要なのは Phase 2→3（対応方針の決定）の1点のみ。** 対応方針は担当者の業務判断そのものであり、ClaudeCode は判断材料と推奨を示すだけで決めない。**それ以外の遷移は全て自動進行**（Phase 0→1／1→1.6／1.6→2／3→3.5／3.5→4／4→5／5→6）し、問題が見つかった時だけ止まる（止まる条件は `backlog.md`【フェーズ進行】を正本とする）。実装着手（3.5→4）も、実装前検証で決定方針・実装計画に問題がなければ自動で進む（Sandbox は可逆のため）。本番デプロイ・お客様サイン・Backlog 投稿はそもそも `/backlog` の範囲外で、hook によるハードブロック・人間の手動実施が別途担保している。

**判断基準**: 「AI にやらせる方が人間がやるより速いか、または人間の目では原理的に検知できないリスクを拾うか」。YES なら自動進行、NO（人間の業務判断そのもの）なら明示承認に残す。

**方針の決定とみなすもの**: Phase 2 の提示に対する、方針を肯定・指定する明確な返答（「OK」「それで」「進めて」「〇〇で対応して」「Q1 は A で」等）。担当者が推奨と異なる方針を指定した場合も、その指定を決定とみなす。

**方針の決定とみなさないもの（次フェーズに進んではいけない）**:
- **質問・確認**: 「本当に？」「どっち？」「これでいい？」等
- **相槌・短い感嘆**: 「ha」「うん」「なるほど」「ふむ」「ほう」等、進行肯定が読み取れない発話
- **別タスク依頼**: 「工数計算して」「見積もって」「〇〇を調べて」等の独立した作業依頼。特に**工数・見積依頼は `sf-effort-estimator` 委譲対象**（`.claude/spec/agent-routing.md` 参照）。依頼を処理した後、改めて方針の確認を出し直す
- **Q への回答が一部だけ**: 未回答の Q が残っている場合は、残りを確認してから進む

### discussion-log.md への追記（確認プロトコル直後・必須）

Phase 末尾確認プロトコルの出力ブロックを出力した**直後**（ユーザーの返答を待つ前）に、`docs/logs/{issueID}/discussion-log.md` へ当該 Phase の議論を追記する。

> 記録仕様・フォーマット・何を残すか: [discussion-log-spec.md](discussion-log-spec.md) を参照

**追記が必要な内容（Phase 末尾時点）**:
- 当該 Phase でユーザーから出た指摘・却下・補足（生引用に近い形）
- エージェントが提示した案の中で却下されたもの（却下理由付き）
- 調査・実装中に判明した重要な発見（後 Phase に影響するもの）
- 方針変更の経緯（何が→何に変わった・理由）

**追記が不要な内容**:
- Q番号テーブルの内容（approach-plan.md「### 業務要件への回答」欄に記録済みのため重複不要）
- 問題なく承認されたフロー（「OK です」→ 次 Phase のみのやり取り）
- 単純な実装詳細・命名・既存パターン踏襲

**ファイルが存在しない場合**: Write で新規作成してから追記する。

---

## §Phase 進行中の差し込みプロトコル

エージェント実行中にユーザーから指示・方針変更・質問が入った場合、main スレッドは以下の手順で対処する。

1. **即時 discussion-log.md に追記**: エージェントの完了を待たずに追記する。形式は §discussion-log 仕様に準ずる（種別: ユーザー差し込み）
2. **エージェント完了後に影響判定**: エージェントが完了した時点で「差し込み内容が成果物に反映されているか」を確認する
   - 反映済み → Phase 末尾の確認プロトコルを通常どおり実行
   - 未反映・軽微（命名等） → 成果物を直接修正して Phase を続行
   - 未反映・重大（方針転換・スコープ変更） → 「差し込みを反映するために当該 Phase を再実行します」と案内し、approach-plan.md への遡り要否を明示する
3. **approach-plan.md まで遡る場合**: Phase 2 の判断材料の提示から再開し、担当者の決定後に approach-plan.md の改版履歴テーブルに変更経緯を追記する
4. **差し込みが「Phase 6 に到達しない」ことを意味する場合**（例: 「客都合で中断」「手動対応へ切替」「リリース省略」等）: [backlog.md §中断時の知見還流](../../commands/backlog.md) を案内し、知見の部分還流を実行してから終了する

---

## §compact 跨ぎ復元プロトコル

/compact 後の再開時に失われる情報とその復元先:

| 変数 | 永続化先 | 復元方法 |
|---|---|---|
| `{issue_type}` | investigation.md フロントマター `issue_type:` | Phase 0d で Read |
| `{deploy_route}` | investigation.md フロントマター `deploy_route:` | Phase 0d で Read |

**運用ルール**: `issue_type` / `deploy_route` は Phase 1 完了時点（`{issue_type}` 確定直後）に `backlog.md` Phase 1 末尾の記録 step で書き込む（全種別で必ず実行）。自動フォールバック（docs/logs/ への書き出し）は `/test` でのフォールバック誤発動の原因になるため、この手順のスキップは禁止。フロントマター例:
```yaml
---
issue_id: XXX-123
issue_type: バグ
deploy_route: normal
---
```

/backlog コマンド再起動後の Phase 0d では、investigation.md のフロントマターから上記変数を読み込んで復元する。

---

## §AskUserQuestion の使用ルール

/backlog コマンド体系では原則としてテキスト会話でフェーズ進行する（AskUserQuestion は使わない）。

**例外として AskUserQuestion を使ってよいケース**（以下のみ）:
1. **Phase 0 再開 Phase 選択**: コマンド起動時に既存の investigation.md を検出した場合の「どこから再開するか」の選択（クリック式の方が誤操作防止になる）

上記以外でユーザーに選択を求める場合は、必ずテキスト会話で行う。validator の issueID 解決も、候補が3件以下なら「`XXX-1`、`XXX-2`、`XXX-3` のどれを対象にしますか？」とテキストで確認する。

---

> **対応記録.xlsx は廃止済み（2026-09-18）**: investigation.md / approach-plan.md 等の内容を xlsx 形式に転記しているだけの二重表現だったため廃止した（`§シート構成と意味性` `§対応記録 xlsx 責務分担表` は削除済み）。証跡は `/test {issueID}` が生成するエビデンス.xlsx（別ファイル）に一元化されている。エビデンス.xlsx と `evidence/before/`（xlsx に入らない実装前・操作前の証跡）は `/test` Phase G が共有フォルダ（`docs/.backlog_config.yml` の `report_dir` 配下の課題フォルダ）へコピーする（2026-10-06。廃止時に共有フォルダへの保存も一緒に無くなっていたため戻した）。

## § 人が読む欄の日本語・表示ラベル規約

**適用範囲**: xlsx・MD 成果物の人が読む欄に加え、**ユーザーへのチャット回答・Phase末尾確認プロトコル・バグ報告・調査結果の説明** も対象。成果物でも口頭でも同じ規約で書く（`/backlog` 系限定。`/sf-design` プログラム設計 JSON は `naming-convention-api-vs-label.md`、`/sf-memory` 業務文書は `sf-memory-quality.md §技術識別子禁止の原則`（より厳格）を参照）。

バグ・不具合・原因分析をユーザーに伝えるときは以下の順で説明する: **①前提・背景**（仕様上こうなっているはず）→ **②本来こうなるはず**（期待挙動）→ **③実際はこうなっている**（観測挙動）→ **④おそらく原因はこれ**（根拠付き）。

xlsx・MD 成果物の **人が読む欄**（概要・メリット・デメリット・採用方針・懸念事項・注意事項・リスク・調査結果サマリー等）は次のルールに従う:

- **オブジェクト・項目はオブジェクトラベル / 項目ラベルで書く**。API 名（`__c` 末尾の英語名）は補助として括弧書きで添えてよい
  - OK 例: 「渡航者マスタの『犯罪歴』項目（CriminalHistory__c）を新設して、preCheckModal で選択肢を保存する」
  - NG 例: 「`BusinessTraveler__c` に `CriminalHistory__c` を新設して `preCheckModal.js` で保存する」
- **日本語の自然な文章で書く**。英語の固有名詞をそのまま並べた箇条書きは禁止
  - OK 例: 「『はい』を選択しても判定結果は OK のまま進める」
  - NG 例: 「`PreCheckResult__c` is OK のまま push」
- **コンポーネント名はそのまま使ってよい**（Apex クラス・LWC・トリガー・Flow の名前は識別子なので英語のまま）
  - OK 例: 「PreCheckController.getInitData の SELECT 句に犯罪歴項目を追加」
  - ただしチャット出力（Phase 末尾サマリー・確認事項）は対象外: チャットではメソッド名・SOQL句・行番号を出さず、「事前チェック画面の初期表示処理」のように機能名で書く（鉄則§サマリーの書き方が優先）。本 OK 例は xlsx・MD 成果物の欄にのみ適用する
- **判断ポイント・受入条件・テスト項目** など機械的に解釈する欄も同じ規約（人が読む欄を兼ねるため）
- **例外（このルール対象外）**: 変更ファイル一覧（ファイル名列）・自動取得値・SOQL 句

**判定基準（迷ったら）**: 「3 ヶ月後の別担当者が、コードを見ずにこの 1 セルを読んで何の話か理解できるか」が分かれ目。「No」なら表示ラベル化が必要。

> オブジェクト・項目の表示ラベルは `docs/catalog/{standard|custom}/{Object}.md` または `docs/overview/org-profile.md` の用語集を参照。docs/ にも記載がなければ、`{ラベル不明}（API名: XXX__c）` の形式で暫定記入し、確認後に修正する。


---

## backlog 系プレースホルダー一覧

`/backlog` 系コマンド・エージェントで使用するプレースホルダー。共通ルール（`.claude/CLAUDE.md §テンプレート置換ルール`）と同じ規則でテキスト置換する。

| プレースホルダー | 種別 | 確定タイミング |
|---|---|---|
| `{issueID}` | 文字列 | `/backlog` Phase 0 |
| `{件名}` / `{件名_sanitized}` | 文字列 | `/backlog` Phase 0（investigation.md 生成時） |

> `{issueID}` は Backlog の課題キー（`[A-Z]{2,}-\d+`、例 `GF-341`）。`docs/knowledge/cases/{issueKey}.md` のファイル名で使う `{issueKey}` と**同一値**で、作業フォルダ・中間成果物系では `{issueID}`、cases ナレッジファイル名では `{issueKey}` と表記を使い分ける。

> `{report_dir}` / `{xlsx_create}` / `{xlsx_folder}` / `{evidence_dir}`（固定パス `docs/logs/{issueID}/evidence` に統一）・`.backlog_config.yml` の `xlsx_default` キーは対応記録.xlsx 廃止（2026-09-18）に伴い削除済み。`.backlog_config.yml` の `report_dir` キーは `/test` Phase G（証跡の共有フォルダ保存）が `share_evidence.py` 経由で使う（プレースホルダーとしては使わない）。
