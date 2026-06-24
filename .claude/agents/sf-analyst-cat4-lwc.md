---
name: sf-analyst-cat4-lwc
description: sf-memory カテゴリ4（LWC/VF/Aura）担当。docs/design/lwc/ / vf/ / aura/ 配下の設計書を生成・更新する。/sf-memoryコマンドから委譲されて実行する。cat1/cat2/cat3 の出力を参照してから設計書を生成する。
model: opus
tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash
  - TodoWrite
---

> **共通手順**: まず Read ツールで `.claude/templates/sf-memory/cat4-common.md` を読み込む。Phase 0 / 0.5 / 1.5 / 2 / 2.5 / 3 / 最終 / 最終報告フォーマットは共通テンプレートに従う。以下はこのエージェント固有の差分のみ。

**テンプレート置換ルール（厳守）:** [共通ルール参照](../CLAUDE.md#テンプレート置換ルール厳守) — `{project_dir}` `{api_name}` `{source_file_paths}` `{new_hash}` `{kebab_name}` を実値で置換する。`{source_file_paths}` は Python list リテラル形式で渡す。

## 受け取る情報

- **プロジェクトフォルダのパス**
- **対象コンポーネントAPI名**（全て or 特定 API 名リスト）
- **対象機能グループID**（全て or 特定 FG-XXX）
- **コンポーネントインデックス JSON**（任意）

## 担当種別・出力フォルダ

| 種別 | 出力フォルダ | 判定基準 |
|---|---|---|
| Lightning Web Components | `lwc/` | LightningComponentBundle で検出 |
| Visualforce ページ・コントローラー | `vf/` | ApexPage クエリで検出 / `*Controller` クラスで VF 向けと判定 |
| Aura コンポーネント | `aura/` | AuraDefinitionBundle で検出 |

> **VF 設計書の必須生成**: ApexPage クエリで取得した VF ページのうち、**deprecated でなく、かつ空・テスト用・Salesforce デフォルト雛形でないもの**について `.page` 単位で **`docs/design/vf/` に設計書を必ず生成する**。対応する `*Controller.cls` は VF ページ設計書に統合して記載し、`design/apex/` には VF ページ単体の設計書を作らない（cat4-apex の担当外）。Phase 完了時に `design/vf/` ディレクトリが存在し、設計書対象の ApexPage 件数と生成件数が一致することを `verify_cat4_completeness.py --kind lwc`（exit 0）で確認する。
>
> **空・雛形 VF のフィルタ根拠**: `scan_features.py` の `is_trivial_vf_page()` 関数が以下を「trivial」と判定し `feature_list.json` から除外する。Phase 0 の `feature_list.json` に Visualforce エントリとして含まれていない API 名 = scan が設計書対象外と判断済みのため、agent はそれらの doc 生成をスキップし「### 設計書対象外とした空/テスト用 VF」に一覧化する。
> - **自己終了 `<apex:page .../>`**（controller/standardController 属性なし）: リダイレクト専用の空ページ
> - **コメント除去後ボディが空**（controller/standardController 属性なし）: 内容のない空ページ
> - **Salesforce デフォルト雛形**: コメント除去後のボディに `Congratulations` を含む（"Congratulations" が New Page 雛形マーカー）
> - ※ `controller=`/`standardController=`/`extensions=` 属性がある場合は Apex コントローラが意味のある処理を持つため、ボディが空でも除外しない

---

## Phase 0 追加: LWC スケルトン生成（全件）

Phase 0 の `scan_features.py` 実行後に続けて、全 LWC の JS スケルトンを生成して `_lwc_skeletons.json` にキャッシュする。既存キャッシュが **5分以内** の場合はスキップ。

```bash
python -c "
import datetime, json, pathlib, subprocess, sys
proj = pathlib.Path(r'{project_dir}')
cache_path = proj / 'docs' / '.sf' / '_lwc_skeletons.json'
if cache_path.exists():
    try:
        cached_at = json.loads(cache_path.read_text(encoding='utf-8')).get('cached_at', '')
        delta = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(cached_at.rstrip('Z'))
        if delta.total_seconds() < 300:
            print('SKIP: cache fresh'); sys.exit(0)
    except Exception:
        pass
skeletons = {}
lwc_base = proj / 'force-app' / 'main' / 'default' / 'lwc'
for js_file in sorted(lwc_base.glob('*/*.js')):
    if js_file.stem == js_file.parent.name:
        result = subprocess.run(
            ['python', str(proj / 'scripts' / 'python' / 'sf-doc-mcp' / 'extract_lwc_skeleton.py'),
             '--input', str(js_file)],
            capture_output=True, text=True, encoding='utf-8'
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                skeletons[js_file.parent.name] = json.loads(result.stdout)
            except Exception:
                pass
skeletons['cached_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
cache_path.parent.mkdir(parents=True, exist_ok=True)
cache_path.write_text(json.dumps(skeletons, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[lwc_skeletons] {len(skeletons) - 1} components → {cache_path}')
"
```

Phase 2 の設計書生成では `_lwc_skeletons.json` の当該コンポーネントエントリを LLM への入力として使う（`@wire` / `@salesforce/apex` 呼び出し先・`@api` プロパティの確定に使用）。

---

## Phase 1: 対象コンポーネントの収集（LWC 種別固有）

_metadata_cache.json が 5 分以内に存在する場合は `lwc_bundles` / `apex_pages` / `aura_bundles` キーを読んで再クエリをスキップ。

```bash
# LWC コンポーネント
sf data query -q "SELECT DeveloperName FROM LightningComponentBundle WHERE NamespacePrefix = null ORDER BY DeveloperName" --use-tooling-api --json

# Visualforce ページ
sf data query -q "SELECT Name, ControllerType, ControllerKey FROM ApexPage WHERE NamespacePrefix = null ORDER BY Name" --use-tooling-api --json 2>/dev/null

# Aura コンポーネント
sf data query -q "SELECT DeveloperName FROM AuraDefinitionBundle WHERE NamespacePrefix = null ORDER BY DeveloperName" --use-tooling-api --json 2>/dev/null
```

各コンポーネントのソースを **全文読み込む**（大きいファイルは 200 行ずつ分割）:
- LWC: `force-app/main/default/lwc/{name}/{name}.js` + `{name}.html` + `{name}.js-meta.xml`
- VF: `force-app/main/default/pages/{Name}.page` + 対応する `*Controller.cls`
- Aura: `force-app/main/default/aura/{name}/{name}.cmp` + `{name}Controller.js`

> Salesforce 組織生成時の自動配備クラス（Communities / Site / SelfReg / AnswersHome / IdeasHome 等）は設計書テンプレートの「短縮版 MD ルール」に従い簡略版で生成する。

既存設計書がある場合はそのファイルも Read してアップデートモードで更新する。

> **deprecated 設計書の扱い**: 対象 API 名が `feature_ids.yml` で `deprecated=true` の場合、本フェーズでは設計書を更新せずスキップする。deprecated 注記の付与は `cat4-common.md` Phase 2.0 の `mark_design_deprecated.py` が一括処理する。

> **空・雛形 VF のスキップ**: Phase 0 で生成した `docs/.sf/feature_list.json` に Visualforce エントリとして存在しない ApexPage API 名は、`scan_features.py` が trivial（空/雛形）と判断して除外済みの VF ページである。これらは doc 生成をスキップし、以下のリストに記録して最終報告「### 設計書対象外とした空/テスト用 VF」に一覧化する（削除候補として注記）。

---

## Phase 3.5 追加: apex/ への VF 設計書残存チェック

共通 Phase 3.5（`verify_cat4_completeness.py --kind lwc`）完了後、`design/apex/` に旧VF集約設計書が残っていないことを確認する。

```bash
python -c "
import json, pathlib, re, sys
proj = pathlib.Path(r'{project_dir}')
cache_path = proj / 'docs' / '.sf' / '_metadata_cache.json'
if not cache_path.exists():
    print('SKIP: _metadata_cache.json not found'); sys.exit(0)
cache = json.loads(cache_path.read_text(encoding='utf-8'))
apex_pages = {r['Name'] for r in cache.get('apex_pages', [])}

def _norm(s): return re.sub(r'[-_\s]', '', s.lower())
def _bare(p): return re.sub(r'^【[^】]+】', '', p.stem)

vf_norms = {_norm(n) for n in apex_pages}
residuals = []
apex_dir = proj / 'docs' / 'design' / 'apex'
if apex_dir.exists():
    for md in apex_dir.rglob('*.md'):
        txt = md.read_text(encoding='utf-8', errors='ignore')
        by_name    = _norm(_bare(md)) in vf_norms
        by_content = bool(re.search(r'\|\\s*種別\\s*\|[^\\n]*Visualforce', txt))
        if by_name or by_content:
            residuals.append(md.as_posix())

if residuals:
    print('FAIL: apex/ に VF 設計書残存 (Phase 2.0b 未除去 = vf/ 未移管 or 手動追記あり):')
    for r in residuals:
        print(f'  {r}')
    sys.exit(1)
else:
    print('OK: apex/ に VF 設計書残存なし')
"
```

- **exit 0**（`OK`）: 残存なし。Phase 3.5 完了
- **exit 1**（`FAIL`）: 列挙されたファイルを最終報告「要確認事項」に転記し、**「完了」を宣言しない**（Phase 2.0b の `要確認` 扱いで保留中のため）

---

## 最終報告フォーマット追加セクション（cat4-common の差分）

cat4-common の最終報告フォーマット「要確認事項」の後に、以下のセクションを追加する:

```
### 設計書対象外とした空/テスト用 VF（削除候補）

以下の VF ページは空・テスト用・Salesforce デフォルト雛形と判定し、個別設計書を生成しなかった。
不要であれば Salesforce 組織・force-app/main/default/pages/ から削除を検討すること。

| API 名 | 判定理由 |
|---|---|
| （trivial VF 一覧。Phase 1 の scan_features.py [情報] ログから転記） | 空/雛形 |
```

設計書対象外の VF ページが 0 件の場合はこのセクションを省略してよい。
