---
description: "Salesforce 組織情報を分析し、組織概要・オブジェクト構成・マスタデータ・設計書・機能グループ・保守履歴・情報所在マップ・SF標準仕様の8カテゴリを docs/ 配下に生成する。3ページのUIで実行カテゴリを選択する。"
---

**AskUserQuestion のルール（厳守）:** [共通ルール参照](../CLAUDE.md#askuserquestion-ルール厳守)

**テンプレート置換ルール（厳守）:** [共通ルール参照](../CLAUDE.md#テンプレート置換ルール厳守)

---

> **注意**: このコマンドはClaude Codeの組み込みmemory機能・CLAUDE.mdへの書き込みは一切行わない。
> 全ての出力は `docs/` 配下のMarkdownファイル/JSONファイルへの保存のみで行う。

> **品質方針（最重要）**:
> - **読み取りは網羅的に、出力は具体的かつ正確に**。ここの精度が後続のプロジェクト資料・設計書の品質を直接決める。
> - 既存プロジェクト資料（要件定義書・業務フロー・画面仕様・システム構成図等）は **必ずフォルダ/ファイル単位で指定される前提**。ヒアリングは最小限にし、提示された資料を**隅々まで読み込む**こと。
> - 曖昧に要約せず、**登場人物・操作タイミング・承認経路・データ作成タイミング・外部連携・例外経路** を可能な限り粒度細かく抽出する。
> - 推測と事実を区別する。推測した箇所は `**[推定]**` を付ける。

---

## Step 0: 対象の選択

### プロジェクトパスの確定

Python で Windows 形式の絶対パスを取得する（`pwd` は POSIX 形式で返るため Python スクリプトに渡すと `C:\c\...` の誤パスが生成される）。

```bash
python -c "import pathlib, sys; p = pathlib.Path('.').resolve(); sys.exit(print('ERROR: カレントディレクトリは Salesforce プロジェクトルートではありません（sfdx-project.json が見つかりません）。', file=sys.stderr) or 1) if not (p / 'sfdx-project.json').exists() else print('project_dir:' + str(p))"
```

出力の `project_dir:` 以降を **`project_dir`** として控える（Windows 形式: `C:\workspace\...`）。取得した値は後続のエージェント委譲時にそのまま渡す。

上記 Python コマンドが `ERROR` または exit 1 で終了した場合は **コマンドを中止する**。「このフォルダは Salesforce プロジェクトとして認識できません（`sfdx-project.json` が存在しません）。Salesforce プロジェクトルートで実行してください」とユーザーに伝える。正常に `project_dir:...` が出力された場合は続行する（`docs/`・`force-app/` の有無はチェック不要。docs/ は初回実行で生成するのが /sf-memory の役割。force-app/ は各カテゴリのエージェントが個別確認する）。

**品質 spec の確認（必須）**: プロジェクトルートチェック通過後、以下を実行して品質原則 spec が存在することを確認する。

```bash
test -f "$(pwd)/.claude/spec/sf-memory-quality.md" && echo OK || echo MISSING
```

- `MISSING` の場合: **コマンドを中止する**。「`.claude/spec/sf-memory-quality.md` が見つかりません。テンプレートの spec が未同期の可能性があります。`/upgrade` を実行してから再度お試しください。各カテゴリの品質チェック（マーカー規約・技術識別子禁止・[推定]自動解消基準）はこの spec に依存するため、欠落状態での実行は品質低下（未解消マーカー乱立等）を招きます」とユーザーに伝える。
- `OK` の場合: 続行する。

---

AskUserQuestion ツールを **1回** 呼び出す。`questions` 配列に以下の **3問** を入れて3ページ形式で表示する。

**第1問**（`multiSelect: true`）:
- **question**: 「【1/3: 組織理解の基盤】どのカテゴリを実行しますか？（複数選択可）」
- **header**: 「カテゴリ選択1」
- **選択肢**:
  - 組織概要・環境情報（推奨・組織理解の核）— org-profile.md / requirements.md / usecases.md 等を生成（業務フロー・システム構成含む）
  - オブジェクト・項目構成（推奨・データ構造の核）— docs/catalog/ 配下のオブジェクト定義書・ER図を生成
  - マスタデータ・ワークフロー設定（オプション）— マスタデータ・承認プロセス・自動化設定を記録
  - このページはスキップ（Cat4以降へ）— Cat1〜Cat3 を実行せず次ページへ進む

> **「このページはスキップ（Cat4以降へ）」が選択された場合**: Cat1〜Cat3 の実行をゼロとして扱う（Q1 で他の選択肢と同時に選ばれた場合も Cat1〜Cat3 は実行しない）。
> **次のページ予告**: Q2 で設計書（cat4）・機能グループ定義（cat5）・過去事例参照（cat6）、Q3 で情報所在マップ（cat7）・SF 標準仕様（cat8）を選択できます。

**第2問**（`multiSelect: true`）:
- **question**: 「【2/3: 設計書・履歴】追加で実行するカテゴリを選択してください（複数選択可）」
- **header**: 「カテゴリ選択2」
- **選択肢**:
  - 設計書生成（cat4）（推奨・コード設計の核）— docs/design/ 配下の Apex・Flow・LWC 等の設計書を生成
  - 機能グループ定義（cat5）（オプション・cat4 依存）— docs/.sf/feature_groups.yml を生成（Cat4 完了後 or 単独再生成）
  - 保守履歴・工数温度感（cat6）（推奨・過去事例の核・Backlog MCP 必須）— Backlog 完了課題から工数温度感・過去事例インデックス・ハマりポイントを生成
  - このページはスキップ（Cat7以降へ）— Cat4〜Cat6 を実行せず次ページへ進む

> **「このページはスキップ（Cat7以降へ）」が選択された場合**: Cat4〜Cat6 の実行をゼロとして扱う（Q2 で他の選択肢と同時に選ばれた場合も Cat4〜Cat6 は実行しない）。
> **次のページ予告**: Q3 で情報所在マップ（cat7）・SF 標準仕様（cat8）を選択できます。

**第3問**（`multiSelect: true`）:
- **question**: 「【3/3: 知識基盤】追加で実行するカテゴリを選択してください（複数選択可）」
- **header**: 「カテゴリ選択3」
- **選択肢**:
  - 情報所在マップ更新（cat7）（推奨・他カテゴリ実行後に走らせると最も効果的）— docs/_README.md を単独で再生成・更新する
  - SF 標準仕様記録（cat8）（推奨・SF 制約参照の核）— Salesforce 公式ドキュメントからガバナ制限・API制限・トリガ順序等を収集して sf-standard.md を生成
  - このページはスキップ（実行しない）— Cat7・Cat8 を実行せず完了する


> **2回目以降の選択目安**（docs/ 配下と実組織・コードの差分があるカテゴリのみ選択）:
> - カテゴリ1: 組織概要・要件・業務フロー・外部連携に変更があった場合
> - カテゴリ2: force-app/ のオブジェクト・項目メタデータに変更があった場合
> - カテゴリ3: マスタデータ・承認プロセス・キュー・メールテンプレート等に変更があった場合
> - カテゴリ4: force-app/ のコンポーネント（Apex・Flow・LWC・ページ等）に変更があった場合
> - カテゴリ5: docs/design/ を手動修正後に feature_groups.yml だけ更新したい場合
> - カテゴリ6: Backlog 完了課題に変更（完了案件の追加・実績工数の更新）があった場合 → 横断ナレッジ（global-calibration / global-pitfalls）も自動更新（差分のみ処理するため2回目以降は軽量）
> - カテゴリ7: docs/ に新しいファイルが追加された場合・_README.md が古くなった場合

> **機能グループ定義だけ再生成したい場合**（docs/design/ 手動修正後に feature_groups.yml だけ更新したい場合）: Q2 の「機能グループ定義（cat5）」のみ選択して実行する。

### カテゴリ1で生成されるファイル（参考）

| ファイル | 用途 |
|---|---|
| `docs/overview/org-profile.md` | 組織プロフィール |
| `docs/requirements/requirements.md` | 要件定義書 |
| `docs/architecture/system.json` | システム構成図用（システム中心＋外部連携） |
| `docs/flow/usecases.md` | 業務ユースケース一覧（新規申込・解約申込・見積依頼等） |
| `docs/flow/swimlanes.json` | 業務フロー図（全体／UC別／例外／データフロー） |
| `docs/logs/changelog.md` | 実行履歴・変更点（Phase 5 で追記） |

### 「オブジェクト・項目構成」が選択された場合

AskUserQuestion ツールで追加選択:

**質問**: 「対象オブジェクトを指定しますか？」

**選択肢**:
- 全オブジェクト（デフォルト）
- 特定のオブジェクトを指定する（次のメッセージでAPI名を入力。カンマ区切りで複数可）

> **オブジェクト名が入力された場合**: 入力値をそのまま受け取り、委譲テンプレートの「対象オブジェクト」フィールドに設定する（バリデーションは行わずエージェントに委ねる）。

### 「設計・機能グループ定義」が選択された場合

AskUserQuestion ツールで追加選択:

**質問**: 「対象を指定しますか？」

**選択肢**:
- 全て（デフォルト）
- コンポーネントAPI名を指定する（次のメッセージで入力。複数可）
- 機能グループID（FG-XXX）を指定する（次のメッセージで入力。複数可）

> エージェント側の動作モード（初回生成 / 差分更新）は、docs/ や force-app/ の状態を見て自動判定する。ユーザーに選ばせない。判定できない場合（docs/ が空かつ force-app/ も空の場合等）は初回生成モードで実行する。

### 読み込ませたい資料がある場合

> **発動条件**: **cat1・cat2・cat3のいずれかが選択されている場合のみ**実施する。cat4〜cat8のみ選択の場合はスキップする（コードベース・Backlog・公式ドキュメントから読むため、プロジェクト資料は使われない）。

AskUserQuestion ツールで確認:

**質問**: 「読み込ませたい既存プロジェクト資料はありますか？（企画書・要件書・業務フロー図・画面仕様書・システム構成図・既存定義書等）」

**選択肢**:
- なし（そのまま進む）
- あり（チャットで直接パスを入力してもらう — AskUserQuestion は使わない。複数可。.xlsx/.docx/.pdf/.md/.pptx 対応）

> **資料ありの場合の扱い**: 受け取ったパス配下は **全て再帰的に読み込む**。サンプル扱いで端折らない。業務フローや画面仕様が含まれる場合は、登場人物・操作タイミング・承認経路まで抽出すること。

> **追加質問の発動ルール（複数カテゴリ選択時）**:
> - ここでの「追加質問」とは **対象オブジェクト指定・コンポーネント/FG指定の2種類のみ** を指す（資料確認は別扱い）。
> - 「オブジェクト・項目構成」が選択に含まれる場合: オブジェクト指定質問を出す
> - 「設計書生成（cat4）」または「機能グループ定義（cat5）」が選択に含まれる場合: コンポーネント/FG指定質問を出す
> - cat1〜6 が全て選択の場合: **追加質問**（↑ 上記2種類のオブジェクト/コンポーネント指定のみ）をスキップし、全オブジェクト・全機能でそのまま進む（**資料確認質問はスキップしない** — cat1〜3 を含む選択パターンで実施する）
> - 複数カテゴリを同時選択した場合の質問順序: 追加質問（オブジェクト指定 → 機能指定）→ 資料確認 の順で行う

---

## Step 1: カテゴリ専用エージェントへ委譲

各カテゴリは専用エージェントに委譲する（トークンコスト削減のため、各エージェントは自カテゴリの定義のみを保持している）。

### 全カテゴリ選択時（cat1〜8 全選択）

```
Phase 1: カテゴリ1 をエージェントへ委譲（順次）
  sf-analyst-cat1（カテゴリ1: 組織概要・環境情報）
    → docs/overview/org-profile.md
    → docs/requirements/requirements.md
    → docs/architecture/system.json
    → docs/flow/usecases.md
    → docs/flow/swimlanes.json
    → 完了サマリを返す

Phase 2: カテゴリ2 をエージェントへ委譲（順次）
  ※ カテゴリ1完了後に実行（org-profile.md を参照するため）
  sf-analyst-cat2（カテゴリ2: オブジェクト・項目構成）
    → docs/catalog/ を生成
    → 完了サマリを返す

Phase 2.5: カテゴリ3 をエージェントへ委譲（順次）
  ※ カテゴリ2完了後に実行（docs/catalog/ を参照するため）
  ※ cat3 を前段に置くことで、承認プロセス・キュー情報が cat4*/cat5 で参照可能になる
  sf-analyst-cat3（カテゴリ3: マスタデータ・ワークフロー設定）
    → docs/data/ を生成（master-data.md / email-templates.md / automation-config.md 等）
    → 完了サマリを返す

Phase 3: カテゴリ4・6・8 を並列でエージェントへ委譲
  ※ カテゴリ3完了後に実行（docs/data/automation-config.md を参照するため）
  ※ cat4-apex/cat4-flow/cat4-lwc・cat6・cat8はいずれも互いに独立しているため並列実行可
  ※ cat6 実行前に Backlog MCP を確認する: `grep -q '"backlog"' .mcp.json 2>/dev/null && echo "configured" || echo "not-configured"`
    未設定の場合は「Backlog MCP 未設定のため cat6 をスキップしました（`/setup-mcp` で設定後に再実行してください）」と通知してスキップ
  ※ cat8 は「SF 標準仕様記録（cat8）」が Q3 で選択されている場合のみ並列に追加する（未選択時はスキップ）
  ※ 並列実行は「1つの assistant メッセージ内で Agent ツールを複数同時に呼び出す」ことで実現する
  ※ cat4 は Apex/Flow/LWC の3種別エージェントに分割して並列実行する
  sf-analyst-cat4-apex（カテゴリ4-Apex: Apex・Trigger・Batch 設計書生成）┐
  sf-analyst-cat4-flow（カテゴリ4-Flow: Flow 設計書生成）                │ 並列実行
  sf-analyst-cat4-lwc（カテゴリ4-LWC: LWC・VF・Aura 設計書生成）       │
  sf-analyst-cat6（カテゴリ6: 保守履歴・工数温度感）                     │ ※ Backlog MCP 設定済みの場合のみ
  sf-analyst-cat8（カテゴリ8: SF 標準仕様記録）                          ┘ ※ Q2 で選択された場合のみ
    → 各カテゴリの docs/ を生成
      - cat4-apex: docs/design/apex/ / docs/design/batch/ / docs/design/integration/ を生成
      - cat4-flow: docs/design/flow/ を生成
      - cat4-lwc: docs/design/lwc/ / docs/design/vf/ / docs/design/aura/ を生成
      - cat6: docs/knowledge/effort-calibration.md / docs/knowledge/case-index.md / docs/knowledge/pitfalls.md / docs/.sf/_cmp_case_index.json を生成
      - cat8: docs/knowledge/sf-standard.md を生成
    → 完了サマリを返す

Phase 3a: feature_list.json の確定再スキャン（cat4 を実行した場合のみ）
  ※ cat4-apex/cat4-flow/cat4-lwc の全完了後、全種別の設計書 MD が出揃った状態で
    scan_features.py を1回実行し、各エントリの design_doc を確定する。
  ※ 各エージェントの Phase 0 では docs/design/ がまだ空のため design_doc が全件 null になっている。
    このステップで design_doc を埋め直す（scan_features.py は冪等・完全上書き）。
  python {project_dir}/scripts/python/sf-doc-mcp/scan_features.py \
    --project-dir "{project_dir}" \
    --output "{project_dir}/docs/.sf/feature_list.json"

Phase 3b: 機能グループ定義をエージェントへ委譲（順次）
  ※ cat4-apex/cat4-flow/cat4-lwc の全完了後に実行（docs/design/ の「関連UC」フィールドと _apex_skeletons.json/_lwc_skeletons.json/_flow_index.json を参照するため）
  sf-analyst-cat5（機能グループ定義）
    → docs/.sf/feature_groups.yml を生成
    → 完了サマリを返す

Phase 4: 2周目（横断補完）＋ cat7（情報所在マップ）
  sf-org-analyst に全 docs/ を読み込んで横断補完を実施させる（cat7 の _README.md 生成は Phase 4 の一部として実行）
```

### カテゴリ指定時

| 選択肢 | 委譲先エージェント | 前提カテゴリ |
|---|---|---|
| 組織概要・環境情報（cat1） | `sf-analyst-cat1` | なし |
| オブジェクト・項目構成（cat2） | `sf-analyst-cat2` | cat1（org-profile.md 必須） |
| マスタデータ・ワークフロー設定（cat3） | `sf-analyst-cat3` | cat1 + cat2（org-profile.md と docs/catalog/_index.md 必須） |
| 設計書生成（cat4） | `sf-analyst-cat4-apex` / `sf-analyst-cat4-flow` / `sf-analyst-cat4-lwc`（並列） | cat1 + cat2（catalog/ 必須）+ cat3（automation-config.md 推奨） |
| 機能グループ定義（cat5） | `sf-analyst-cat5` | cat4（docs/design/ 必須。cat4 と同時選択時は cat4 完了後に自動起動） |
| 保守履歴・工数温度感（cat6） | `sf-analyst-cat6` | なし（Backlog MCP 必須 — `.mcp.json` に `backlog` キーが必要） |
| 保守履歴・横断ナレッジ更新（cat6-global） | `sf-analyst-cat6-global` | cat6 完了後（cat6 が選択されている場合のみ起動可） |
| 情報所在マップ更新（cat7） | `sf-org-analyst`（mode: readme-only） | cat1（org-profile.md 必須） |
| SF 標準仕様記録（cat8） | `sf-analyst-cat8` | なし（WebFetch 必須 — インターネット接続が必要） |

> **前提チェック**:
> - cat2・cat3・cat4 を選択した場合、実行前に `docs/overview/org-profile.md` の存在を確認する。
> - さらに cat3・cat4 を選択した場合は `docs/catalog/_index.md`（cat2 の生成物）の存在も確認する。
> - 不足している場合は「先にカテゴリN（org-profile.md 不足ならカテゴリ1、catalog 不足ならカテゴリ2）を実行することを推奨します」と報告し、**AskUserQuestion で「このまま続行する / 前提カテゴリを先に実行する」の2択を提示してユーザーの判断を得る**。
> - **「このまま続行する」選択時の挙動**: 前提ファイルが欠けたまま各カテゴリのエージェントを起動する。各エージェント側では、読み込めない前提情報に依存するフィールドは全て `**[要確認]**` でマークし、完了報告の「要確認事項」セクションに「前提不足項目: {不足したファイル名}」として明記する。cat5 は `usecases.md` が必須のため例外で中断する（cat5 Phase 0 の規定通り）。

> **複数カテゴリ部分選択時の実行順序**（全カテゴリ選択時のフローを縮約して適用する）:
> - 実行前に「**前提チェック**」セクションを適用し、前提不足の場合はユーザー確認を先に行う（ユーザーが「このまま続行する」を選択した場合のみ下記フローに進む）。
> - 全カテゴリ選択時の順序（Phase 1: cat1 → Phase 2: cat2 → Phase 2.5: cat3 → Phase 3: cat4-apex+cat4-flow+cat4-lwc+cat6 並列 → Phase 3a: feature_list.json 確定再スキャン → Phase 3b: cat5 → Phase 4: 横断補完）から、**選択されたカテゴリのみを抽出して同じ順序で実行**する。
> - cat1・cat2・cat3 は依存先のため、選択されている場合は順次実行する。
> - cat4-apex/cat4-flow/cat4-lwc・cat6 は互いに独立しているため、複数選択された場合は並列実行する（1メッセージ内で Agent ツールを同時呼び出し）。cat6 は Backlog MCP 未設定の場合はスキップ（MCP 確認後に実行）。「設計書生成（cat4）」1カテゴリを選択した場合は cat4-apex/cat4-flow/cat4-lwc を並列起動する。cat6 実行完了後、自動的に `sf-analyst-cat6-global` を起動して横断ナレッジ（global-calibration.md / global-pitfalls.md）を更新する（確認なし）。cat6-global は初回のみ全量処理、2回目以降は差分のみ処理するため軽量。cat6 が選択されていない場合はこの自動起動をスキップする。
> - **cat5（機能グループ定義）**: cat4 と同時選択時は cat4 完了後に自動起動（Phase 3b）。**cat5 のみ単独選択**の場合は sf-analyst-cat5 を単独起動して終了する（Phase 4 はスキップ）。
> - **cat7（情報所在マップ更新）**: 他の cat1〜cat6 と並行可能。cat1〜cat6 の選択と同時に cat7 が選ばれている場合は、cat1〜cat6 完了後に Phase 4（横断補完）の一部として実行する。**cat7 のみ単独選択**の場合は sf-org-analyst を `mode: readme-only` で呼び出してから終了する（Phase 4 スキップ）。
> - **cat8（SF 標準仕様記録）**: cat1〜cat6 とは独立して並列実行可（docs/ を参照しない）。cat1〜cat6 のいずれかと同時に選択された場合は Phase 3 に追加して並列実行する。**cat8 のみ単独選択**の場合は sf-analyst-cat8 を単独起動して終了する（Phase 4 スキップ）。
> - 単一カテゴリ選択時は Phase 1 のみ（Phase 4 はスキップ）。ただし cat4 選択時は cat4-apex/cat4-flow/cat4-lwc 完了後に Phase 3a（確定再スキャン）を実行し、さらに cat5 が同時選択されていれば起動する。
> - 例: cat1+cat3 → cat1 実行後に cat3 を単独実行 → Phase 4
> - 例: cat3+cat4+cat5 → cat3 → cat4-apex/cat4-flow/cat4-lwc 並列 → cat5 → Phase 4
> - 例: cat3+cat6 → cat3 実行後に cat6 を単独実行（cat6 は Backlog MCP 確認後）→ Phase 4
> - 例: cat5 のみ → sf-analyst-cat5 を単独起動して終了（Phase 4 スキップ）
> - 例: cat8 のみ → sf-analyst-cat8 を単独起動して終了（Phase 4 スキップ）
> - 例: cat6+cat8 → cat6 と cat8 を並列実行（各前提チェック後）→ Phase 4
> - 例: cat7 のみ → sf-org-analyst（readme-only）を単独起動して終了

> ※ **Phase 4（sf-org-analyst による 2周目横断補完）の実行条件**: **2件以上**のカテゴリを選択した場合は常に実行する（全カテゴリ選択時を含む）。**cat7 単独のみ** 選択時は readme-only モードで呼び出す。**cat5 単独のみ / cat8 単独のみ** 選択時はスキップする。**cat1〜cat6 が1件のみ**（cat7/cat8 未選択）選択時はスキップする。

> ※ **単一カテゴリ実行時のマーカー軽量点検**（Phase 4 をスキップする **cat1〜cat6 が1件のみ** の場合に実行。cat5 単独 / cat8 単独 / 2件以上選択時は対象外 — cat5・cat8 はマーカー非該当、2件以上は Phase 4-A が全マーカーを処理するため不要）:
> - 横断*解消*（他カテゴリの情報でマーカーを埋める処理）は Phase 4 でのみ可能なため単一カテゴリでは行わない。代わりに、実行したカテゴリの生成先フォルダのみを対象に7種マーカー（[マーカー規約](../spec/sf-memory-quality.md#マーカー規約) 参照。一覧はここで再定義しない）の**件数点検**を行い、Step 2 の完了報告に付記する。
> - 対象フォルダ（実行カテゴリに対応するもののみ Grep する。`docs/` 全体は対象にしない — 前回実行の stale マーカー混入防止）: cat1=`docs/overview/`・`docs/requirements/`・`docs/architecture/`・`docs/flow/` / cat2=`docs/catalog/` / cat3=`docs/data/` / cat4=`docs/design/` / cat6=`docs/knowledge/`
> - 点検コマンド（複合マーカー `[推定: 分布=...]` 等も検出開始位置でカウント）:
>   ```bash
>   grep -rEo '\*\*\[(要確認|推定|資料未確認|組織未調査|未ヒアリング|出典不明|未実装)' {対象フォルダ} | sed -E 's/.*\[//' | sort | uniq -c
>   ```
> - 報告形式は Step 2「カテゴリ指定（単独・複数）実行時」参照。

---

## エージェントへの委譲方法

Agent ツールを使用し、以下を self-contained なプロンプトで渡す:
- 実行するカテゴリ名と対象範囲
- 読み込む既存 docs/ のパス
- 読み込ませたい資料のパス（Step 0 で指定があった場合）
- プロジェクトフォルダのパス

エージェント定義は Agent ツールが自動でロードするため、全文転記不要。

**委譲時の必須情報テンプレート**:
- プロジェクトフォルダパス: `{pwd の結果}`
- 対象オブジェクト: `{Step 0 で取得した値、未指定時は「全オブジェクト」}`
- 対象コンポーネントAPI名: `{Step 0 で取得した値、未指定時は「全て」}`
- 対象機能グループID: `{Step 0 で取得した値、未指定時は「全て」}`
- 読み込む docs/ パス: `{プロジェクトフォルダ}/docs/`
- 読み込ませたい資料パス: `{Step 0 で指定があった場合のみ記載}`
- 実行モード: 初回 / 差分更新（docs/ の既存ファイル有無でエージェントが自動判断）

**cat5（機能グループ定義）への追加情報**（**cat4 が選択されている場合のみ** cat4 完了後に起動する際に追加で渡す。cat4 を含まない選択では無視する）:
- docs/design/ パス: `{プロジェクトフォルダ}/docs/design/`（cat4 が生成した設計書の「関連UC」フィールドを参照するため）

---

## Step 2: ユーザーへの報告

各ステップ完了時に報告する:

**2件以上選択時（全カテゴリ含む）:**
```
✅ カテゴリ1 完了 — org-profile.md, requirements.md, system.json, usecases.md, swimlanes.json を生成しました
✅ カテゴリ2 完了 — オブジェクト定義書 X件 を生成しました
✅ カテゴリ3 完了 — マスタデータ・ワークフロー設定情報を記録しました
✅ カテゴリ4 完了 — 設計書 X件 を生成しました（docs/design/）
🔄 カテゴリ5（機能グループ定義）を実行中...
✅ カテゴリ5 完了 — feature_groups.yml（FG-XXX 件）
✅ カテゴリ6 完了 — effort-calibration.md / case-index.md / pitfalls.md を生成しました
（Backlog MCP 未設定の場合: ⏭️ カテゴリ6 スキップ — Backlog MCP 未設定。/setup-mcp で設定後に再実行してください）
✅ 横断ナレッジ 完了 — global-calibration.md, global-pitfalls.md を生成しました（cat6-global）
（cat6-global を実行した場合のみ表示。cat6 未選択またはユーザーが「いいえ」と回答した場合は出力なし）
✅ カテゴリ8 完了 — sf-standard.md を生成しました（Salesforce 公式ドキュメント参照）
（cat8 未選択の場合: 出力なし）
🔄 2周目（横断補完）を実行中...
✅ 2周目（横断補完）完了 — 修正 X件・補完 Y件
✅ カテゴリ7 完了 — docs/_README.md を更新しました
```

**カテゴリ指定（単独・複数）実行時:**
```
✅ {カテゴリ名} 完了 — 生成ファイル X件
```
（cat4 と cat5 が同時選択されている場合は cat4 完了後に自動的に cat5 を起動して報告する）

**単一カテゴリ実行時（cat1〜cat6 が1件のみ）は、上記に加えてマーカー軽量点検の結果を1行追記する**（cat5 単独 / cat8 単独時は追記しない）:
```
✅ {カテゴリ名} 完了 — 生成ファイル X件
   未解消マーカー: 要確認 A件 / 推定 B件 / その他 C件（横断解消は複数カテゴリ実行時の Phase 4 で実施）
```
