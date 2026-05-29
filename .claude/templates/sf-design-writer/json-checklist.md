## Phase 1.5 セルフレビューチェックリスト

全 JSON を生成し終えたら、**スクリプトを呼ぶ前に**以下を全件確認する。問題があれば修正してから Phase 2 へ進む。

### チェックリスト

- [ ] **決定木の適用漏れ**: 全ステップに対してステップ記述プロトコル（Q1〜Q5）を適用したか。`node_type: "process"` ばかりになっていないか（全部同じ図形 = 適用漏れのサイン）
- [ ] **object_ref / calls / branch の重複**: 同一ステップに複数が設定されていないか
- [ ] **node_type: "object" の使用禁止**: `"process"` + `object_ref` に統一
- [ ] **calls テキスト長**: 20文字以内か
- [ ] **抽象的タイトル禁止**: 「処理を実行」「データを取得」のような意味のないタイトルがないか
- [ ] **タイトルにクラス名・メソッド名を含めていないか**: クラス名・メソッド名は `method_name` フィールドに。`title` は日本語説明のみ
- [ ] **スコープ逸脱がないか**: 別Apexの内部実装を詳述していないか。外部呼び出しは `calls` + 高レベル説明にとどめているか
- [ ] **detail にコード混入禁止**: `detail` は日本語説明のみ。コードは sub_steps に
- [ ] **type フィールドの正確性**: このエージェントが扱うのは Apex/Batch/Flow/Integration のみ。LWC/画面フロー/Aura/Visualforce が混在していれば sf-screen-writer に委ねる
- [ ] **overview の品質**: 具体的なオブジェクト名・処理内容・連携先が含まれているか

チェックリストの確認後、必ずスクリプトで機械チェックを実行する:

```bash
python "{project_dir}/scripts/python/sf-doc-mcp/check_design_json.py" \
  --input "{tmp_dir}/{api_name}_design.json" \
  --type feature
```

- ERROR が出た場合: JSON を修正して再チェック。エラーが消えるまで Phase 2 へ進まない
- WARNING のみの場合: 内容を確認し、問題なければ続行してよい
- 「✅ 問題なし」が出た場合: Phase 2 へ進む
