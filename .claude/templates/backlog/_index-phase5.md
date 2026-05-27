# Phase 5 オプションインデックス（テスト）

backlog-tester が Phase 5 の Step 0b で参照する判定情報。8 オプション。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

```yaml
options:

  - name: option-sandbox-reproduction
    description: Sandbox 修正後の再現確認（修正前症状が出なくなったことを実機で確認）
    category: C
    auto-execute-when:
      - 種別がバグ（常時実行・修正後の再現確認は必須に近い）
      - Sandbox 環境で事象を再現できる場合
    auto-skip-when:
      - 種別が追加要望（再現確認の概念が無関係）
      - Sandbox で事象が再現しない場合（本番特有の条件）
    ask-user-prompt: |
      この課題は追加要望（または Sandbox 再現不可）のようです。Sandbox 修正後再現確認は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-prod-select-reference
    description: 本番 SELECT 参照（許可取得→実行→要約。実データ確認が必要な場合）
    category: D
    auto-execute-when:
      - 実データの状態確認が原因特定・テストに必要
      - Sandbox データが本番と大きく異なる可能性がある
      - 課題に「本番データ」「実データ確認」等のワード
    auto-skip-when:
      - Sandbox データで十分確認可能
      - データ変更を含まない純粋な UI 変更
      - 権限上の問題で本番 SELECT 不可
    ask-user-prompt: |
      Sandbox データで十分確認できそうです。本番 SELECT 参照は省略してもよさそうですか？
    estimated-cost: 重
    default-when-uncertain: skip

  - name: option-unit-test-creation
    description: Apex 単体テスト作成（新規・修正したメソッドの Apex テストクラス追加）
    category: B
    auto-execute-when:
      - 変更対象が Apex クラス・トリガー
      - 新規 Apex メソッドを追加
      - 既存テストカバレッジが低い（70% 未満）
    auto-skip-when:
      - Apex コードを含まない変更
      - 既存テストクラスで十分なカバレッジを確保済み
    ask-user-prompt: |
      この変更は Apex コードを含まないようです。Apex 単体テスト作成は省略してもよさそうですか？
    estimated-cost: 重

  - name: option-regression-test
    description: リグレッションテスト（変更によって既存機能が壊れていないかの確認）
    category: B
    auto-execute-when:
      - 変更対象が共通コンポーネント・共通ユーティリティ
      - 複数の機能から参照されるクラス・フィールド・オブジェクトを変更
      - 大規模修正（複数ファイル・複数メタデータタイプ）
    auto-skip-when:
      - 影響範囲が単一機能に閉じている最小修正
      - typo 修正・ラベル変更のみ
    ask-user-prompt: |
      この変更は単一機能に閉じた最小修正のようです。リグレッションテストは省略してもよさそうですか？
    estimated-cost: 中

  - name: option-edge-case-test
    description: 境界値・異常系テスト（null / 空文字 / 最大件数 / 権限なしユーザー等）
    category: C
    auto-execute-when:
      - 種別がバグ（エッジケースが原因の可能性）
      - 数値計算・日付計算・文字列処理を含む実装
      - 課題に「特定条件」「稀なケース」「一部ユーザーのみ」等のワード
    auto-skip-when:
      - 単純なラベル変更・設定変更
      - 入力バリデーションが無関係な管理画面操作のみ
    ask-user-prompt: |
      この修正は単純な設定変更のようです。境界値・異常系テストは省略してもよさそうですか？
    estimated-cost: 中

  - name: option-permission-test
    description: 権限・FLS テスト（異なるプロファイル・権限セットでの動作確認）
    category: C
    auto-execute-when:
      - 変更対象に権限セット・プロファイル・FLS が関与
      - 課題に「権限」「プロファイル」「見えない」「アクセスできない」等のワード
      - 新規フィールド・オブジェクト追加（FLS デフォルト設定の確認）
    auto-skip-when:
      - 権限とは無関係な処理修正
      - システム管理者のみが使う機能の変更
    ask-user-prompt: |
      この修正は権限・FLS に関係しないようです。権限・FLS テストは省略してもよさそうですか？
    estimated-cost: 中

  - name: option-performance-test
    description: パフォーマンステスト（応答時間・大量データ時の動作・ガバナ制限余裕）
    category: C
    auto-execute-when:
      - 課題に「遅い」「タイムアウト」「大量データ」「件数が多い」等のワード
      - バルク処理・バッチ Apex を含む
      - 一覧表示・レポート系の処理変更
    auto-skip-when:
      - データ件数が少ない単一レコード操作
      - 設定変更・ラベル変更のみ
    ask-user-prompt: |
      この修正はパフォーマンス影響が無さそうです。パフォーマンステストは省略してもよさそうですか？
    estimated-cost: 重
    default-when-uncertain: skip

  - name: option-security-audit
    description: セキュリティ監査（CRUD/FLS 一括確認・SOQL インジェクション・XSS・with sharing）
    category: D
    auto-execute-when:
      - 課題優先度が「高」または「緊急」でセキュリティ懸念あり
      - 変更対象に外部入力を受け取る処理（フォーム・API）
      - 課題に「セキュリティ」「不正アクセス」「情報漏洩」等のワード
      - 新規 Apex クラス追加（with sharing / CRUD / FLS 全確認）
    auto-skip-when:
      - 内部管理画面のみの変更（外部入力なし）
      - 設定・ラベル変更のみ
    ask-user-prompt: |
      この修正はセキュリティリスクが低い変更のようです。セキュリティ監査は省略してもよさそうですか？
    estimated-cost: 重
    default-when-uncertain: skip
```
