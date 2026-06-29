# /backlog À la carte option 仕組み

`/backlog` コマンドは「ベース処理（最小限・全課題必須）」と「オプション（必要時のみ実行）」の組み合わせで動作する。重い処理・細かいチェックを **必要な時だけ呼ぶ** ことで、軽い課題は軽く・重い課題は徹底的に対応できるようにしている。

このファイルは、各 backlog 系エージェント（investigator / planner / validator / implementer / tester / releaser）の **Step 0** から共通参照される。

---

## ディレクトリ構成

```
.claude/templates/backlog/
├── _README.md                    # このファイル（仕組み説明・Step 0 共通ロジック）
├── _index-phase1.md              # Phase 1 用判定情報
├── _index-phase2.md              # Phase 2 用判定情報
├── _index-phase3.md              # Phase 3 用判定情報
├── _index-phase3-5.md            # Phase 3.5 用判定情報
├── _index-phase4.md              # Phase 4 用判定情報
├── _index-phase5.md              # Phase 5 用判定情報
├── _index-phase5-5.md            # Phase 5.5 用判定情報
├── _index-phase6.md              # Phase 6 用判定情報
├── xlsx-setup.md                 # Phase 1.5 対応記録ファイル作成手順
├── deploy-skip-judgment.md       # デプロイ適否の判定基準
├── resume-phase-routing.md       # 途中フェーズからの再開ルーティング
├── test-fail-routing.md          # Phase 5 NG 時の戻り先テーブル
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
- backlog-investigator / backlog-planner — **knowledge-only モード**（sf-context-loader を `focus_hints: ["knowledge-only"]` で呼び出し、knowledge/ ファイルの選択的読込のみを行う。docs/ 全件読みは別途 Step C / Phase B で実施するため重複しない）
- backlog-validator / backlog-implementer / backlog-tester / backlog-releaser — **通常モード**（sf-context-loader を標準 focus_hints で呼び出す）

### Step 0b: 関連オプションの判定（全エージェント必須）

1. **このフェーズ用の `_index-phase{N}.md` を Read**（Phase 1 なら `_index-phase1.md`、Phase 3.5 なら `_index-phase3-5.md`）
2. 各オプションについて以下の 3 分岐で判定:

   | 判定 | 条件 | 挙動 |
   |---|---|---|
   | **実行** | `auto-execute-when` のいずれかにマッチ | そのまま実行（ユーザー確認なし） |
   | **スキップ** | `auto-skip-when` のいずれかに明確マッチ | **黙ってスキップ**（成果物末尾にスキップ理由を 1 行記録するのみ・ユーザー確認なし） |
   | **判断不能** | どちらにもマッチしない / グレー | オプションに `default-when-uncertain: skip` が設定されていれば**黙ってスキップ**（理由「判断不能 + default skip」を成果物末尾に記録）。未設定または `execute` の場合は**実行に倒す**（ユーザー確認なし） |

4. **実行決定したオプションのみ** `options/option-{name}.md` を Read して実行
5. 各オプションの結果を成果物（`investigation.md` / `approach-plan.md` / `validation-report.md` / `test-report.md` 等）に統合
6. スキップしたオプションは成果物末尾に「スキップ理由」付きで記録

### オプション実行ログの書式

各 Phase の成果物 MD の末尾に `## オプション実行ログ` セクションを設ける。スキップしたオプションは `- [SKIP] {option-name}: {スキップ判定条件}` の形式で記録する。実行したオプションは `- [EXEC] {option-name}: {実行結果の要旨 1 行}` の形式で記録する。この書式に従うことで、後続 Phase のエージェントがオプション実行状況を確認できる。

### 重要原則

- **迷ったら実行**（既定）: グレー判定はスキップではなく実行に倒す（取り逃しを防ぐ）
- **例外: 高コストオプションの `default-when-uncertain: skip`**: `estimated-cost: 重` かつ実行条件がキーワードヒット型のオプション（subagent 起動・本番 SELECT・全件探索系）は、`default-when-uncertain: skip` を明示することで「グレー → スキップ」を選べる。`auto-execute-when` がヒットすれば従来通り実行されるため、明示的な実行シグナルがある時のみ起動する形になる
- **オプション判定でユーザーに確認しない**: 実行もスキップも黙って実施。スキップ判定は成果物末尾に理由を 1 行記録するのみ。判定の正誤はユーザーが成果物を見て指摘できる
- **ユーザー確認はフェーズ末の業務判断のみ**: 過去データの扱い・業務ルール解釈・受入条件・適用範囲の確認に限る。実装側で判別できる事項（テストクラス追加・命名・grep して確認するだけの調査・既存パターン踏襲・カバレッジ要件）は確認に出さない
- **option カタログの選択は意味のあるシグナルに基づく**: `auto-execute-when` / `auto-skip-when` は「課題内容・変更対象・規模」から評価可能な条件のみ

#### ⚠️ バグ非自明における徹底調査ゲート

種別が**バグかつ非自明**（タイポ修正・ラベル変更等の典型的自明ケース以外）の場合、以下が上記「迷ったら実行」より優先して適用される:

- **原因特定系オプションは `auto-execute-when` ヒット有無に関わらず実行側へ倒す**: category A（常時実行寄り: option-symptom-reverification / option-multi-cause-hypothesis / option-counter-evidence-search / option-causal-chain-analysis / option-apex-debug-log / option-cross-record-comparison / option-error-message-reverse-lookup / option-assumption-listing）および option-reverse-grep は、明示的なキーワードシグナルがなくても実行する
- **カタログに無い調査手段も自律的に実行**: オプションは最低限の床。バグ非自明では、カタログ外の調査方法も investigator 自身が発想して実行してよい（実行ログに `[EXEC] adhoc-{名前}` で記録）
- **コスト最適化の適用対象は「自明ケース・追加要望・その他」のみ**: `default-when-uncertain: skip` の軽量化バイアスはバグ非自明に適用しない（軽量課題・追加要望・その他は従来通り）

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

それ以外のオプションは parent 内実行で OK（blind 性が要件でないため）。

---

## メンテルール

### option を新規追加する時

1. `options/option-{name}.md` を作成（実行手順のみ・判定情報は持たない）
2. 該当 Phase の `_index-phase{N}.md` にエントリ追加（name / description / auto-execute-when / auto-skip-when / ask-user-prompt / category / estimated-cost）
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

現状は **手動メンテ**。オプションが揃って判定パターンが安定したら、`scripts/python/backlog-options/build_index.py` などの自動生成スクリプトを後付けで導入する。先に自動化すると判定情報のフォーマット制約が増えて柔軟性が落ちるため、現段階では手動を選択している。

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
- 接続先確認・Sandbox デプロイ（Phase 6 は Sandbox リリース専用）
- 対応記録ファイル作成（簡易/詳細選択は AskUserQuestion で現状維持）
- エビデンスファイル作成（簡易/詳細選択は AskUserQuestion で現状維持）

詳細は各エージェント定義（`backlog-investigator.md` 等）を参照。

---

## §調査責務の境界

各 Phase で「何をユーザーに問い、何を自分で確認するか」の線引き。特に Phase 1（investigator）に適用。

| 分類 | 内容 | 判断基準 |
|---|---|---|
| **ユーザーに出してよい（Q 番号 or テキスト依頼）** | (a) 業務判断（対応方針が変わる Q）/ (b) ClaudeCode が本当にアクセスできない外部データ（本番限定実値・認証必須リンク・スクショ実体・別 SF 組織設定） | 自分のツールでは取得不可能か？ |
| **絶対に委ねない（自分で確認）** | 調査方法・着眼点（「ログを見るべきか」「どこを grep するか」）/ Sandbox で再現可能な事象 / コード・メタデータで判明する事実 / Apex ログで判明する実行時挙動 / 類似レコードとの差分 | 自分のツール（Read/Grep/Bash/sf CLI/WebFetch）で確認できるか？ |

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

各 Phase 終了時、エージェントは以下のテキストブロックを出力してユーザの確認を待つ。AskUserQuestion は使わず、テキスト会話形式とする（承認判定ルールは本節 §承認判定 参照）。

### 出力テンプレート

```
【Phase {N} 完了サマリー】
（フェーズ別の型に従って書く。詳細は §サマリーの書き方 参照）

【確認事項】
特に確認事項はありません
（業務判断が必要な場合のみ ① ② ③ で列挙・最大 3 件・Q 番号は昇順）

【次へ】
Phase {N+1} に進んでよろしいですか？（または Phase X に戻る必要がありますか？）
```

### §サマリーの書き方（フェーズ別）

> **書き方の鉄則**（全フェーズ共通）:
>
> - **先頭に結論を1文**。「で、結局どうなの」が最初の1行で分かるように書く。
> - **自然な日本語・人間向け**。メソッド名・SOQL・API名を地の文に並べない。オブジェクト/項目は **§人が読む欄規約** に従いラベルで書き、API名は括弧補助のみ（コンポーネント名＝Apexクラス/LWC名は識別子なのでそのまま可、ただし羅列しない）。
>   - OK 例: 「渡航者マスタに『犯罪歴』項目を新設して、事前チェック画面で選んだ内容を保存するようにします」
>   - NG 例: 「`BusinessTraveler__c` に `CriminalHistory__c` を足して `preCheckModal.js` で保存」
> - **ダラダラ書かない**。技術的詳細は成果物（MD/xlsx）に置き、チャットは要点だけ。

**Phase 0・1.6・3.5・4・5・6**（調査/対応/実装方針以外）:
3〜5行で成果物の本質・主な発見・次フェーズへの引き渡し要点を要約する（従来どおり）。

---

**Phase 1（調査）**:

まず「今どうなっていて、なぜそうなっているか、お客さんは何を求めているか」が1読で分かるように書く。

```
【Phase 1 完了サマリー】
（結論1文: 今回の課題の本質を一言で。例:「〇〇機能で、条件Aのときに期待した処理が走らない問題です。」）

■ 課題の概要: どんな機能・画面の話か、どういう業務場面で使われているか、なぜ今回起票されたか
  （課題を全く知らない人でも「何の話をしているか」が分かる説明。背景・経緯も含めて丁寧に書く）
■ 前提・背景: 現状の仕様・設定上どう動くことになっているか
■ 実際こうなっている: 観測された現象（根拠: ファイル名・Backlog コメント等）
  （バグ系は「本来こうなるはず → 実際はこうなっている → 原因はここ」の3段で書く）
■ お客さんの要望: どういう仕様にしてほしいと言っているか（出典確認済みの場合のみ断定。未確認は [要確認] を付ける）
```

---

**Phase 2（対応方針）**:

「前フェーズの状況を踏まえて、どういう対応をすればどうなるか、なぜそれで実現できるか」が1読で分かるように書く。

```
【Phase 2 完了サマリー】
（結論1文: 採用方針の本質を一言で。例:「〇〇を△△に変えることで、お客さんの要望を満たす形になります。」）

■ 前提（Phase 1 のまとめ）: 現状と要望を1行で再掲（このフェーズ単独で文脈が通るように）
■ 行う対応: こういう変更をします
■ 結果こうなる: そうすれば、こういう仕様・挙動になります
■ 根拠: なぜそれで実現できるか（「〇〇が△△するから」——仕様・設定・既存実装に基づく）
```

---

**Phase 3（実装方針）**:

「どこをどう直すと、最終的にどう動くか」がエンドツーエンドで1読で分かるように書く。

```
【Phase 3 完了サマリー】
（結論1文: 変更の全体感を一言で。例:「〇〇コンポーネントを中心に△件のファイルを修正します。」）

■ 前提（Phase 2 のまとめ）: 合意した対応方針を1行で再掲
■ 修正箇所: どのコンポーネント/ファイルをどう直すか（ファイル名のみ可、パス羅列不要）
■ 変わること: 修正によって直接変わる挙動
■ 最終挙動: ユーザー目線で最終的にどう動くか（「〇〇したら△△できるようになります」の形で）
```

### 確認事項の選定基準

> **原則: 迷ったら 0 件。確認事項を埋めるために質問を作るのは禁止。**

- **書いてよい**: 業務判断が分かれる点・スコープ判断・Q 答えと方針の整合性・実装で新規発見した影響
- **書かない**: テストクラス追加要否・命名・既存パターン踏襲・カバレッジ要件（実装側で判断する事項）・「採用案を確定してください」（次へ確認で兼ねる）・抽象的な文言（「念のため〇〇」「適切か確認」「問題ないか確認」）
- **件数**: 0〜3 件。0 件が正常。1〜3 件は例外（業務判断が本当に割れる場合のみ）

### 文言統一

- 0 件時の文言: **「特に確認事項はありません」**（validator の「全ステップ異常なし」は validation-report.md 総合判定欄にのみ記載し、Phase 末尾の確認事項表記は「特に確認事項はありません」に統一）
- 確認列挙の番号: `①` `②` `③`（半角 1. 2. 3. ではない）
- 「次へ」表現: 「Phase {N+1} に進んでよろしいですか？」（「進みますか」「進んでいい？」等は不可）

### 承認判定（厳格化・必須）

> **原則: 確信できなければ次フェーズに進まない。迷ったら確認を出し直す。**

**承認とみなすもの（明示承認のみ）**:
直前の「Phase {N+1} に進んでよろしいですか？」に対する肯定の意思表示（「OK」「進んで」「はい進めて」「承認」等、進行を肯定する明確な語）。

**承認とみなさないもの（非承認シグナル — 次フェーズに進んではいけない）**:
- **質問・確認**: 「本当に？」「どっち？」「これでいい？」等
- **相槌・短い感嘆**: 「ha」「うん」「なるほど」「ふむ」「ほう」等、進行肯定が読み取れない発話
- **別タスク依頼**: 「工数計算して」「見積もって」「〇〇を調べて」「〇〇を修正して」等の独立した作業依頼。特に**工数・見積依頼は承認ではなく `sf-effort-estimator` 委譲対象**（`.claude/spec/agent-routing.md` 参照）。依頼を処理した後、改めて「Phase {N+1} に進んでよろしいですか？」を出し直す。
- **一語の曖昧返答全般**: 「ok」「ふむ」単体等、文脈から進行肯定が確実に読み取れない語

**別タスク混在時のルール**:
ユーザー返答が「工数計算して」のような独立タスクを含む場合、それは**直前フェーズへの承認を兼ねない**。タスク完了後に承認プロトコルを再提示する。フェーズ承認と別タスクを同時に処理してはいけない。

**Phase 3.5→4 は特に厳格に**:
Phase 3.5→4 の境界はファイル編集（実装）に入る唯一のゲート。確信できない返答はすべて非承認として扱い、必ず「Phase 4 に進んでよろしいですか？」を改めて提示してから次フェーズへ進む。

### discussion-log.md への追記（確認プロトコル直後・必須）

Phase 末尾確認プロトコルの出力ブロックを出力した**直後**（ユーザーの返答を待つ前）に、`docs/logs/{issueID}/discussion-log.md` へ当該 Phase の議論を追記する。

> 記録仕様・フォーマット・何を残すか: [discussion-log-spec.md](discussion-log-spec.md) を参照

**追記が必要な内容（Phase 末尾時点）**:
- 当該 Phase でユーザーから出た指摘・却下・補足（生引用に近い形）
- エージェントが提示した案の中で却下されたもの（却下理由付き）
- 調査・実装中に判明した重要な発見（後 Phase に影響するもの）
- 方針変更の経緯（何が→何に変わった・理由）

**追記が不要な内容**:
- Q番号テーブルの内容（approach-plan.md 側に記録済みのため重複不要）
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
3. **approach-plan.md まで遡る場合**: Phase 2 の Phase A 確認プロトコルから再開し、改版履歴テーブルに変更経緯を追記する
4. **差し込みが「Phase 6 に到達しない」ことを意味する場合**（例: 「客都合で中断」「手動対応へ切替」「リリース省略」等）: [backlog.md §中断時の知見還流](../../commands/backlog.md) を案内し、知見の部分還流を実行してから終了する

---

## §compact 跨ぎ復元プロトコル

/compact 後の再開時に失われる情報とその復元先:

| 変数 | 永続化先 | 復元方法 |
|---|---|---|
| `{issue_type}` | investigation.md フロントマター `issue_type:` | Phase 0d で Read |
| `{xlsx_folder}` | investigation.md フロントマター `xlsx_folder:` | Phase 0d で Read |
| `{evidence_dir}` | investigation.md フロントマター `evidence_dir:` | Phase 0d で Read |
| `{light_mode}` | investigation.md フロントマター `light_mode:` | Phase 0d で Read |

**運用ルール**: Phase 1.5 で xlsx_folder / evidence_dir が確定した時点で、`xlsx-setup.md` §1.5.3（「作成する」の場合）または「作成しない」手順（`backlog.md` に記載）に従い investigation.md フロントマターを必ず更新する。`--light` 時は `backlog.md` 記載の手順で更新する。自動フォールバック（docs/logs/ への書き出し）は `/test` でのフォールバック誤発動の原因になるため、この手順のスキップは禁止。フロントマター例:
```yaml
---
issue_id: XXX-123
issue_type: bug
xlsx_folder: C:/work/output
evidence_dir: docs/logs/XXX-123/evidence
light_mode: false
---
```

/backlog コマンド再起動後の Phase 0d では、investigation.md のフロントマターから上記変数を読み込んで復元する。

---

## §AskUserQuestion の使用ルール

/backlog コマンド体系では原則としてテキスト会話でフェーズ進行する（AskUserQuestion は使わない）。

**例外として AskUserQuestion を使ってよいケース**（以下のみ）:
1. **Phase 0 再開 Phase 選択**: コマンド起動時に既存の investigation.md を検出した場合の「どこから再開するか」の選択（クリック式の方が誤操作防止になる）
2. **Phase 1.5 xlsx 作成要否・フォルダパス確定**: フォルダパス選択はクリック UX が有用
3. **Phase 3 xlsx スクリプト失敗時**: 3択（続行/再試行/中止）の誤操作防止

上記以外でユーザーに選択を求める場合は、必ずテキスト会話で行う。validator の issueID 解決も、候補が3件以下なら「`XXX-1`、`XXX-2`、`XXX-3` のどれを対象にしますか？」とテキストで確認する。

---

## §シート構成と意味性

対応記録 xlsx は以下の **2 シート**で構成される。各シートは「何の問いに答えるか」が明確に分かれている。

| # | シート名 | 答える問い | 主なセクション |
|---|---|---|---|
| 1 | 課題と対応方針 | この課題は何で・なぜこの方針を選んだか・いつ誰が動いたか | 課題の整理 / 経緯・対応方針 / 対応経緯タイムライン |
| 2 | 対応内容 | 実際にどのコンポーネントのどこをどう修正したか・テスト NG の経緯 | 実施した対応 / 変更を加えた資材一覧 / Before/After / NG対応履歴 |

> **エビデンス.xlsx（別ファイル）**: ClaudeCode が自動実行したテストの結果証跡（SOQL / Apex Test / CLI / メタデータ確認）。UI 手動確認も含む期待/実際/判定の詳細を保持する。Phase 4 完了後に `/test {issueID}` が生成する。

---

## §対応記録 xlsx 責務分担表

各 Phase ・エージェントが対応記録 xlsx に書き込む内容の全体マップ。`update_records.py` コマンドは `{xlsx_folder}` が設定されている場合のみ実行する。

| シート | セクション | 担当 Phase / 実行主体 | コマンド |
|---|---|---|---|
| 課題と対応方針 | 課題の整理（ID/件名/優先度・期限/種別/ステータス/課題の内容・詳細/原因・現状） | Phase 3 / ハーネス直実行 | `create_records.py` 一括生成 |
| 課題と対応方針 | 経緯・対応方針（対応方針（結論）/方針決定の経緯・根拠） | Phase 3 / ハーネス直実行 | `create_records.py` 一括生成 |
| 課題と対応方針 | 対応経緯タイムライン No1-3 | Phase 3 / ハーネス直実行 | `create_records.py` 一括生成 |
| 課題と対応方針 | 対応経緯タイムライン No4〜 | Phase 3.5/4/5/6 / 各エージェント | `timeline --phase X` |
| 課題と対応方針 | ステータス更新（完了） | **Phase 6 末 / ハーネス直実行** | `cell --label "ステータス" --value "完了" --force` |
| 課題と対応方針 | ステータス更新（中断中） | **中断時パス / ハーネス直実行** | `cell --label "ステータス" --value "中断中" --force` |
| 対応内容 | 実施した対応 / 変更を加えた資材一覧 / Before/After | **Phase 4 末 / ハーネス直実行** | `content-from-md --summary implementation-summary.md` |
| 対応内容 | NG対応履歴（/test NG 修正ループ記録） | Phase 5 / tester・/test judge_results.py | `ng-history` |
| エビデンス.xlsx（別ファイル） | 証跡（SOQL/スクショ）正本・期待/実際/判定の詳細 | /test が generate_evidence_xlsx.py で自動生成、judge_results.py が実装後記入 | — |

> **verify ゲート**: Phase 4 末（`content-from-md` 直後）に `verify --stage pre-release` でブロック確認、Phase 6 末（`cell 完了` 直後）に `verify --stage final --status-expected 完了` で最終確認を実施する。NG は未充足枠を列挙して exit 2。

> **注**: 対応記録.xlsx のシート構成は **課題と対応方針 / 対応内容 の2シートのみ**。以下のシートは廃止済み: リリース・ロールバック（patch_template_v8 で削除。人間がデプロイ実施するため Claude 非関与）/ 残対応・懸念・保留（廃止。残対応はエビデンス.xlsx または MD での管理に集約）/ テスト・検証（廃止。証跡はエビデンス.xlsx に集約、実装後記入は judge_results.py が担当）/ 調査・影響範囲・サマリー・経緯・対応方針（廃止。課題と対応方針シートのセクションに統合）。影響確認チェックリストは patch_template_v9 で廃止済み（影響範囲テーブルの「問題ない根拠・対応内容」列に統一）。
>
> **注**: xlsx・MD 成果物の全ての値書き込み欄は §人が読む欄の日本語・表示ラベル規約に従うこと（ファイル名列等の例外を除く）。

---

## § 人が読む欄の日本語・表示ラベル規約

**適用範囲**: xlsx・MD 成果物の人が読む欄に加え、**ユーザーへのチャット回答・Phase末尾確認プロトコル・バグ報告・調査結果の説明** も対象。成果物でも口頭でも同じ規約で書く。

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
- **判断ポイント・受入条件・テスト項目** など機械的に解釈する欄も同じ規約（人が読む欄を兼ねるため）
- **例外（このルール対象外）**: 変更ファイル一覧（ファイル名列）・自動取得値・SOQL 句

**判定基準（迷ったら）**: 「3 ヶ月後の別担当者が、コードを見ずにこの 1 セルを読んで何の話か理解できるか」が分かれ目。「No」なら表示ラベル化が必要。

> オブジェクト・項目の表示ラベルは `docs/catalog/{standard|custom}/{Object}.md` または `docs/overview/org-profile.md` の用語集を参照。docs/ にも記載がなければ、`{ラベル不明}（API名: XXX__c）` の形式で暫定記入し、確認後に修正する。

> **方針比較テーブルは特にコンパクト性が求められる**（概要 60 字・メリット/デメリット 30 字・工数 20 字以内）。詳細は `backlog-planner.md §対応方針` を参照。

---

## backlog 系プレースホルダー一覧

`/backlog` 系コマンド・エージェントで使用するプレースホルダー。共通ルール（`.claude/CLAUDE.md §テンプレート置換ルール`）と同じ規則でテキスト置換する。

| プレースホルダー | 種別 | 確定タイミング |
|---|---|---|
| `{report_dir}` | パス | `.backlog_config.yml` 読み込み時 |
| `{xlsx_folder}` | パス | `/backlog` Phase 1.5 |
| `{evidence_dir}` | パス | Phase 1.5 連動 |
| `{issueID}` | 文字列 | `/backlog` Phase 0 |
| `{件名}` / `{件名_sanitized}` | 文字列 | Phase 1.5 |

> `{issueID}` は Backlog の課題キー（`[A-Z]{2,}-\d+`、例 `GF-341`）。`docs/knowledge/cases/{issueKey}.md` のファイル名で使う `{issueKey}` と**同一値**で、作業フォルダ・中間成果物系では `{issueID}`、cases ナレッジファイル名では `{issueKey}` と表記を使い分ける。
