# option-error-message-reverse-lookup

## 何をするか

課題に記載されたエラー文言・トースト・例外メッセージを起点に `force-app/` を全文 grep し、発生源（Apex の throw/addError、Validation Rule の errorMessage、カスタムラベル、LWC 表示箇所）を特定する。「エラーが出るが原因箇所が分からない」「どのロジックが弾いているか不明」なケースで発生条件の特定を効率化する。

## 実行手順

### Step 1: エラー文言の抽出

課題本文・コメント・スクリーンショット説明からエラー文言を抽出する:
- 画面に表示されたメッセージ（例: 「保存できませんでした。条件を確認してください」）
- System.AuraHandledException / DmlException のメッセージ
- Validation Rule のエラーメッセージ
- LWC のトースト表示テキスト

**部分一致でも OK**（前後の一般的な語は除去して固有部分を抜き出す）。

### Step 2: force-app/ 全文 grep

```bash
# 1. Apex（throw / addError / AuraHandledException）
grep -r --include="*.cls" -n "<エラー文言の固有部分>" force-app/

# 2. LWC（JavaScript / HTML のトースト・表示テキスト）
grep -r --include="*.js" --include="*.html" -n "<エラー文言の固有部分>" force-app/

# 3. カスタムラベル
grep -r --include="*.labels-meta.xml" -n "<エラー文言の固有部分>" force-app/

# 4. Validation Rule / フロー
grep -r --include="*.validationRule-meta.xml" --include="*.flow-meta.xml" -n "<エラー文言の固有部分>" force-app/

# 5. カスタムメタデータ / カスタム設定
grep -r --include="*.md-meta.xml" -n "<エラー文言の固有部分>" force-app/
```

**ヒットしない場合の対処**:
1. 日本語メッセージは部分文字列に絞って再試行（助詞「が」「で」「を」等で分割）
2. カスタムラベル経由の可能性 → `System.Label.` を grep してラベル名を特定 → ラベルファイルで対応する文言を確認
3. 動的生成（`String.format()` / 変数結合）の可能性 → 固定文字列部分のみで grep

### Step 3: 発生源の読み込みと条件特定

ヒットしたファイル・行を Read して、エラーが投げられる条件（if 分岐・ルール条件式）を特定する:

```bash
# ヒット箇所の前後20行を確認
grep -r --include="*.cls" -n -A 10 -B 10 "<エラー文言>" force-app/
```

確認すべき事項:
- **Apex**: throw/addError の直前の `if` 条件 → 何が真のときにエラーになるか
- **Validation Rule**: `ISPICKVAL`/`ISBLANK`/`AND`/`OR` の条件式 → どのフィールド値の組み合わせでエラーになるか
- **LWC**: `showToast` の呼び出し元 → どのイベント/レスポンスでトーストが発火するか

### Step 4: Sandbox での条件再現

Step 3 で特定した条件を使って、Sandbox で故意にエラーを再現できるか確認する（`option-apex-debug-log` と組み合わせると効果的）。

## 出力

investigation.md「根本原因」セクションに追記:

```markdown
## エラー文言逆引き結果

- 検索したエラー文言: 「{エラー文言}」（固有部分: `{grep キーワード}`）

### 発生源

| # | ファイル（パス:行番号） | 種別 | エラーを出す条件 |
|---|---|---|---|
| 1 | {ファイルパス}:{行番号} | Apex / LWC / ValidationRule / CustomLabel | {条件式または文言} |

### 発生条件の特定

{Apex の if 条件 / Validation Rule の論理式 / LWC のトリガーイベントを自然言語で説明}

### 仮説への影響

- 発生源が特定されたため H{N}（{仮説名}）の根拠を強化。尤度を {高/中/低} に更新
- 発生条件: {具体的な条件（フィールド値・状態）}
```

発生源が見つからない場合:
```markdown
## エラー文言逆引き結果

- 検索したエラー文言: 「{エラー文言}」（固有部分: `{grep キーワード}`）
- 結果: force-app/ に一致箇所なし
- 考察: カスタムラベルの可能性（{カスタムラベル grep 結果}）/ 外部パッケージ経由 / Salesforce 標準エラー
- 次の手順: {カスタムラベル確認 / option-sf-docs-verification で標準エラー裏取り}
```

## 禁止事項

- grep が大量ヒットした場合でも全件を investigation.md に貼り付けない。発生源の特定に必要な最小限の行数のみ記録する
