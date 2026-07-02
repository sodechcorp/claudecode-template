# option-org-drift-check

## 何をするか

本番組織の状態が、今回リリースするメタデータの想定と乖離していないか（＝自分たちの知らないところで誰かが本番を直接触っていないか）を **階層型（軽→深）** で確認する。組織間メタデータ比較機能はテンプレートに存在しないため、Tier1 の軽量スキャンで対象を絞り込み、疑わしいものだけ Tier2 で本番から実際に取得して差分を見る。

**本番に対しては read-only のみ**。[prod-readonly-check.md](../../common/prod-readonly-check.md) を先に実施してから本オプションを実行する。

## 実行手順

### Tier 1: 軽量スキャン（全リリース対象コンポーネントに実施）

1. release-preparer Phase 1 で確定した資材マニフェスト（API 名一覧）を用意する
2. 本番組織のメタデータ一覧を取得し、更新日時・更新者を確認する:
   ```bash
   sf org list metadata --metadata-type ApexClass --target-org "$PROD_ALIAS" --json
   sf org list metadata --metadata-type Flow --target-org "$PROD_ALIAS" --json
   # リリース対象に含まれる種別のみ実行（全種別を舐めない）
   ```
3. 出力の `lastModifiedDate` / `lastModifiedByName` を確認し、以下のいずれかに該当するコンポーネントを「痕跡あり」としてマークする:
   - 最終更新日が **base コミット日時（release-preparer Phase 1 で特定した差分起点）より後**
   - 最終更新者が **今回のリリース担当者・実装者以外**
4. 痕跡なしのコンポーネントは Tier 2 をスキップして「ドリフトなし」と記録する

### Tier 2: 深掘り（Tier 1 で痕跡ありのコンポーネントのみ）

1. 痕跡ありコンポーネントのみを対象に、一時ディレクトリへ本番から retrieve する（**`force-app/` には絶対に取得しない**）:
   ```bash
   mkdir -p "{tmp_dir}/prod-drift-check"
   sf project retrieve start --metadata "ApexClass:{クラス名}" --target-org "$PROD_ALIAS" --output-dir "{tmp_dir}/prod-drift-check" --json
   ```
2. 取得結果と現在の `force-app/` 配下の該当ファイルを diff する:
   ```bash
   diff "{tmp_dir}/prod-drift-check/force-app/main/default/classes/{クラス名}.cls" "force-app/main/default/classes/{クラス名}.cls"
   ```
3. diff の内容を評価する:
   - **差分なし**: 誰かが触ったが結果的に今の Sandbox/リポジトリ内容と一致 → 「痕跡あるが実害なし」
   - **差分あり かつ 今回のリリース内容と非干渉**（無関係な別ロジックの変更）: 「他者変更あり・要確認（リリースで上書きする点をユーザーに警告）」
   - **差分あり かつ 今回のリリース内容と重なる**（同一メソッド・同一項目）: 「競合・要人間判断」（最重要警告）
4. 一時ディレクトリを削除する（[cleanup-rules.md](../../../spec/cleanup-rules.md) 準拠）:
   ```bash
   python -c "import shutil; shutil.rmtree(r'{tmp_dir}/prod-drift-check', ignore_errors=True)"
   ```

## 出力

`docs/logs/{issueID}/release-plan.md`「## 本番環境ドリフト確認」セクションに追記:

```markdown
## 本番環境ドリフト確認

### Tier 1（軽量スキャン）
| コンポーネント | 最終更新日 | 最終更新者 | 痕跡 |
|---|---|---|---|
| {API名} | {日時} | {更新者} | あり / なし |

### Tier 2（深掘り・痕跡ありのみ）
| コンポーネント | diff 結果 | 判定 |
|---|---|---|
| {API名} | 差分なし / 差分あり | 実害なし / 要確認 / 競合・要人間判断 |

総合判定: ドリフトなし・リリース可 / 要確認あり（内容: {詳細}） / 競合あり（リリース中断推奨）
```

**「競合・要人間判断」が1件でもある場合**: release-plan.md 生成は継続するが、手順書冒頭とデプロイコマンド直前に警告ブロックを挿入し、完了報告でユーザーに明示的に伝える。デプロイの実行可否はユーザー判断（エージェントは判断しない）。
