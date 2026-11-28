# option-error-message-reverse-lookup

## 何をするか

課題に記載されたエラー文言・トースト・例外メッセージを起点に `force-app/` を全文 grep し、発生源（Apex の throw/addError、Validation Rule の errorMessage、重複ルール・参照項目の検索条件・数式項目の文言、カスタムラベル、LWC・Aura・Visualforce の表示箇所）を特定する。「エラーが出るが原因箇所が分からない」「どのロジックが弾いているか不明」なケースで発生条件の特定を効率化する。

## 実行手順

### Step 1: エラー文言の抽出

課題本文・コメント・添付（エラー画面の画像等）からエラー文言を抽出する:
- 画面に表示されたメッセージ（例: 「保存できませんでした。条件を確認してください」）
- System.AuraHandledException / DmlException のメッセージ
- Validation Rule のエラーメッセージ
- LWC のトースト表示テキスト

**部分一致でも OK**（前後の一般的な語は除去して固有部分を抜き出す）。

### Step 2: force-app/ 全文 grep

```bash
# 1. Apex・トリガー（throw / addError / AuraHandledException / ApexPages.addMessage）
grep -r --include="*.cls" --include="*.trigger" -n "<エラー文言の固有部分>" force-app/

# 2. LWC・Aura・Visualforce（JavaScript / HTML / コンポーネント・ページに直書きのトースト・表示テキスト）
grep -r --include="*.js" --include="*.html" --include="*.cmp" --include="*.page" --include="*.component" -n "<エラー文言の固有部分>" force-app/

# 3. カスタムラベル
grep -r --include="*.labels-meta.xml" -n "<エラー文言の固有部分>" force-app/

# 4. Validation Rule / フロー / 重複ルール / 参照項目の検索条件・数式項目（field-meta.xml は、ヒットが検索条件の <errorMessage> か数式項目の <formula> の中なら発生源。description・inlineHelpText・label・検索条件の infoMessage は外す）
grep -r --include="*.validationRule-meta.xml" --include="*.flow-meta.xml" --include="*.duplicateRule-meta.xml" --include="*.field-meta.xml" -n "<エラー文言の固有部分>" force-app/

# 5. カスタムメタデータのレコード
grep -r --include="*.md-meta.xml" -n "<エラー文言の固有部分>" force-app/
```

カスタムラベル（3.）にヒットしたら、組織の地図があれば `python scripts/python/sf-lineage/lineage.py who Label:<ラベル名>` でそのラベルを使う Apex・LWC・Aura・フローなどを出し、Step 3 で読む発生源の候補にする（[option-lineage-map.md](option-lineage-map.md)。地図はクラス単位なので、どのメソッド・どの条件で出すかはファイルで確かめる）。

**ヒットしない場合の対処**:
1. 日本語メッセージは部分文字列に絞って再試行（助詞「が」「で」「を」等で分割）
2. カスタムラベル経由の可能性 → `label\.`（Apex。大文字小文字を区別しない検索で。`System.` は省略できる）・`@salesforce/label/c.`（LWC）・`\$Label\.`（Aura・VF・フロー・数式項目。`$` はエスケープする。`grep` なら `-F '$Label.'`）を grep してラベル名を特定 → ラベルファイルで対応する文言を確認
3. 動的生成（`String.format()` / 変数結合）の可能性 → 固定文字列部分のみで grep
4. 記号（`'` `"` `&` `<` `>`）を含む文言 → XML では `&apos;` 等になっているので、記号を含まない部分で grep

### Step 3: 発生源の読み込みと条件特定

ヒットしたファイル・行を Read して、エラーが投げられる条件（if 分岐・ルール条件式）を特定する:

```bash
# ヒット箇所の前後10行を確認
grep -n -A 10 -B 10 "<エラー文言の固有部分>" <Step 2 でヒットしたファイル>
```

確認すべき事項:
- **共通**: 手元の有効・無効（入力規則・検索条件の `<active>`、重複ルールの `<isActive>`、フロー・トリガーの `<status>`）だけで発生源から外さない（手元は retrieve した時点の写しで、フローは最新の版が入る）。手元で無効なものは発生源の表に残して条件の列に「手元では無効・組織で要確認」と書き、フロー・トリガーは [option-flow-trigger-trace.md](option-flow-trigger-trace.md) 手順2 のとおり組織に問い合わせて確かめる
- **Apex**: throw/addError の直前の `if` 条件 → 何が真のときにエラーになるか
- **Validation Rule**: `ISPICKVAL`/`ISBLANK`/`AND`/`OR` の条件式 → どのフィールド値の組み合わせでエラーになるか
- **LWC・Aura**: `showToast`（Aura は `force:showToast`）の呼び出し元 → どのイベント/レスポンスでトーストが発火するか
- **Visualforce**: 文言を出す要素の `rendered` 条件・ページ内の JavaScript の条件分岐 → どの状態・入力で表示されるか
- **フロー**: エラー要素・画面に至る `decisions` の条件と、起動条件（`start` の `filters`・`filterLogic`・`filterFormula`）
- **重複ルール**: 作成時は `actionOnInsert`・`operationsOnInsert`、更新時は `actionOnUpdate`・`operationsOnUpdate` を見る。action が Block なら保存を止めて `alertText` を出す。Allow でも operations に Alert があれば `alertText` を警告として出す（Report だけなら文言は出ない）。条件は `duplicateRuleFilter` と、`matchingRule` が指す照合ルール（`matchingRules/{matchRuleSObjectType}.matchingRule-meta.xml` の同じ `fullName` の `matchingRuleItems`・`booleanFilter`。`ruleStatus` も見る。`Standard_` で始まる標準のルールは force-app に無い）
- **参照項目の検索条件**: `filterItems` の条件と `isOptional`（false なら保存を止める）
- **数式項目**: その文言を返す `IF` 等の条件
- **カスタムラベル・カスタムメタデータ**: そのラベル・レコードを使う側の条件を読む

### Step 4: Sandbox での条件再現

Step 3 で特定した条件を使って、Sandbox で故意にエラーを再現できるか匿名 Apex（データの作成・更新を含む。実行前の確認と rollback は [backlog-investigator.md](../../../agents/backlog-investigator.md)「調査原則」の「Sandbox のデータは変えずに確かめる」のとおり）で確認する（`option-apex-debug-log` と組み合わせると効果的）。画面側の処理（LWC・Aura・Visualforce の表示、画面フローの画面、重複ルールの Allow＋Alert の警告）や操作ユーザーの権限で決まる条件と、レコードトリガーフローの非同期パス・スケジュール済みパス、時間ベースワークフロー・プロセスビルダーのスケジュール済みアクションで出るエラーは匿名 Apex では再現できないため、再現しなくても発生源から外さない（バグは Phase 1.6 が画面で再現する）。

## 出力

investigation.md「## 根本原因 / 要件の本質」の末尾（次の「## 」見出しの前）に追記（尤度・根拠を変えた仮説は「### 原因仮説（多角分析）」の表のその行も直す）:

```markdown
### エラー文言逆引き結果

- 検索したエラー文言: 「{エラー文言}」（固有部分: `{grep キーワード}`）

#### 発生源

| # | ファイル（パス:行番号） | 種別 | エラーを出す条件 |
|---|---|---|---|
| 1 | {ファイルパス}:{行番号} | Apex / Trigger / LWC / Aura / VF / ValidationRule / Flow / DuplicateRule / LookupFilter / Formula / CustomLabel / CustomMetadata | {条件式または文言} |

#### 発生条件の特定

{Apex の if 条件 / Validation Rule の論理式 / LWC のトリガーイベントを自然言語で説明}

#### 仮説への影響

- 発生源が特定されたため H{N}（{仮説名}）の根拠を強化。尤度を {高/中/低} に更新
- 発生条件: {具体的な条件（フィールド値・状態）}
```

発生源が見つからない場合:
```markdown
### エラー文言逆引き結果

- 検索したエラー文言: 「{エラー文言}」（固有部分: `{grep キーワード}`）
- 結果: force-app/ に一致箇所なし
- 考察: カスタムラベルの可能性（{カスタムラベル grep 結果}）/ カスタム設定・レコードに持たせた文言（データ）/ 外部パッケージ経由 / Salesforce 標準エラー
- 次の手順: {カスタムラベル確認 / option-sf-docs-verification で標準エラー裏取り}
```

## 禁止事項

- grep が大量ヒットした場合でも全件を investigation.md に貼り付けない。発生源の特定に必要な最小限の行数のみ記録する
