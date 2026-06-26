# Phase 1 オプションインデックス（調査・理解・原因特定）

backlog-investigator が Step 0b で参照する判定情報。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

## 実行順序の依存関係

以下のオプションは判定条件・実行手順が前段オプションの結果に依存するため、評価順序を守る:

1. **`multi-cause-hypothesis`** を最初に評価
2. その結果を踏まえて **`second-opinion`** / **`counter-evidence-search`** を評価（前段で原因仮説が薄い・偏っている場合に発火する設計）
3. その他のオプションは独立評価可能（任意順序）

並列実行不可。Step 0b で順次評価すること。

---

```yaml
options:

  - name: option-reverse-grep
    description: 変更対象の API 名・関数名・フィールド名を force-app/ 全体から逆参照 grep
    category: B
    auto-execute-when:
      - 変更対象が Apex メソッド・LWC 関数・カスタムフィールド API 名
      - 課題が「ロジック修正」「項目追加・削除」「リネーム」を含む
      - 種別がバグ
    auto-skip-when:
      - 変更対象がコメント文字列のみ
      - 変更対象がラベル・表示文字列のみ（API 名・コードロジック非該当）
    ask-user-prompt: |
      この修正はコード実体に影響しない変更（コメント・ラベル等）のようです。
      変更対象を呼んでいる他のコードがないか確認する手順は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-similar-impl-search
    description: 類似実装パターンを force-app/ から全件探索して読む
    category: B
    auto-execute-when:
      - 種別が追加要望
      - 種別がバグかつ非自明で同種処理が他のオブジェクト・ビザ種別・コンポーネントに存在しうる（正常動作する類似実装と比較して差異を特定するため）
      - 課題に「同じパターン」「類似機能」「他で実装済み」の言及あり
      - 新規 LWC・Apex クラス・Flow を作成する場合
    auto-skip-when:
      - 既存コード 1 メソッド内の単純な値修正のみ
      - 単純な定数値変更
    ask-user-prompt: |
      この修正はごく狭い範囲の値変更のようです。プロジェクト内の類似実装を広く探す手順は省略してもよさそうですか？
    estimated-cost: 重
    default-when-uncertain: skip

  - name: option-sf-docs-verification
    description: Salesforce 公式ドキュメント（help.salesforce.com / developer.salesforce.com）で標準仕様を裏取り
    category: C
    auto-execute-when:
      - 課題で標準 UI・標準オブジェクト・標準項目・標準コンポーネントの挙動が論点
      - 課題に「リスト ビュー」「フィルター」「検索」「列挙型項目」等の標準機能名が登場
      - 標準 API（REST/SOAP）の仕様確認が必要
    auto-skip-when:
      - 完全カスタム実装のみが対象（標準仕様非該当）
    ask-user-prompt: |
      この課題はカスタム実装のみが対象のようです。Salesforce 公式ドキュメントでの標準仕様裏取りは省略してもよさそうですか？
    estimated-cost: 中

  - name: option-symptom-reverification
    description: 症状の前提（固有名詞の実在・名前表記・実データ値・実際の操作で再現するか）を再確認
    category: A
    auto-execute-when:
      - 種別がバグ（常時実行）
      - 課題に「○○が表示されない」「○○できない」等の症状記述あり
    auto-skip-when:
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
      - 種別が「追加要望」かつ既存挙動への言及がない
      - 設定変更のみで症状概念が無関係
    ask-user-prompt: |
      この課題は新機能追加であり、既存挙動の症状確認は不要そうです。症状の前提再確認は省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-impact-scope-grep
    description: Validation Rule / 承認プロセス / 割り当てルール / 共通ユーティリティの参照を grep
    category: B
    auto-execute-when:
      - 変更対象がオブジェクトのフィールド・項目
      - 変更対象が共通 Apex クラス・共通ユーティリティメソッド
    auto-skip-when:
      - 変更対象が単一 LWC 内の表示制御のみ
      - コメント・ラベル変更のみ
    ask-user-prompt: |
      この修正は単一コンポーネント内の表示制御のみのようです。Validation Rule や承認プロセス・割り当てルール・共通ユーティリティへの影響確認は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-second-opinion
    description: blind second-opinion（前情報なし原因仮説）— subagent 化必須
    category: D
    auto-execute-when:
      - 種別がバグかつ非自明（典型的自明ケース以外）
      - 課題優先度が「高」または「緊急」
      - 課題に「全社影響」「重要バグ」「複数箇所で発生」等の言及あり
      - 既存仮説が単一原因に偏っている兆候（option-multi-cause-hypothesis 結果が薄い）
    auto-skip-when:
      - 種別が「その他」かつ単純な設定変更のみ
      - typo 修正・ラベル変更レベル（典型的自明ケース）
    ask-user-prompt: |
      この課題は影響範囲が小さい修正のようです。blind 別仮説（subagent）の検証は省略してもよさそうですか？
    estimated-cost: 重
    default-when-uncertain: skip

  - name: option-related-issue-search
    description: 関連 Backlog 過去課題の履歴検索（mcp__backlog__get_issues / get_issue_comments）
    category: D
    auto-execute-when:
      - 課題に「以前にも発生」「過去に類似」「再発」等の言及あり
      - 同一機能・同一画面で過去に課題があった可能性が高い
    auto-skip-when:
      - 完全新規機能の追加要望
      - 設定変更のみでロジック関与なし
    ask-user-prompt: |
      この課題は過去の同種課題が無さそうです。Backlog 過去課題の履歴検索は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-git-blame-history
    description: 変更対象ファイルの git blame で過去変更履歴・変更理由を確認
    category: B
    auto-execute-when:
      - 変更対象が既存コード（Apex/LWC/Flow メタデータ）
      - 「なぜこう実装されているか」が論点
    auto-skip-when:
      - 完全新規ファイル作成のみ
      - 変更対象が docs/ や設定ファイルのみ
    ask-user-prompt: |
      この修正は新規ファイル作成のみで既存コードに触れないようです。git blame による過去履歴確認は省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-permission-fls-check
    description: 権限セット・プロファイル・FLS の影響確認
    category: C
    auto-execute-when:
      - 変更対象がオブジェクト・フィールドの追加・削除・型変更
      - 課題に「権限」「ユーザー」「プロファイル」「アクセス」等のワード
      - 種別がバグかつ「○○ユーザでだけ発生」等の権限関連症状あり
    auto-skip-when:
      - 変更対象が Apex 内部ロジックのみ（FLS 非該当）
      - コメント変更のみ
    ask-user-prompt: |
      この修正は内部ロジックのみで権限・FLS への影響は無さそうです。権限セット・プロファイル・FLS の確認は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-flow-trigger-trace
    description: Flow / Apex Trigger の連鎖実行を追跡
    category: C
    auto-execute-when:
      - 変更対象がオブジェクトのフィールド更新を含む処理
      - 課題に「保存後」「更新時」「自動実行」等の連鎖系ワード
    auto-skip-when:
      - 変更対象が読み取り専用処理（クエリ・表示のみ）
      - LWC 内の表示制御のみ
    ask-user-prompt: |
      この修正は読み取り専用処理のようです。Flow / Trigger の連鎖実行追跡は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-test-class-impact
    description: 既存テストクラスへの影響確認
    category: B
    auto-execute-when:
      - 変更対象が Apex クラス・トリガー
      - 既存メソッド削除・シグネチャ変更を含む
    auto-skip-when:
      - 変更対象が LWC のみ・Flow メタデータのみ（Apex 非該当）
      - 設定変更のみ
    ask-user-prompt: |
      この修正は Apex を含まないようです。既存テストクラスへの影響確認は省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-data-volume-analysis
    description: データ件数・大量データ影響評価（SOQL 実行で件数確認・LIMIT 検証）
    category: C
    auto-execute-when:
      - 変更対象が SOQL クエリを含む処理
      - 課題に「件数」「大量データ」「タイムアウト」「ガバナ制限」等のワード
      - バッチ処理・スケジューラ系の修正
    auto-skip-when:
      - LWC 内の表示制御のみ（DB 操作なし）
      - 単一レコード操作のみ
    ask-user-prompt: |
      この修正は単一レコード操作のみのようです。データ件数・大量データ影響評価は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-similar-past-issue
    description: 類似過去課題の再発確認（同種の課題が繰り返されていないか）
    category: D
    auto-execute-when:
      - 課題で「またか」「再発」「以前と同じ」等の言及あり
      - 同一機能領域で過去 1 ヶ月以内に類似修正履歴がある可能性
    auto-skip-when:
      - 完全新規機能の追加要望
    ask-user-prompt: |
      この課題は新機能追加で再発概念が無さそうです。類似過去課題の再発確認は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-business-process-mapping
    description: 業務フロー視点での影響確認（docs/ の業務フロー図と照合）
    category: D
    auto-execute-when:
      - 変更対象がオブジェクトのステータス遷移・承認プロセス
      - 課題で「業務フロー」「営業プロセス」「申請フロー」等への言及
    auto-skip-when:
      - 変更対象が UI 表示・コメント・ラベルのみ（業務ロジック非関与）
    ask-user-prompt: |
      この修正は業務ロジックに関与しないようです。業務フロー視点での影響確認は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-user-impact-survey
    description: 影響ユーザー数・部署の見積もり
    category: D
    auto-execute-when:
      - 変更対象が共有・標準機能・全ユーザーが触る画面
      - 課題で「全社」「全営業」「全部署」等の言及
    auto-skip-when:
      - 変更対象が単一プロファイル・特定ユーザー専用機能
      - 内部処理のみで UI 影響なし
    ask-user-prompt: |
      この修正は特定ユーザー専用機能のようです。影響ユーザー数・部署の見積もりは省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-sharing-rule-check
    description: 共有ルール・OWD への影響確認
    category: C
    auto-execute-when:
      - 変更対象がオブジェクトの所有者・関連レコード
      - 課題に「共有」「アクセス」「閲覧不可」「権限不足」等のワード
      - レコードタイプ変更を含む
    auto-skip-when:
      - 変更対象が UI のみ・Apex 内部処理のみ（DB 構造非関与）
    ask-user-prompt: |
      この修正は共有モデルに影響しないようです。共有ルール・OWD への影響確認は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-multi-cause-hypothesis
    description: 原因仮説を 3 件以上立てて尤度比較（単一原因への思考ロック防止）
    category: A
    auto-execute-when:
      - 種別がバグ（常時実行）
      - 課題に明確な単一原因が見えていない場合
    auto-skip-when:
      - 種別が追加要望（原因概念が無関係）
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
    ask-user-prompt: |
      この課題は新機能追加で原因仮説の概念が無関係です。多重原因仮説の検討は省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-assumption-listing
    description: 暗黙の前提を全て明示（「○○のはず」を全列挙して検証可能化）
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望（常時実行）
      - 「○○のはず」「通常は」「想定では」等の前提語が課題にある
    auto-skip-when:
      - 単純な定数値修正・typo 修正で前提概念が無関係
    ask-user-prompt: |
      この課題は前提検証が不要そうです。暗黙前提の明示は省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-counter-evidence-search
    description: 現原因仮説に矛盾する反証を探す（仮説検定の片側偏り防止）
    category: A
    auto-execute-when:
      - 種別がバグ（常時実行）
      - 既存仮説がある状態（option-multi-cause-hypothesis 後の段階）
    auto-skip-when:
      - 種別が追加要望（原因概念が無関係）
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
    ask-user-prompt: |
      この課題は新機能追加で反証概念が無関係です。反証探索は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-causal-chain-analysis
    description: 症状 → 直接原因 → 根本原因の連鎖を図示（中間層を飛ばさない）
    category: A
    auto-execute-when:
      - 種別がバグかつ複数コンポーネントが関与
      - 連鎖実行（Trigger / Flow / Workflow）を含む処理
    auto-skip-when:
      - 単一行修正レベル
      - 設定変更のみ
    ask-user-prompt: |
      この修正は単一箇所への修正のようです。症状から根本原因への連鎖図示は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-reproduction-step-detail
    description: 再現手順を 1 操作粒度まで分解（前提データ・操作ユーザ・タイミング含む）
    category: C
    auto-execute-when:
      - 種別がバグ（常時実行）
      - 再現条件が課題本文で曖昧
    auto-skip-when:
      - 種別が追加要望（再現概念が無関係）
      - その他で再現性確認が不要
    ask-user-prompt: |
      この課題は新機能追加で再現概念が無関係です。再現手順の 1 操作粒度分解は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-apex-debug-log
    description: Sandbox で Apex デバッグログを取得・解析し、バグの発生箇所・例外内容・実行時変数値を特定
    category: A
    auto-execute-when:
      - 種別がバグかつ非自明で Apex / Trigger / Flow が関与する処理
      - 課題にエラー・例外・「処理が走らない」「値が入らない」「保存できない」等の実行時挙動の問題
      - 静的コード読解のみでは分岐到達・例外発生箇所を確定できない
    auto-skip-when:
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
      - 種別が「追加要望」または「その他」
      - 変更対象が純 UI（HTML・表示文言のみ）・ラベル変更・設定のみで Apex / Trigger / Flow が非関与
    ask-user-prompt: |
      この課題はバックエンドロジックに関係しないようです。Apex デバッグログの取得・解析は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-cross-record-comparison
    description: 症状あり/なしレコードを SOQL で抽出・比較し、差分フィールドを原因候補に昇格
    category: A
    auto-execute-when:
      - 種別がバグで「特定のレコードのみ発生」「一部で再現」「特定ユーザーだけ」等の限定的発生パターン
      - 同一オブジェクト内で正常動作するレコードと異常レコードが混在する
    auto-skip-when:
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
      - 種別が「追加要望」または「その他」
      - 全レコードで一律に発生する（比較対象となる正常レコードが存在しない）
      - 設定・コードのみが原因でデータ差分が関係しない（単一コード分岐の誤り等）
    ask-user-prompt: |
      この課題は全レコードで一律に発生しているようです。症状あり/なしレコードの差分比較は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-error-message-reverse-lookup
    description: エラー文言・例外メッセージを起点に force-app/ を grep し発生源（Apex/Validation Rule/カスタムラベル/LWC）を特定
    category: A
    auto-execute-when:
      - 課題に具体的なエラー文言・トーストメッセージ・例外メッセージが記載されている
      - 種別がバグで「エラーになる」「保存できない」「弾かれる」等の拒否系症状
    auto-skip-when:
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
      - 種別が「追加要望」または「その他」
      - エラー文言の記載がなく、症状が「表示されない」「データが変わらない」等の無反応系のみ
    ask-user-prompt: |
      この課題にはエラー文言の記載がないようです。エラーメッセージからの逆引き grep は省略してもよさそうですか？
    estimated-cost: 軽
```

---

## メンテナンス

新しいオプションを追加する場合は [_README.md](./_README.md) §メンテルール を参照。判定条件の変更はこのファイルのみで完結する（option-*.md 側は実行手順のみ）。
