# Agent Selection — エージェント選択・委譲ルール

タスクを受け取ったら以下の基準でエージェントに委譲する。複数該当する場合はタスクを分解して各エージェントに割り当てる（ただし工数見積系は L14 の強制集約が優先。タスク分解より前に `sf-effort-estimator` へ委譲する）。

## 主担当エージェント（ユーザーから直接指示を受ける）

| タスクの性質 | エージェント |
|---|---|
| コードレビュー / セキュリティ監査 / ドキュメントレビュー（設計書・要件定義書） | `reviewer` |
| 要件定義 / 設計書作成 / 設計レビュー / オブジェクト定義書 / 影響調査 / ユーザーストーリー | `sf-architect` |
| 一般調査 / メール下書き / 翻訳 / アドホック / その他秘書業務 | `assistant` |
| 工数計算 / 工数見積 / 工数 / effort / 見積 / 「何時間」「どのくらい」系の新規見積依頼（コマンド内外問わず） | `sf-effort-estimator` |

> **工数見積の強制集約**: `工数 / effort / 見積 / 何時間 / どのくらい` 等の語を含む依頼は、他エージェントが回答を始める前に必ず `sf-effort-estimator` に委譲する。例外なし。
>
> | 種別 | 判定 | 例 |
> |---|---|---|
> | **新規見積依頼** | 委譲 | 「この課題の工数を見積もって」「effort はどれくらい？」「何時間かかる？」 |
> | **再見積・更新** | 委譲 | 「scope が変わったので再見積して」「最新工数で見直して」 |
> | **過去案件参照付き見積** | 委譲 | 「過去の類似案件を参考に工数を見積もって」「LINK-123 と比較して工数を出して」 |
> | **見積結果の閲覧** | 除外 | 「過去の工数を確認したい」「温度感を見せて」「前回の見積結果を見せて」 |
> | **集計・参照** | 除外 | 「今月の工数合計は？」「過去 3 件の工数推移を表示して」 |

## Phase 0（sf-context-loader）を持つエージェント一覧

sf-architect / reviewer / assistant（SF条件付き）/ backlog-investigator / backlog-planner / backlog-implementer / backlog-tester / backlog-validator / backlog-releaser

## 保守特化エージェント（/backlog フロー内で Claude が自動委譲）

| 起動経路 | エージェント | 役割 |
|---|---|---|
| Phase 1 / option-similar-past-issue → investigator から Task 委譲 | `pattern-curator` | 過去完了課題の症状・対応実績を Backlog 全文検索して要約。Write 持たない |
| Phase 1 / option-second-opinion → investigator から Task 委譲 | `backlog-blind-second-opinion` | parent の調査結果に引きずられない独立仮説（blind）。単発・非並列のため main thread への引き上げ対象外 |
| Phase 1 → backlog.md（本体）から直接 Task 委譲（二段ネスト回避のため investigator 経由にしない。同一メッセージ並列発行はせず逐次実行） | `sf-context-loader`（knowledge-only モード → 通常モードの順） | 知識層・設計層コンテキストを取得し investigator へ渡す |
| Phase 2（A-2.5・`option-alternative-approaches` 採用時は案毎）→ planner から Task 委譲 | `sf-effort-estimator` | 工数見積を算出。単発・非並列かつ案毎に異なる入力が必要なため main thread への引き上げ対象外 |
| Phase 3（`option-validator-blind` 採用時のみ）→ backlog.md（本体）から直接 Task 委譲 | `backlog-blind-validator` | planner 完了後、implementation-plan.md を見ない独立実装案を生成 |
| Phase 3.5 → backlog.md（本体）から直接 Task 委譲（二段ネスト回避のため validator 経由にしない） | `regression-guard` | 変更ファイルの依存先・テストカバレッジ・影響再走査・過去修正履歴を一括確認。Write 持たない |
| Phase 3.5（UI 影響時のみ）→ backlog.md（本体）から直接 Task 委譲 | `ui-evidence-runner`（`mode: before-capture`） | 実装前の現状画面を自動撮影 |

> **investigator / planner の残存ネスト構造（意図的に据え置き）**: investigator は `pattern-curator`（option-similar-past-issue）・`backlog-blind-second-opinion`（option-second-opinion）を、planner は `sf-effort-estimator`（A-2.5・`option-alternative-approaches` 採用時は案 B・C 分も個別）をそれぞれ単発・非並列で Task 委譲する。`sf-effort-estimator` は案ごとに異なる入力（各案の概要・スコープ）が実行時に初めて確定するため、main thread が事前に一括取得することができない。いずれも「同一メッセージでの並列発行」を伴わない単発ネストであり、`auto-evidence-runner → ui-evidence-runner`（`/test`）と同型の安定パターンのため main thread への引き上げ対象外とした。不安定化が確認されているのは「同一メッセージでの複数 Agent/Task 同時発行」（旧 backlog-validator Step1+Step2-3、investigator 旧 Step0a+B-1）であり、こちらは解消済み。

## コマンド専用エージェント（内部処理からのみ起動・ユーザーの直接指示不可）

| 起動コマンド | エージェント |
|---|---|
| `/sf-memory` cat1〜cat6・cat6-global・cat8 / cat7（横断補完） | `sf-analyst-cat1〜cat3` / `sf-analyst-cat4-apex` / `sf-analyst-cat4-flow` / `sf-analyst-cat4-lwc` / `sf-analyst-cat5〜cat6` / `sf-analyst-cat6-global` / `sf-analyst-cat8` / `sf-org-analyst`（= cat7） |
| `/sf-memory` Phase 0 コンテキスト読込 | `sf-context-loader` |
| `/sf-design` 各ステップ | `sf-design-step1〜3` / `sf-design-writer` / `sf-screen-writer` / `sf-detail-design-writer` |
| `/sf-doc` 各ステップ | `sf-doc-overview-writer` / `sf-doc-objects-writer` |
| `/backlog` 各 Phase | `backlog-investigator` / `backlog-repro-runner` / `backlog-planner` / `backlog-implementer` / `backlog-tester` / `backlog-releaser` / `backlog-validator` |
| `/test` 各 Phase（証跡採取・レポート） | `auto-evidence-runner` / `ui-evidence-runner` / `test-spec-builder` |
| `/release`（本番リリース準備。`/backlog`・`/test` 完了後の独立段階） | `release-preparer` |
| blind 系（Task 経由のみ・親の情報を受け取らない） | `backlog-blind-second-opinion` / `backlog-blind-final-verifier`（起動元は各々の親エージェント） / `backlog-blind-validator`（起動元は backlog.md 本体） |

> `sf-design-step2` の委譲先（順番厳守）: ① `sf-screen-writer`（画面系: LWC/画面フロー/Aura/VF）→ ② `sf-design-writer`（Apex系・機能一覧、①の結果を集約）の順に両方委譲
