# xlsx 断念時の investigation.md フロントマター巻き戻し

> **参照元**: `backlog.md` Phase 3 / Phase 4 の xlsx スクリプト失敗ゲートで「xlsx なしで続行」（`{xlsx_folder}` = null）が選ばれた場合に実行する。
>
> **目的**: Phase 1.5「作成する」選択時に [xlsx-setup.md](../xlsx-setup.md) §1.5.3 が investigation.md フロントマターへ書き込んだ `xlsx_folder` / `evidence_dir` は、Phase 3/4 で `{xlsx_folder}` を会話内変数として null に倒すだけでは書き換わらない。/compact 後の Phase 0d 再開時に Phase 0d はフロントマターから `xlsx_folder` を読み直すため、破棄したはずの値が復元され、後続 Phase の `update_records.py` がファイル未存在で exit 1 になる。

`{tmp_dir}` = `docs/logs/{issueID}/.tmp` に固定し、以下の内容で `{tmp_dir}/clear_xlsx_frontmatter.py` を Write する（同一セッション内で既に Write 済みなら使い回してよい）:

```python
import pathlib, re, sys
issue_id = sys.argv[1]
invest = pathlib.Path(f'docs/logs/{issue_id}/investigation.md')
text = invest.read_text(encoding='utf-8') if invest.exists() else ''
keys = {'xlsx_folder': 'null', 'evidence_dir': f'docs/logs/{issue_id}/evidence'}
if text.startswith('---'):
    end = text.index('---', 3)
    front = text[3:end]
    body = text[end+3:]
    for k, v in keys.items():
        if re.search(rf'^{k}:', front, re.MULTILINE):
            front = re.sub(rf'^{k}:.*$', f'{k}: {v}', front, flags=re.MULTILINE)
        else:
            front = front.rstrip('\n') + f'\n{k}: {v}\n'
    invest.write_text(f'---\n{front}---{body}', encoding='utf-8')
else:
    fm = '\n'.join(f'{k}: {v}' for k, v in keys.items())
    invest.write_text(f'---\n{fm}\n---\n\n{text}', encoding='utf-8')
print('[OK] investigation.md xlsx_folder/evidence_dir 巻き戻し完了')
```

Write 後、以下を実行する（置換対象は `{issueID}` のみ）:

```bash
python "{tmp_dir}/clear_xlsx_frontmatter.py" "{issueID}"
```
