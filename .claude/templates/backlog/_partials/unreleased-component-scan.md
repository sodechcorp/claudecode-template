# 未リリース積み残し検出: コンポーネント名候補リストの抽出手順

`docs/decisions.md` の当該課題（`{issueID}`）に該当する**全エントリ**（`## {issueID}:` で始まる見出しを Grep。降順記録のため同一課題が複数エントリに分かれていることがある＝再スコープの証跡。**最新エントリだけで打ち切らない**）と、存在すれば `docs/knowledge/cases/{issueKey}.md` の全文から、コンポーネント名らしき識別子（LWC/Aura ディレクトリ名・Apex クラス名等）を抽出し、暫定候補リストとする。

組織の地図があれば、文章から抜いた候補に次を足す（[option-lineage-map.md](../options/option-lineage-map.md)。足したものも候補なので、今回の課題の変更かはファイル・差分で確かめる）:
- `python scripts/python/sf-lineage/lineage.py uses <候補（LWC:名前・クラス名）>` と `who <候補>` でつながる LWC の親子・LWC が呼ぶ Apex（片方だけ資材に入るのを防ぐ）
- `modified --target-org <本番> --target-org <Sandbox>` の「Sandbox のほうが本番より新しい部品」「Sandbox にだけある部品」（本番に未リリースの変更の候補）のうち、候補とつながるもの（つながらないものは他の課題の変更でありうるので入れない）

> **同一セッション内キャッシュ（必須）**: release-preparer Phase 1（1a-1 / 2a-1）・option-org-drift-check Tier 0 のいずれかで本手順を一度実行済みの場合、同一セッション内では結果（暫定候補リスト）をそのまま再利用し、再走査しない。

呼び出し元（利用箇所）:
- [release-preparer.md](../../../agents/release-preparer.md) Phase 1 1a-1（資材マニフェスト再構築時の暫定候補リスト抽出）
- [release-preparer.md](../../../agents/release-preparer.md) Phase 1 2a-1（未リリース積み残しの突合）
- [option-org-drift-check.md](../options/option-org-drift-check.md) Tier 0 手順1-3（対象スコープ確定）
