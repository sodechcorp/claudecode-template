# option-validator-blind

## 何をするか

implementation-plan を見ずに別の実装案を独立に生成して比較する（blind reviewer）。subagent として実行することで parent context の先入観を排除する。

## 実行手順（subagent 化必須）

**このオプションは必ず `backlog-blind-validator` subagent を Task ツールで起動して実行する。parent（backlog-planner）内で直接実行してはならない（blind 性が崩れる）。二段ネストを避けるため、起動自体も backlog-planner ではなく backlog.md（本体）が Phase 3（implementation-plan.md 保存直後）に行う。**

backlog.md（本体）が用意する引き渡し情報（investigation.md・approach-plan.md は既に disk 上にあるため Read で取得する）:
1. 課題 ID（Backlog issue key）
2. 課題本文の全文
3. 全コメントのテキスト
4. investigation.md の内容（調査結果）
5. approach-plan.md の「採用方針」のみ（「採用方針:」行の記述。「### 判断ポイント一覧」以降の実装詳細は含めない）
6. 以下を明示する: 「implementation-plan.md の内容は一切伝えない。あなたは上記情報だけで独立に実装案を生成してください」

**禁止事項**: prompt に implementation-plan.md の内容（ファイル本文・要約・参照のいずれも）を含めないこと。含めた時点で blind 性が崩壊する。

subagent が返す内容:
- 独立に生成した実装案（処理構造・データ設計・SOQL・エラーハンドリング）
- parent の implementation-plan との相違点（blind 差異）

## 出力

implementation-plan.md に追記:

## blind 実装案レビュー

### subagent 独立案の概要

{subagent が生成した案の主要ポイント}

### parent 案との相違点（blind 差異）

| 判断ポイント | parent 案 | blind 案 | 採用判断 |
|---|---|---|---|
| 処理構造 | ... | ... | parent / blind / 統合 |
| データ設計 | ... | ... | ... |
