# Agent Selection — エージェント選択・委譲ルール

タスクを受け取ったら以下の基準でエージェントに委譲する。複数該当する場合はタスクを分解して各エージェントに割り当てる。

## 主担当エージェント（ユーザーから直接指示を受ける）

| タスクの性質 | エージェント |
|---|---|
| Apex / LWC / Flow / メタデータ実装 / 新規開発 / 機能改修 / デプロイ | `sf-dev` |
| テスト計画 / テストケース作成 / バグ調査 / UAT支援 / 品質確認 | `qa-engineer` |
| コードレビュー / セキュリティ監査 / PRレビュー支援 / ドキュメントレビュー（設計書・要件定義書） | `reviewer` |
| 要件定義 / 設計書作成 / 設計レビュー / オブジェクト定義書 / 影響調査 / ユーザーストーリー | `sf-architect` |
| データ移行 / CSVマッピング / Data Loader / SOQL最適化 / バルク処理 / データクレンジング | `data-manager` |
| 外部API連携 / REST・SOAP / Named Credentials / Platform Events / MuleSoft | `integration-dev` |
| 一般調査 / メール下書き / 翻訳 / アドホック / その他秘書業務 | `assistant` |
| 工数 / effort / 見積 / 「何時間」「どのくらい」系の新規見積依頼（コマンド内外問わず） | `sf-effort-estimator` |

> **工数見積の強制集約**: `工数 / effort / 見積 / 何時間 / どのくらい` 等の語を含む依頼は、他エージェントが回答を始める前に必ず `sf-effort-estimator` に委譲する。例外なし。
>
> | 種別 | 判定 | 例 |
> |---|---|---|
> | **新規見積依頼** | 委譲 | 「この課題の工数を見積もって」「effort はどれくらい？」「何時間かかる？」 |
> | **再見積・更新** | 委譲 | 「scope が変わったので再見積して」「最新工数で見直して」 |
> | **過去案件参照付き見積** | 委譲 | 「過去の類似案件を参考に工数を見積もって」「LINK-123 と比較して工数を出して」 |
> | **見積結果の閲覧** | 除外 | 「工数ログを開いて」「effort-log を確認して」「前回の見積結果を見せて」 |
> | **集計・参照** | 除外 | 「今月の工数合計は？」「過去 3 件の工数推移を表示して」 |

## Phase 0（sf-context-loader）を持つエージェント一覧

sf-dev / sf-architect / qa-engineer / reviewer / data-manager / integration-dev / assistant（SF条件付き）/ backlog-investigator / backlog-planner / backlog-implementer / backlog-tester / backlog-validator / backlog-releaser

## 保守特化エージェント（/backlog フロー内で Claude が自動委譲）

| 起動経路 | エージェント | 役割 |
|---|---|---|
| Phase 1 / option-similar-past-issue → investigator から Task 委譲 | `pattern-curator` | 過去完了課題の症状・対応実績を Backlog 全文検索して要約。Write 持たない |
| Phase 3.5 → validator から Task 委譲 | `regression-guard` | 変更ファイルの依存先・テストカバレッジ・影響再走査・過去修正履歴を一括確認。Write 持たない |

## コマンド専用エージェント（内部処理からのみ起動・ユーザーの直接指示不可）

| 起動コマンド | エージェント |
|---|---|
| `/sf-memory` cat1〜cat6・cat8 / 横断補完 | `sf-analyst-cat1〜cat3` / `sf-analyst-cat4-apex` / `sf-analyst-cat4-flow` / `sf-analyst-cat4-lwc` / `sf-analyst-cat5〜cat6` / `sf-analyst-cat8` / `sf-org-analyst` |
| `/sf-memory` Phase 0 コンテキスト読込 | `sf-context-loader` |
| `/sf-design` 各ステップ | `sf-design-step1〜3` / `sf-design-writer` / `sf-screen-writer` / `sf-detail-design-writer` / `sf-doc-overview-writer` / `sf-doc-objects-writer` |
| `/backlog` 各 Phase | `backlog-investigator` / `backlog-planner` / `backlog-implementer` / `backlog-tester` / `backlog-releaser` / `backlog-validator` |
| blind 系（Task 経由のみ・親の情報を受け取らない） | `backlog-blind-second-opinion` / `backlog-blind-final-verifier` / `backlog-blind-validator` |

> `sf-design-step2` の委譲先（順番厳守）: ① `sf-screen-writer`（画面系: LWC/画面フロー/Aura/VF）→ ② `sf-design-writer`（Apex系・機能一覧、①の結果を集約）の順に両方委譲
