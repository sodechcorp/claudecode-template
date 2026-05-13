# 途中フェーズからの再開ルーティング

`docs/logs/{issueID}/` 配下の既存成果物の有無に応じて再開可能フェーズをテキストで列挙して選択を促す:

- `validation-report.md` 存在 → 「Phase 4（実装）から / Phase 3.5（実装前検証）から / 中止 のどれにしますか？」
- `implementation-plan.md` 存在（validation-report.md なし） → 「Phase 3.5（実装前検証）から / Phase 3（実装方針確定）から / 中止 のどれにしますか？」
- `approach-plan.md` 存在（implementation-plan.md なし） → 「Phase 3（実装方針確定）から / Phase 2（対応方針確定）から / 中止 のどれにしますか？」
- `investigation.md` のみ存在 → 「Phase 2（対応方針確定）から / Phase 1.5（対応記録作成）から / 中止 のどれにしますか？」

選択されたフェーズの該当節へ進む。前フェーズの成果物は再生成せず保持する。
