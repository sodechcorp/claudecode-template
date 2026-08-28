# 新規エージェント Phase 0 テンプレート（sf-context-loader 経由）

新規エージェントを追加する際は、以下のテンプレートに従って **Phase 0** と **Step 0c** を冒頭に設ける。

## 適用基準

- **設ける**: SFプロジェクトの状態（オブジェクト定義・設計書・要件・業務フロー）を知っていれば精度が上がるエージェント → Phase 0・Step 0c ともに設ける
- **不要**: 汎用調査・ファイル生成のみのエージェント → Phase 0・Step 0c ともに不要
- **条件付き**: SF 固有タスクとは限らないエージェント（assistant 等）は「SF 固有キーワードを含む場合のみ実行」と記述する。Step 0c も同じ条件判定に従わせる（判定 → 該当時のみ Read）

呼び出し仕様: `.claude/templates/common/sf-context-load-phase0.md` 参照

**Step 0c の書式**: 新規エージェントは [`step-0c-template.md`](./step-0c-template.md) への 1 ファイル参照（下記テンプレートの blockquote 行）を既定とする。reviewer.md / sf-architect.md と同じ方式（4 ルールをまとめて索引した 1 ファイルを Read）で、ルール改訂時の横展開漏れ（過去に発生した「4系統分裂」drift）を防げる。backlog 系・release-preparer.md・assistant.md は 4 ファイルのインライン列挙方式で実装済みだが、これは既存の分裂修正時に内容を揃えるに留めたもの。既存エージェントの書式統一は本テンプレート整備のスコープ外とし、新規エージェントのみ本テンプレートの方式に従う。

## Phase 0 テンプレート

```markdown
## Phase 0: SFコンテキスト読込（sf-context-loader 経由）

タスク開始前に sf-context-loader を呼び出し、関連 docs の要約を取得する。

\`\`\`
task_description: 「{ユーザー指示 / タスク概要}」
project_dir: {プロジェクトルートパス。不明な場合はカレントディレクトリ}
focus_hints: []
\`\`\`

- **「該当コンテキストなし」が返った場合**: 共通仕様に従い、最低限 docs/_README.md を 1 回 Read（存在する場合のみ）してドキュメント体系・用語集の所在を把握してから次フェーズへ進む（docs/ 未整備または SF 無関係）
- **エラー / タイムアウトが発生した場合**: 呼び出し仕様の「エラー / タイムアウト」節に従い、最低限 `docs/_README.md` + `docs/overview/org-profile.md` を直接 Read してフォールバックしてから次フェーズへ進む。**コンテキスト未取得のままプロジェクト固有の用語・構成を推測で扱わない**（断定する場合は不確実マーカーを付す）
- **関連コンテキストが返った場合**: 関連オブジェクト・F-番号・UC・注意点を以降の作業の判断材料として保持する

> **Step 0c: CRITICAL ルール読込** — [`step-0c-template.md`](../templates/common/step-0c-template.md) を Read する（実装裏付け・出典確認・スコープ管理・不確実マーカーの 4 ルール）

---
```
