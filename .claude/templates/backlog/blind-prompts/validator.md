<!-- このファイルは backlog-planner.md および backlog-blind-validator.md から参照される。
     Task prompt を変更する場合はこのファイルのみを編集すること。 -->

```
Task(
  subagent_type="backlog-blind-validator",
  prompt="""
課題ID: {issueID}

課題本文:
{課題本文の全文}

コメント全文:
{全コメントのテキスト}

investigation.md の内容:
{investigation.md のテキスト}

approach-plan.md の採用方針（「採用方針:」行のみ。「### 判断ポイント一覧」以降は含めない）:
{採用方針テキスト}

implementation-plan.md の内容は一切伝えない。あなたは上記情報だけで独立に実装案を生成してください。
"""
)
```
