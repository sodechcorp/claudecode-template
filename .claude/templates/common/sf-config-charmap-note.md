# 文字化けリスクと対策（sf-doc / sf-design 共通）

Claude LLM 生成段階で rare CJK 文字が近傍の頻出字に自動補正されるバイアスがある（例: 「俣」→「係」）。以下のルールを **作成者名・出力先・プロジェクト名の取得フロー全体** に適用すること。

| 対象 | 方法 | 理由 |
|---|---|---|
| 作成者名（人名） | description に値を埋め込まず、popup 直前に Bash で個別印字する | Bash stdout = IDE terminal 直接描画。LLM 生成を経由しないため 100% 正確 |
| 出力先パス | description に値を埋め込む | 一般字のみ構成でドリフトリスクが極めて低い |
| プロジェクト名（/sf-design のみ） | description に値を埋め込む | 同上 |

## 作成者名の印字パターン（必須）

AskUserQuestion で作成者名の選択肢を提示する**直前**に、必ず以下を実行して前回値を Bash 印字すること（LLM 生成を経由しないため文字化けしない）。改行・インデント付き多行スクリプトは tool-call の JSON パースを壊すリスクがあるため単一行で書く（詳細: [inline-script-hygiene.md](inline-script-hygiene.md)）:

```bash
python -c "import yaml, pathlib; p = pathlib.Path(r'{project_dir}/docs/.sf/sf_config.yml'); v = ((yaml.safe_load(p.read_text(encoding='utf-8')) or {}).get('author', '') if p.exists() else ''); print('━━ 前回の作成者名 ━━\n  ' + v + '\n━━━━━━━━━━━━━') if v else None"
```

その後 AskUserQuestion の description には「↑ 直前のBash出力に表示された値を使用」と記載し、作成者名の値そのものは description に埋め込まない。
