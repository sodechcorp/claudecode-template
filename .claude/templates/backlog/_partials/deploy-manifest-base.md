# デプロイ対象差分の base コミット決定

`option-progressive-commits` 採用時は実装が複数コミットに分かれ、標準フローでは実装変更が未コミットの作業ツリーに残る。どちらを取り逃しても差分抽出が不完全になるため、**段階コミット一覧の先頭コミットの親（base）から差分を取得する**（先頭コミット自体の変更を含めるため `~1` で親を base にする。先頭コミットのハッシュそのものを base にすると、そのコミットで加えた変更が diff から漏れる）。

**base 取得**: `docs/logs/{issueID}/implementation-plan.md` の「## 段階コミット一覧」に記録された先頭コミットハッシュを読み、その親コミットを base とする:
```bash
python -c "import re,os; p=os.path.join('docs/logs/{issueID}','implementation-plan.md'); t=open(p,encoding='utf-8').read() if os.path.exists(p) else ''; m=re.search(r'段階コミット一覧.*?\n((?:\|.*\n)+)', t, re.S); rows=[r for r in (m.group(1).splitlines() if m else []) if re.match(r'\|\s*\d+\s*\|', r)]; print((rows[0].split('|')[2].strip()+'~1') if rows else '')"
```

- **base が取得できた場合**: `git diff --name-only {base} -- 'force-app/**'`（コミット済み・未コミットの両方を網羅）
- **base が取得できない場合**（標準フロー＝コミットなし・段階コミット一覧なし）: `git diff --name-only HEAD -- 'force-app/**'`（未コミットの作業ツリー差分）

呼び出し元（利用箇所）:
- [backlog-releaser.md](../../../agents/backlog-releaser.md) §2a. Sandbox の場合
- [release-preparer.md](../../../agents/release-preparer.md) Phase 1
- [option-diff-review.md](../options/option-diff-review.md) §1. diff の取得
