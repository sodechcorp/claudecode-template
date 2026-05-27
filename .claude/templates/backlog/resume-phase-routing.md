# 途中フェーズからの再開ルーティング

`docs/logs/{issueID}/` 配下の既存成果物の有無に応じて再開可能フェーズをテキストで列挙して選択を促す:

- `validation-report.md` 存在 → 「Phase 4（実装）から / Phase 3.5（実装前検証）から / 中止 のどれにしますか？」
- `implementation-plan.md` 存在（validation-report.md なし） → 「Phase 3.5（実装前検証）から / Phase 3（実装方針確定）から / 中止 のどれにしますか？」
- `approach-plan.md` 存在（implementation-plan.md なし） → 「Phase 3（実装方針確定）から / Phase 2（対応方針確定）から / 中止 のどれにしますか？」
- `investigation.md` のみ存在 → 「Phase 2（対応方針確定）から / Phase 1.5（対応記録作成）から / 中止 のどれにしますか？」

選択されたフェーズの該当節へ進む。前フェーズの成果物は再生成せず保持する。

### Phase 5/6 から Phase 1 完全やり直し

Phase 5 または Phase 6 で根本的な問題（原因誤特定・スコープ根本見直し等）が発覚し、Phase 1 からの再調査が必要な場合:

1. **既存成果物のアーカイブ**:
   - `docs/logs/{issueID}/` 配下の全 MD を `docs/logs/{issueID}/archive/v{N}/` に移動する
   - `N` は既存の archive フォルダ数 + 1（初回は v1）
   - `docs/logs/{issueID}/discussion-log.md` はアーカイブせず残存させ、「v{N} やり直し理由: {理由}」を追記してから続行

2. **Phase 1 から再起動**:
   - /backlog コマンドを再起動し、「既存 investigation.md が見当たらない場合の新規フロー」として Phase 1 から実施
   - やり直し理由は discussion-log.md に記録済みのため、investigator は冒頭で discussion-log.md を Read して経緯を把握してから調査を開始する

3. **ループ上限への影響**:
   - アーカイブした回数（v{N}-1）を discussion-log.md から算出してループ上限の通算カウントに含める
   - 通算で Phase 1 完全やり直しが 2 回以上に達した場合は、ユーザーに「課題の根本的な見直しが必要な可能性があります」と案内してから続行する
