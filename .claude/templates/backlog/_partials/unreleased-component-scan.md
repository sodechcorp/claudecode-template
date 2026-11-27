# 未リリース積み残し検出: コンポーネント名候補リストの抽出手順

`docs/decisions.md` の当該課題（`{issueID}`）の**全エントリ**（見出し `## …` に `{issueID}` を含むもの。降順記録のため同一課題が複数エントリに分かれていることがある＝再スコープの証跡。**最新エントリだけで打ち切らない**）と、存在すれば `docs/knowledge/cases/{issueKey}.md` の全文を本文として、[option-org-drift-check.md](../options/option-org-drift-check.md) Tier 0 で比べられる部品（LWC・Aura・Apex クラス・Apex トリガー・Visualforce）の名前を次の 1.・2. で抜き出し、暫定候補リストとする。候補は種別と名前の組で扱う（同じ名前でも種別が違えば別の候補。資材マニフェストとの突き合わせ・Tier 0 でも組で照合する）。フロー・項目などほかの種別は抜き出さない（その積み残しは release-preparer Phase 1 の 2c が開発環境との差で見る）。

1. **force-app に在る部品**（機械的に拾う）: 次を実行し、`種別:名前` の行を全て候補にする（種別は Metadata API の名前。その前の行は、読んだ decisions.md のエントリの数・cases の有無と、そのエントリの見出し）。`force-app/main/default` の LWC・Aura のディレクトリ名と、Apex クラス・Apex トリガー・Visualforce ページ・Visualforce コンポーネントのファイル名のうち、本文に単語として出てくるものが出る（大文字小文字は区別しない。`<c-kebab-case>` のタグも拾う）
   ```bash
   cd "{project_dir}" && python -c "import re,sys,glob,os,pathlib; sys.stdout.reconfigure(encoding='utf-8'); k=sys.argv[1]; R=lambda f: open(f,encoding='utf-8-sig').read() if os.path.exists(f) else ''; e=[s for s in re.split('(?m)^(?=## )',R('docs/decisions.md')) if s.startswith('## ') and re.search('(?<![0-9A-Za-z_-])'+re.escape(k)+'(?![0-9A-Za-z_])',s.splitlines()[0])]; c=R('docs/knowledge/cases/'+k+'.md'); t='\n'.join(e+[c]); w={x.lower() for x in re.findall('[0-9A-Za-z_]+',t)}|{x[2:].replace('-','') for x in re.findall('(?<![0-9A-Za-z])c-[a-z0-9]+(?:-[a-z0-9]+)*',t)}; G=[('LightningComponentBundle','lwc/*/'),('AuraDefinitionBundle','aura/*/'),('ApexClass','classes/*.cls'),('ApexTrigger','triggers/*.trigger'),('ApexPage','pages/*.page'),('ApexComponent','components/*.component')]; r=sorted({(g,pathlib.Path(p).name.split('.')[0]) for g,q in G for p in glob.glob('force-app/main/default/'+q)}); print('本文: decisions.md のエントリ '+str(len(e))+' 件・cases '+('あり' if c else 'なし')); [print(s.splitlines()[0]) for s in e]; print('\n'.join(g+':'+n for g,n in r if n.lower() in w) or '該当なし')" {issueID}
   ```
2. **force-app に無い部品**（取得していない・ローカルから削除済みのもの。Tier 0 が「UAT のみ存在」で見つける対象なので落とさない）: 1. が見出しを出したエントリと cases を読み、部品の名前として書かれている英字の識別子のうち、次を候補にする。目印は、種別の語（LWC・Aura・コンポーネント・クラス・トリガー・ページ等）、拡張子（`.cls`・`.trigger`・`.page`・`.component`・`.cmp`・`.js`・`.html`）、タグ（`<c-kebab-case>`・`<c:名前>`）、`c/名前`・`@salesforce/apex/クラス名.` の形、命名（LWC は先頭が小文字の lowerCamelCase、Aura・Apex・Visualforce は PascalCase が多い）。メソッド名・変数名は入れない。部品の名前かどうか迷うものは入れる
   - 1. に出なかった名前: 目印から決まる種別で候補にする。種別が1つに決まらなければ、ありうる種別の全てで候補にする（違う種別で Tier 0 に問い合わせると「どちらにも無い」＝差分なしになり、黙って落ちる）
   - 1. に出た名前: 本文が 1. と別の種別として書いているとき（`X.cmp`・「Aura の X」・`<c:X>` 等）だけ、その種別で候補にする

組織の地図があれば、文章から抜いた候補に次を足す（[option-lineage-map.md](../options/option-lineage-map.md)。足したものも候補なので、今回の課題の変更かはファイル・差分で確かめる）:
- `python scripts/python/sf-lineage/lineage.py uses <候補>` と `who <候補>`（候補は地図の書き方で渡す。LWC は `LWC:名前`、Aura は `uses` では `Aura:名前`・`who` では `LWC:名前`、Visualforce ページは `VF:名前`、Apex クラス・トリガーは名前だけ）でつながる LWC の親子・LWC が呼ぶ Apex（片方だけ資材に入るのを防ぐ）
- `modified --target-org <本番> --target-org <Sandbox>` の「Sandbox のほうが本番より新しい部品」「Sandbox にだけある部品」（本番に未リリースの変更の候補）のうち、候補とつながるもの（つながらないものは他の課題の変更でありうるので入れない）

> **同一セッション内キャッシュ（必須）**: release-preparer Phase 1（1a-1 / 2a-1）・option-org-drift-check Tier 0 のいずれかで本手順を一度実行済みの場合、同一セッション内では結果（暫定候補リスト）をそのまま再利用し、再走査しない。

呼び出し元（利用箇所）:
- [release-preparer.md](../../../agents/release-preparer.md) Phase 1 1a-1（資材マニフェスト再構築時の暫定候補リスト抽出）
- [release-preparer.md](../../../agents/release-preparer.md) Phase 1 2a-1（未リリース積み残しの突合）
- [option-org-drift-check.md](../options/option-org-drift-check.md) Tier 0 手順1-3（対象スコープ確定）
