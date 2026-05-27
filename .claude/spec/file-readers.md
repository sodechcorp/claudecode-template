# ファイル読み込み（共通）

| 形式 | 方法 |
|---|---|
| .md / .txt / .csv / .json / .yml / .cls / .js / .html | Read ツールで直接読み込み |
| .xml（flow-meta.xml 等） | Read ツールで直接読み込み |
| .pdf | Read ツール（1回20ページまで。大きいPDFはページ指定で分割） |
| .xlsx | `python -c "import pandas as pd, sys; xl=pd.ExcelFile(sys.argv[1]); [print(f'=== {s} ===\n{pd.read_excel(xl,s).to_markdown(index=False)}\n') for s in xl.sheet_names]" "<ファイルパス>"` |
| .docx | `python -c "import docx, sys; doc=docx.Document(sys.argv[1]); [print(p.text) for p in doc.paragraphs]; [print('\|'+'\|'.join(c.text for c in r.cells)+'\|') for t in doc.tables for r in t.rows]" "<ファイルパス>"` |
| .pptx | `python -c "from pptx import Presentation; import sys; prs=Presentation(sys.argv[1]); [print(f'=== スライド{i+1} ===\n'+'\n'.join(s.text for s in slide.shapes if s.has_text_frame)) for i,slide in enumerate(prs.slides)]" "<ファイルパス>"` |

## sf コマンドが Git Bash で失敗する場合

```bash
SF_CLIENT_BIN="$(dirname "$(where sf | head -1 | sed 's/\\/\//g')")/../client/bin"
"$SF_CLIENT_BIN/node.exe" "$SF_CLIENT_BIN/run.js" <サブコマンド> <引数>
```
