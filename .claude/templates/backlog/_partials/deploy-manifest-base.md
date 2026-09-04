# デプロイ対象差分の base コミット決定

`option-progressive-commits` 採用時は実装が複数コミットに分かれ、標準フローでは実装変更が未コミットの作業ツリーに残る。どちらを取り逃しても差分抽出が不完全になるため、**段階コミット一覧の先頭コミットの親（base）から差分を取得する**（先頭コミット自体の変更を含めるため `~1` で親を base にする。先頭コミットのハッシュそのものを base にすると、そのコミットで加えた変更が diff から漏れる）。

**base 取得**: `docs/logs/{issueID}/implementation-plan.md` の「## 段階コミット一覧」に記録された先頭コミットハッシュを読み、その親コミットを base とする:
```bash
python -c "import re,os; p=os.path.join('docs/logs/{issueID}','implementation-plan.md'); t=open(p,encoding='utf-8').read() if os.path.exists(p) else ''; m=re.search(r'^##\s*段階コミット一覧\s*\n(.*?)(?=^##\s|\Z)', t, re.S|re.M); section=m.group(1) if m else ''; rows=[r for r in section.splitlines() if re.match(r'\|\s*\d+\s*\|', r)]; print((rows[0].split('|')[2].strip()+'~1') if rows else '')"
```

- **base が取得できた場合**: `{ git diff --name-only {base} -- 'force-app/**'; git ls-files --others --exclude-standard -- 'force-app/**'; } | sort -u`（コミット済み・未コミット・未追跡（新規）ファイルの全てを網羅。`git diff` は untracked ファイルを列挙しないため `git ls-files --others` で補う）
- **base が取得できない場合**（標準フロー＝コミットなし・段階コミット一覧なし）: `{ git diff --name-only HEAD -- 'force-app/**'; git ls-files --others --exclude-standard -- 'force-app/**'; } | sort -u`（未コミット・未追跡（新規）ファイルを含む作業ツリー差分）

呼び出し元（利用箇所）:
- [backlog-releaser.md](../../../agents/backlog-releaser.md) §2a. Sandbox の場合
- [release-preparer.md](../../../agents/release-preparer.md) Phase 1
- [option-diff-review.md](../options/option-diff-review.md) §1. diff の取得
