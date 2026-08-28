# option-org-drift-check

## 何をするか

本番組織の状態が、今回リリースするメタデータの想定と乖離していないか（ドリフト）を **3段階（Tier0: 実体差分 → Tier1: 軽量スキャン → Tier2: 深掘り）** で確認する。ドリフトには方向が2つあり、検知手段が異なる:

- **本番が新しすぎる**（自分たちの知らないところで誰かが本番を直接触った）→ Tier1（資材マニフェスト対象の更新日時/更新者スキャン）→ Tier2（疑わしいものだけ実体取得して diff）
- **本番が古すぎる**（未リリース積み残し。今回の資材マニフェストに漏れているコンポーネントが本番に未反映のまま）→ **Tier0**（資材マニフェストに依存せず、UAT/本番の実体を直接比較）

Tier1/2 は release-preparer Phase 1 で確定した資材マニフェストに載っているコンポーネントしか検査しない。そのためマニフェスト自体に漏れがある場合（実例: GF-368 — 親 LWC のみが資材化され、参照される子コンポーネントの旧版が本番に残置。子は今回のコミット差分に含まれないためマニフェストに現れず、Tier1/2 の検査対象にすら入らなかった。本番だけ旧版のまま9日間・申込31件全てで必須項目が保存されず気づかれなかった）は Tier1/2 単独では検知できない。**Tier0 はマニフェストとは独立にスコープを決定して UAT/本番を直接比較することで、この穴を塞ぐ。**

**本番に対しては read-only のみ**（Tooling API の SELECT のみ。`force-app/` への取得・書き込みは一切行わない）。[prod-readonly-check.md](../../common/prod-readonly-check.md) を先に実施してから本オプションを実行する。**Tier 0 のみ UAT（Sandbox）との比較を伴うため、[sandbox-alias-check.md](../../common/sandbox-alias-check.md) で Sandbox 接続（`$SF_ALIAS`）も確認する**（Tier 1/2 は本番のみで完結するため不要）。

## 実行手順

### Tier 0: 環境間実体差分チェック（マニフェスト非依存・最優先）

> **検査対象の範囲（重要）**: Tier 0 の実体比較は **LWC（LightningComponentResource）/ Apex クラス / Apex トリガーの3種のみ**対応する（Tooling API で本文が取得できる種別に限定されるため）。Flow・カスタム項目・レイアウト等それ以外の種別の未リリース積み残しは Tier 0 では検知できない。これらは Tier 1（`sf org list metadata` の最終更新日時/更新者比較。資材マニフェストに載っている種別のみが対象）でカバーする。Tier 1 も資材マニフェスト外のコンポーネント（今回のマニフェストに現れない積み残し）は検知対象外である点に留意する。

release-preparer Phase 1 のマニフェスト確定を待たず、以下の手順でスコープを独自に決定してから実施する（Phase 1 内で先出し実行される場合もある。詳細: release-preparer.md Phase 1）。

**1. 対象スコープを次の和集合で確定する（全量比較はしない）**:
1. release-preparer Phase 1 で確定した資材マニフェスト
2. マニフェスト対象と**同一 LWC バンドル**、および**相互に参照し合うコンポーネント**（親が子を `modal.open({...})` / `<c-child prop=…>` で呼ぶ関係。実例: preCheck ⇄ preCheckModal）。特定方法: マニフェスト対象 LWC の `.js`/`.html` を Grep し、`import ... from 'c/{other}'` のインポート文・`<c-{kebab-case}` タグ・`{Something}Modal.open(` 等の呼び出しパターンから、参照先/参照元の LWC バンドルを双方向に洗い出してスコープへ追加する
3. [unreleased-component-scan.md](../_partials/unreleased-component-scan.md) の手順で暫定候補リストを抽出してスコープへ追加する（release-preparer Phase 1 1a-1/2a-1 で抽出済みの場合はそれを再利用し、再走査しない）

**2. UAT（Sandbox）と本番の双方から Tooling API 経由で実体を取得する**（`$SF_ALIAS` = [sandbox-alias-check.md](../../common/sandbox-alias-check.md) で確認済みの Sandbox/UAT エイリアス、`$PROD_ALIAS` = [prod-readonly-check.md](../../common/prod-readonly-check.md) で確認済みの本番エイリアス。`force-app/` への retrieve は行わない。取得結果は一時ディレクトリ `{tmp_dir}/org-drift-tier0/` に保存し、比較にのみ使う）:
```bash
mkdir -p "{tmp_dir}/org-drift-tier0"
# LWC（LightningComponentResource は Tooling API のみで取得可能。Source にコンポーネント本文が入る）
sf data query --use-tooling-api -q "SELECT Source, FilePath FROM LightningComponentResource WHERE LightningComponentBundle.DeveloperName = '{バンドル名}'" --target-org "$SF_ALIAS" --json > "{tmp_dir}/org-drift-tier0/{バンドル名}.uat.json"
sf data query --use-tooling-api -q "SELECT Source, FilePath FROM LightningComponentResource WHERE LightningComponentBundle.DeveloperName = '{バンドル名}'" --target-org "$PROD_ALIAS" --json > "{tmp_dir}/org-drift-tier0/{バンドル名}.prod.json"
# Apex クラス（Body は Tooling API のみで取得可能）
sf data query --use-tooling-api -q "SELECT Body FROM ApexClass WHERE Name = '{クラス名}'" --target-org "$SF_ALIAS" --json > "{tmp_dir}/org-drift-tier0/{クラス名}.uat.json"
sf data query --use-tooling-api -q "SELECT Body FROM ApexClass WHERE Name = '{クラス名}'" --target-org "$PROD_ALIAS" --json > "{tmp_dir}/org-drift-tier0/{クラス名}.prod.json"
# Apex トリガー
sf data query --use-tooling-api -q "SELECT Body FROM ApexTrigger WHERE Name = '{トリガー名}'" --target-org "$SF_ALIAS" --json > "{tmp_dir}/org-drift-tier0/{トリガー名}.uat.json"
sf data query --use-tooling-api -q "SELECT Body FROM ApexTrigger WHERE Name = '{トリガー名}'" --target-org "$PROD_ALIAS" --json > "{tmp_dir}/org-drift-tier0/{トリガー名}.prod.json"
```
> フィールド名・リレーション名がエラーになる場合は `sf sobject describe --sobject LightningComponentResource --use-tooling-api --target-org "$SF_ALIAS"` で実際のスキーマを確認してから再実行する（API バージョン差異の可能性）。

**3. UAT側・本番側の `Source` / `Body` を比較する**:
```bash
python -c "import json; a=json.load(open('{tmp_dir}/org-drift-tier0/{対象}.uat.json',encoding='utf-8'))['result']['records']; b=json.load(open('{tmp_dir}/org-drift-tier0/{対象}.prod.json',encoding='utf-8'))['result']['records']; ..."
```

**4. 差分の意味を判定する**（本判定は手順2で実体取得できた LWC / Apex クラス / Apex トリガーの3種のみに適用する。それ以外の種別の候補がスコープに含まれていた場合、実体取得できないため Tier0 では判定不可＝Tier1 の更新日時比較に委ねる）:
| 判定 | 条件 |
|---|---|
| **未リリース積み残し（最重要警告）** | UAT に存在するコンポーネントが本番に存在しない |
| **未リリース積み残しの疑い（最重要警告）** | UAT と本番で内容が異なり、UAT 側の差分が今回のリリース対象の変更を含む/含みうる |
| 他者変更あり・要確認 | UAT と本番で内容が異なるが、差分が今回のリリース内容と無関係（Tier1/2 の観点と合流） |
| 差分なし | UAT と本番が一致 |

**5. 「未リリース積み残し」「未リリース積み残しの疑い」が1件でもある場合**、release-plan.md 冒頭に最重要警告として記録する。**Tier0 で見つかったコンポーネントを資材マニフェストへ自動追加しない**（誤検知・スコープ外の可能性があるため）。完了報告で「マニフェストに含めるべきか」をユーザーに明示的に確認する。

**6. 一時ディレクトリ `{tmp_dir}/org-drift-tier0/` は release-preparer「Phase 最終: クリーンアップ」で削除される**（[cleanup-rules.md](../../../spec/cleanup-rules.md) 準拠。本 Step 単体では削除しない。Phase 1 で前倒し実行された場合も含め、release-plan.md 生成・完了報告後にまとめて削除するため）。

### Tier 1: 軽量スキャン（全リリース対象コンポーネントに実施）

> **release-preparer Phase 2 の mtime 判定禁止規定との違い（重要）**: Phase 2 は「ファイルの更新日時」（ローカル `force-app/` の mtime。`git checkout`・エディタの保存操作だけで内容が変わらなくても更新される）を差分判定に使わないと明記しているが、これはローカル Git 管理下ファイル特有の誤検知リスクへの対策であり、本 Tier 1 が参照する Salesforce 組織側の `lastModifiedDate`（メタデータ API が記録する組織側の保存時刻。ローカルの checkout/editor 操作では変化しない）とは対象・発生メカニズムが異なるため抵触しない。ただし本 Tier 1 の「痕跡なし → Tier 2 スキップ」判定は `lastModifiedDate` のみに基づき実体 diff で裏取りしないため、「本番側で更新されたが `lastModifiedDate` に反映されない」ケースは検知できない残存リスクがある（Tier 0 がマニフェスト外の積み残しを検知できないのと同種の、既知の限界として運用する）。

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

### Tier 0（環境間実体差分・マニフェスト非依存。検査対象は LWC / Apex クラス / Apex トリガーのみ。それ以外の種別は Tier 1 の更新日時比較でのみカバー）
| コンポーネント | 検査方式 | スコープ根拠 | UAT/本番 比較結果 | 判定 |
|---|---|---|---|---|
| {API名} | Tier0 実体比較 | マニフェスト / 参照関係 / decisions.md・cases | 一致 / UAT のみ存在 / 内容相違 / 未比較（Sandbox未接続） | 差分なし / 未リリース積み残し / 未リリース積み残しの疑い / 他者変更あり・要確認 / 未実施（Sandbox未接続） |

### Tier 1（軽量スキャン）
| コンポーネント | 最終更新日 | 最終更新者 | 痕跡 |
|---|---|---|---|
| {API名} | {日時} | {更新者} | あり / なし |

### Tier 2（深掘り・痕跡ありのみ）
| コンポーネント | diff 結果 | 判定 |
|---|---|---|
| {API名} | 差分なし / 差分あり | 実害なし / 要確認 / 競合・要人間判断 |

総合判定: ドリフトなし・リリース可 / 未リリース積み残しあり（リリース対象への追加要確認） / 要確認あり（内容: {詳細}） / 競合あり（リリース中断推奨） / Tier 0未実施のため要確認（Sandbox未接続）
```

**「未リリース積み残し」「未リリース積み残しの疑い」「競合・要人間判断」のいずれかが1件でもある場合**: release-plan.md 生成は継続するが、手順書冒頭とデプロイコマンド直前に警告ブロックを挿入し、完了報告でユーザーに明示的に伝える。デプロイの実行可否・マニフェストへの追加要否はユーザー判断（エージェントは判断しない）。
