# templates/common/ 索引

`templates/common/` はエージェントが実行時に Read する**共通実行手順・チェックリスト**を置く場所。
`spec/` との使い分け: **spec/ = 人が読む規約（CLAUDE.md から索引される）／ templates/common/ = エージェントが Phase 0 等で Read する実行手順**。新しい共通ルールを追加する場合、規約・原則なら `spec/`、エージェントの具体的な実行手順・チェックリストなら `templates/common/` に置く。

以下は全ファイルの一覧。「正本」列は、当該トピックについて本ファイルが単一の正規定義かどうかを示す（○ = 正本、△ = 一部委譲あり／他ファイルとスコープ分担、詳細は本文の参照節を参照）。

## Phase 0・エージェント基盤

| ファイル | 目的 | 正本 |
|---|---|---|
| `agent-phase0-template.md` | 新規エージェント追加時の Phase 0 冒頭ブロックのテンプレート | ○ |
| `sf-context-load-phase0.md` | `sf-context-loader` 呼び出し仕様（パラメータ・結果解釈・不確実マーカー運用） | ○ |
| `step-0c-template.md` | SF系エージェント共通の Step 0c（実装裏付け・出典確認・スコープ管理・不確実マーカーの要約＋各 spec への索引） | △（§1 実装裏付けは要約のみ・全文は `verify-implementation-spec.md`。§2-5 は自己完結） |
| `agent-cleanup-template.md` | `tmp_dir` を使うエージェントの Phase 最終クリーンアップ実装パターン | ○ |

## 品質・検証系（規約の詳細版・spec/ から委譲）

| ファイル | 目的 | 正本 |
|---|---|---|
| `verify-implementation-spec.md` | 実装裏付けルール全文（適用範囲・確認方法テーブル・調査尽くしゲート・追問反転ガード）+ backlog 固有 extras（追加ルール記入欄あり） | ○（サブエージェントから到達可能な唯一の正本。`.claude/CLAUDE.md` 側はメインスレッド向けの同内容） |
| `verify-source-attribution-spec.md` | 出典確認ルール（Backlog コメント・チャット履歴の出典帰属の確認手順） | ○ |
| `answer-scope-spec.md` | ユーザー回答時のスコープ管理（派生事項の分離・無断リファクタ禁止） | ○ |
| `uncertainty-marker-spec.md` | 不確実マーカーの正規定義（全エージェント共通の基本3種）。sf-analyst 系の追加5種は `spec/sf-memory-quality.md` に委譲 | ○（基本3種）／sf-analyst追加分は委譲 |
| `naming-convention-api-vs-label.md` | `/sf-design` プログラム設計 JSON 生成時の API名 vs 日本語ラベル使い分け | ○（`/sf-design` 限定。`/sf-memory` は `spec/sf-memory-quality.md`、`/backlog` は `templates/backlog/_README.md` が別途正本） |

## Backlog・運用チェックリスト系

| ファイル | 目的 | 正本 |
|---|---|---|
| `backlog-mcp-hygiene.md` | Backlog MCP 呼び出し時の作法（書き込み系ハードブロックとの付き合い方等） | ○ |
| `knowledge-reflux-formats.md` | `backlog-releaser.md` / `backlog.md §中断時の知見還流` が共有する追記フォーマット | ○ |
| `cases-format.md` | `docs/knowledge/cases/<案件キー>.md` の出力構造 | ○ |
| `completion-report-spec.md` | SF環境の状態に関わる完了報告のフォーマット | ○ |
| `new-metadata-permissions-checklist.md` | 新規メタデータ作成時の権限・基本設定チェックリスト（正本） | ○ |
| `phase07-hash-check-by-feature.md` | 変更のないコンポーネントをスキップするハッシュチェック手順 | ○ |
| `template-substitution-spec.md` | `{project_dir}` 等プレースホルダーのテキスト置換規則 | ○ |
| `docs-readme-template.md` | `docs/_README.md`（情報所在マップ）生成テンプレート | ○ |

## セキュリティ・安全確認系

| ファイル | 目的 | 正本 |
|---|---|---|
| `prod-readonly-check.md` | 本番組織 read-only チェック手順（release-preparer 等が使用） | ○ |
| `sandbox-alias-check.md` | Sandbox 接続確認（本番誤操作防止の必須チェック） | ○ |
| `shared-folder-protection.md` | 共有フォルダ（G:\ 等）への書き込み・削除時の警告フロー | ○ |
| `visual-confirmation-handoff.md` | ユーザーへの目視確認依頼時、レコードURL/ID/操作手順を添える運用ルール | ○ |

## 実装作法・その他ユーティリティ

| ファイル | 目的 | 正本 |
|---|---|---|
| `inline-script-hygiene.md` | Python/Bash インラインスクリプトの記述規約（単一物理行縛り等） | ○ |
| `tmp-file-rules.md` | 一時ファイルの作成・配置禁止ルール | ○ |
| `sf-config-charmap-note.md` | rare CJK 文字の LLM 自動補正対策（作成者名等の取得フロー） | ○ |
| `ask-user-question-spec.md` | AskUserQuestion の詳細スキーマ・NG例 | ○ |
| `playwright-sf-screen-ops.md` | Salesforce Sandbox での Playwright 画面操作共通手順 | ○ |

---

**運用で肥大化するファイル**: `verify-implementation-spec.md` / `verify-source-attribution-spec.md` は「追加ルール記入欄」を持ち、インシデント対応のたびに追記される。`answer-scope-spec.md` は `backlog-releaser` が自動追記する設計。

**索引の更新**: 新規ファイルを `templates/common/` に追加したら、この表に1行追加する。
