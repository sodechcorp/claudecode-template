"""
force-app/ と docs/design/ を走査して機能一覧を JSON 出力する。

機能IDは docs/feature_ids.yml を唯一の台帳として管理する。
- 既存API名は台帳のIDを再利用
- 新規は末尾に追番
- 今回見つからなかったものは deprecated=true にしてID欠番を保持

Usage: python scan_features.py --project-dir <path>
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from feature_id_ledger import (
    load_ledger, save_ledger, resolve_id, mark_deprecated, _make_key,
)
from text_cleaning import clean_tech_business, translate_sf_objects, translate_trigger_events


FEATURE_TYPES = {
    "classes":   "Apex",
    "triggers":  "Trigger",
    "flows":     "Flow",
    "lwc":       "LWC",
    "aura":      "Aura",
}

BATCH_PATTERNS       = re.compile(r"\bDatabase\.Batchable\b", re.IGNORECASE)
SCHED_PATTERNS       = re.compile(r"\bSchedulable\b", re.IGNORECASE)
TEST_PATTERNS        = re.compile(r"@IsTest|@isTest|isTest", re.IGNORECASE)
INTEGRATION_PATTERNS = re.compile(
    r"\bHttp\b|\bHttpRequest\b|\bHttpResponse\b"
    r"|\bHttpCalloutMock\b"
    r"|\bWebServiceCallout\b",
    re.IGNORECASE,
)

FLOW_NS = "http://soap.sforce.com/2006/04/metadata"


# Apex クラス名の suffix → 和名ロール（fallback overview 生成用）
_APEX_SUFFIX_ROLES = [
    ("TriggerHandler", "トリガーハンドラ"),
    ("FlowStarter",   "フロー起動クラス"),
    ("Controller",    "コントローラ"),
    ("Handler",       "ハンドラ"),
    ("Scheduler",     "スケジューラ"),
    ("Schedule",      "スケジューラ"),
    ("Service",       "サービス"),
    ("Helper",        "ヘルパー"),
    ("Utility",       "ユーティリティ"),
    ("Util",          "ユーティリティ"),
    ("Factory",       "ファクトリ"),
    ("Batch",         "バッチ"),
    ("Wrapper",       "ラッパー"),
    ("Builder",       "ビルダー"),
    ("Mock",          "モッククラス"),
    ("Mapper",        "マッパー"),
    ("Validator",     "バリデータ"),
    ("Parser",        "パーサ"),
    ("Resolver",      "リゾルバ"),
    ("Processor",     "プロセッサ"),
    ("Starter",       "起動クラス"),
    ("Entity",        "エンティティ"),
]

# Apex クラス名の prefix → 和名アクション（fallback overview 生成用）
# verb-noun 形式（CreateXxx / CopyXxx / VerifyXxx 等）を想定。
_APEX_PREFIX_ACTIONS = [
    ("Create",  "作成クラス"),
    ("Copy",    "コピークラス"),
    ("Delete",  "削除クラス"),
    ("Update",  "更新クラス"),
    ("Verify",  "検証クラス"),
    ("Select",  "選択クラス"),
    ("Search",  "検索クラス"),
    ("Fetch",   "取得クラス"),
    ("Get",     "取得クラス"),
    ("Send",    "送信クラス"),
    ("Import",  "インポートクラス"),
    ("Export",  "エクスポートクラス"),
    ("Generate","生成クラス"),
    ("Convert", "変換クラス"),
    ("Register","登録クラス"),
]


def _apex_role_from_name(api_name: str) -> str:
    """クラス名の suffix/prefix から「{残り} の {role}」形式の fallback overview を生成する。

    優先順:
      1. suffix マッチ（例: BulkPaymentController → "BulkPayment のコントローラ"）
      2. prefix マッチ（例: CreateCustomerUser → "CustomerUser の作成クラス"）
      一致しない場合は空文字を返す。
    """
    for suffix, role_ja in _APEX_SUFFIX_ROLES:
        if api_name.endswith(suffix) and len(api_name) > len(suffix):
            prefix = api_name[:-len(suffix)]
            prefix_ja = clean_tech_business(prefix)
            return f"{prefix_ja} の{role_ja}" if prefix_ja else role_ja
    for prefix_en, role_ja in _APEX_PREFIX_ACTIONS:
        if api_name.startswith(prefix_en) and len(api_name) > len(prefix_en):
            rest = api_name[len(prefix_en):]
            rest_ja = clean_tech_business(rest)
            return f"{rest_ja} の{role_ja}" if rest_ja else role_ja
    return ""


def extract_javadoc(path: Path, api_name: str = "", design_doc: str | None = None) -> str:
    """Apex クラスの概要を抽出する。

    優先順:
      1. docs/design/ 配下の対応MDファイルの title 行（`# 【F-XXX】APIName — 説明文`）
      2. クラス宣言の直前にある javadoc (`/** ... */` → `public class X`)
      3. ファイル先頭の javadoc（クラス直前でなくても可）
      4. クラス名 suffix からのヒューリスティック生成（api_name が渡された場合）

    SFデフォルトの英語ボイラープレート javadoc（`An apex page controller that...` 等）は
    (2)(3) で除外されて (4) に fallback する。
    """
    # 1. Design doc MD を最優先
    doc_title = extract_design_doc_title(design_doc)
    if doc_title:
        return doc_title

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return _apex_role_from_name(api_name) if api_name else ""

    def _first_meaningful_line(javadoc_body: str) -> str:
        lines = [l.strip().lstrip('*').strip() for l in javadoc_body.split('\n')
                 if l.strip().strip('*').strip() and not l.strip().lstrip('*').strip().startswith('@')]
        return lines[0] if lines else ""

    # 2. クラス宣言の直前の javadoc を優先
    m = re.search(
        r'/\*\*(.*?)\*/\s*(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:public|global|private|protected)\s+'
        r'(?:(?:abstract|virtual|with\s+sharing|without\s+sharing|inherited\s+sharing)\s+)*'
        r'class\s+\w+',
        text, re.DOTALL,
    )
    if m:
        line = _first_meaningful_line(m.group(1))
        if line and not _is_default_javadoc(line):
            return clean_tech_business(line)

    # 3. ファイル先頭の javadoc（メソッド名・デフォルトテンプレ除外）
    METHOD_NAMES = {"start", "execute", "finish", "run", "handle", "init", "constructor"}
    m = re.search(r'/\*\*(.*?)\*/', text, re.DOTALL)
    if m:
        line = _first_meaningful_line(m.group(1))
        if line and line.lower() not in METHOD_NAMES and not _is_default_javadoc(line):
            return clean_tech_business(line)

    # 4. Suffix/Prefix ヒューリスティック
    return _apex_role_from_name(api_name)


def extract_trigger_overview(trigger_path: Path, design_doc: str | None = None) -> str:
    """Triggerファイルから概要を抽出する。

    優先順:
      1. docs/design/ の MD title
      2. ファイル先頭の javadoc
      3. trigger 宣言から自動生成（例: `FeedComment の after insert トリガー`）
    """
    doc_title = extract_design_doc_title(design_doc)
    if doc_title:
        return doc_title
    try:
        text = trigger_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    m = re.match(r'\s*/\*\*(.*?)\*/', text, re.DOTALL)
    if m:
        lines = [l.strip().lstrip('*').strip() for l in m.group(1).split('\n')
                 if l.strip().strip('*').strip() and not l.strip().lstrip('*').strip().startswith('@')]
        if lines and not _is_default_javadoc(lines[0]):
            return clean_tech_business(lines[0])
    m = re.search(r'trigger\s+\w+\s+on\s+(\w+)\s*\(([^)]+)\)', text)
    if m:
        obj = translate_sf_objects(m.group(1))
        events = translate_trigger_events(m.group(2))
        return f"{obj} の {events} トリガー"
    return ""


def extract_lwc_overview(lwc_dir: Path, design_doc: str | None = None) -> str:
    """LWC コンポーネントバンドルから概要を抽出する。

    優先順:
      1. docs/design/lwc/ の MD title
      2. .js-meta.xml の <description> / <masterLabel>
      3. .js の冒頭 JSDoc（`/** ... */`）
      4. .js の最初の単行コメント（`// ...`）
    """
    doc_title = extract_design_doc_title(design_doc)
    if doc_title:
        return doc_title
    name = lwc_dir.name
    meta = lwc_dir / f"{name}.js-meta.xml"
    if meta.exists():
        try:
            content = meta.read_text(encoding="utf-8", errors="ignore")
            # namespace を意識せず Regex で抜く（XML 名前空間差異を許容）
            for tag in ("description", "masterLabel"):
                m = re.search(rf'<{tag}>(.*?)</{tag}>', content, re.DOTALL)
                if m:
                    val = m.group(1).strip()
                    if val:
                        return clean_tech_business(val)
        except Exception:
            pass
    # Fallback: .js
    js = lwc_dir / f"{name}.js"
    if js.exists():
        try:
            text = js.read_text(encoding="utf-8", errors="ignore")
            # 2a: 先頭 JSDoc
            m = re.match(r'\s*/\*\*(.*?)\*/', text, re.DOTALL)
            if m:
                lines = [l.strip().lstrip('*').strip() for l in m.group(1).split('\n')
                         if l.strip().strip('*').strip() and not l.strip().lstrip('*').strip().startswith('@')]
                if lines:
                    return clean_tech_business(lines[0])
            # 2b: 最初に出現する `// コメント` を拾う（import 後の概要コメントを想定）
            for line in text.split('\n')[:30]:
                stripped = line.strip()
                if stripped.startswith('//'):
                    val = stripped.lstrip('/').strip()
                    if val and len(val) > 2:
                        return clean_tech_business(val)
        except Exception:
            pass
    return ""


def extract_vf_overview(page_meta_path: Path, design_doc: str | None = None) -> str:
    """Visualforce ページから概要を抽出する。

    優先順:
      1. docs/design/ の MD title
      2. .page-meta.xml の <description> → <label>
      3. .page の <title> タグ
    """
    doc_title = extract_design_doc_title(design_doc)
    if doc_title:
        return doc_title
    try:
        content = page_meta_path.read_text(encoding="utf-8", errors="ignore")
        for tag in ("description", "label"):
            m = re.search(rf'<{tag}>(.*?)</{tag}>', content, re.DOTALL)
            if m:
                val = m.group(1).strip()
                if val:
                    return clean_tech_business(val)
    except Exception:
        pass
    # .page ファイルの <title> を fallback
    page_path = page_meta_path.with_name(page_meta_path.name.replace(".page-meta.xml", ".page"))
    if page_path.exists():
        try:
            text = page_path.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r'<title>\s*(.*?)\s*</title>', text, re.DOTALL)
            if m:
                val = m.group(1).strip()
                if val:
                    return clean_tech_business(val)
        except Exception:
            pass
    return ""


_VF_CONTROLLER_ATTRS = re.compile(
    r'\b(?:controller|standardController|extensions)\s*=', re.IGNORECASE
)


def is_trivial_vf_page(page_meta_path: Path) -> bool:
    """空・自己終了・Salesforce デフォルト雛形の VF ページを判定する。

    True の場合、機能一覧・個別設計書の対象外とする（保守的に content ベースのみ）。
    判定基準:
      1. .page 本体が存在しない → False（安全側で除外しない）
      2. <apex:page .../> 自己終了かつ controller/standardController 属性なし → True
      3. コメント除去後のボディが空かつ controller/standardController 属性なし → True
      4. Salesforce デフォルト雛形マーカーを body_no_comments に含む → True
    ※ controller/extensions 属性がある場合は Apex コントローラが意味のある処理を持つため除外しない
    """
    page_path = page_meta_path.with_name(
        page_meta_path.name.replace(".page-meta.xml", ".page"))
    if not page_path.exists():
        return False  # .page 本体なし → 判定不能。安全側で除外しない
    try:
        text = page_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    m = re.search(
        r'<apex:page\b([^>]*?)(/\s*>|>(.*?)</apex:page>)',
        text, re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return False
    opening_attrs = m.group(1)
    has_controller = bool(_VF_CONTROLLER_ATTRS.search(opening_attrs))
    if has_controller:
        return False  # controller あり → Apex コントローラが処理を持つ → 非trivial
    tail = m.group(2)
    if tail.lstrip().startswith('/'):
        return True  # 自己終了 <apex:page .../> (controller なし)
    body = m.group(3) or ""
    body_no_comments = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL).strip()
    if not body_no_comments:
        return True  # 空ボディ（コメントのみ、controller なし）
    # Salesforce デフォルト雛形: コメント除去後の body にマーカーを確認
    if "Congratulations" in body_no_comments:
        return True
    return False


def extract_aura_overview(aura_dir: Path, design_doc: str | None = None) -> str:
    """Aura コンポーネントバンドルから概要を抽出する。

    優先順:
      1. docs/design/aura/ の MD title
      2. .cmp-meta.xml の <description>（デフォルト値は除外）
      3. .design の <design:component label="..."> 属性
      4. .cmp の冒頭 HTML コメント
    """
    doc_title = extract_design_doc_title(design_doc)
    if doc_title:
        return doc_title
    name = aura_dir.name
    DEFAULT_DESCS = {"A Lightning Component Bundle"}

    # 1. cmp-meta.xml の description
    meta = aura_dir / f"{name}.cmp-meta.xml"
    if meta.exists():
        try:
            content = meta.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r'<description>(.*?)</description>', content, re.DOTALL)
            if m:
                val = m.group(1).strip()
                if val and val not in DEFAULT_DESCS:
                    return clean_tech_business(val)
        except Exception:
            pass

    # 2. .design ファイルの component label 属性（App Builder 表示名）
    design = aura_dir / f"{name}.design"
    if design.exists():
        try:
            content = design.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r'<design:component[^>]*\blabel\s*=\s*"([^"]+)"', content)
            if m:
                val = m.group(1).strip()
                if val:
                    return clean_tech_business(val)
        except Exception:
            pass

    # 3. .cmp の冒頭の HTML コメント
    cmp = aura_dir / f"{name}.cmp"
    if cmp.exists():
        try:
            text = cmp.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r'<!--\s*(.*?)\s*-->', text, re.DOTALL)
            if m:
                val = m.group(1).strip()
                # "attribute" など雑なコメントは除外
                if val and len(val) > 5 and "attribute" not in val.lower():
                    return clean_tech_business(val.split('\n')[0])
        except Exception:
            pass
    return ""


def extract_trigger_handler(trigger_path: Path) -> str | None:
    """トリガーファイルからハンドラークラス名を抽出する。
    見つからない場合は {TriggerStem}Handler を推測して返す。
    推測したクラスファイルが classes/ に存在しない場合は None を返す。
    """
    classes_dir = trigger_path.parent.parent / "classes"
    try:
        text = trigger_path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'\b(\w+Handler)\b', text)
        if m:
            handler_name = m.group(1)
            if not (classes_dir / f"{handler_name}.cls").exists():
                print(f"[警告] {trigger_path.name}: ハンドラー {handler_name}.cls が classes/ に存在しません → absorb_into=None", file=sys.stderr)
                return None
            return handler_name
    except Exception:
        pass
    # フォールバック: OpportunityTrigger → OpportunityTriggerHandler
    stem = trigger_path.stem
    guessed = f"{stem}Handler"
    if not (classes_dir / f"{guessed}.cls").exists():
        print(f"[警告] {trigger_path.name}: ハンドラークラス名を推測 → {guessed} だが classes/ に存在しません → absorb_into=None", file=sys.stderr)
        return None
    print(f"[警告] {trigger_path.name}: ハンドラークラス名を推測 → {guessed}", file=sys.stderr)
    return guessed


def classify_apex(path: Path) -> str:
    """Apexクラスの種別を判定する (Batch / Integration / Apex)

    Schedulable のみを実装するクラス（バッチの起動設定だけ）は
    独立した機能として扱わず None を返してスキャン対象から除外する。
    スケジュール情報（cron式）は対応する Batch の設計書の trigger に記載する。

    Http / HttpRequest / HttpResponse を使う外部連携クラスは Integration に分類する。
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return "Apex"
    if TEST_PATTERNS.search(text):
        return None          # テストクラスは除外
    if BATCH_PATTERNS.search(text):
        return "Batch"
    if SCHED_PATTERNS.search(text):
        return None          # Schedulable のみ → Batch の trigger に吸収
    if INTEGRATION_PATTERNS.search(text):
        return "Integration"
    return "Apex"


def get_flow_info(path: Path) -> tuple[str, str, str]:
    """フロー XML から label, processType, description を取得する"""
    try:
        content = path.read_bytes()
        tree = ET.fromstring(content)
        ns = {"sf": FLOW_NS}
        label = tree.findtext("sf:label", namespaces=ns) or path.stem
        ptype = tree.findtext("sf:processType", namespaces=ns) or "Flow"
        desc  = tree.findtext("sf:description", namespaces=ns) or ""
        return label, ptype, desc
    except Exception:
        return path.stem, "Flow", ""


# 種別 → docs/design/ 配下のサブフォルダ名マッピング（cat4 の出力先と一致）
_TYPE_TO_DESIGN_FOLDER = {
    "Apex":        "apex",
    "Trigger":     "apex",
    "Batch":       "batch",
    "Flow":        "flow",
    "画面フロー":   "flow",
    "LWC":         "lwc",
    "Aura":        "aura",
    "Visualforce": "vf",
    "Integration": "integration",
}


def get_design_doc(docs_design_dir: Path, name: str, ftype: str = "") -> str | None:
    """docs/design/ 配下から機能名に対応するMDファイルのパスを返す。

    マッチングは「スペース・ハイフン除去した小文字一致（stem 完全一致）」のみで行い、
    異なる種別同士の誤マッチ（例: Flow `QuoteRequestPending` が LWC `request.md` に
    マッチしてしまう）を防ぐ。

    種別が指定された場合はまず対応サブフォルダ内を探索し、見つからない場合のみ
    docs/design/ 全体を再検索する。
    """
    def _normalize(s: str) -> str:
        return re.sub(r'[-_\s]', '', s.lower())

    target = _normalize(name)

    def _match(md: Path) -> bool:
        # ファイル名から "【CMP-XXX】" や "【CMP-XXX〜CMP-YYY等】" などのプレフィックスを除去
        stem = re.sub(r'^【[^】]+】', '', md.stem)
        return _normalize(stem) == target

    # 1. 種別に対応するサブフォルダ内をまず検索（誤マッチ防止）
    folder = _TYPE_TO_DESIGN_FOLDER.get(ftype)
    if folder:
        sub_dir = docs_design_dir / folder
        if sub_dir.exists():
            for md in sub_dir.rglob("*.md"):
                if _match(md):
                    return md.as_posix()
            # 同種フォルダに無ければ None を返す（他種別フォルダに誤マッチさせない）
            return None

    # 2. 種別不明時のみ全体を完全一致で検索
    for md in docs_design_dir.rglob("*.md"):
        if _match(md):
            return md.as_posix()
    return None


def extract_design_doc_title(md_path: str | None) -> str:
    """docs/design/ 配下の MD ファイルから title 行の説明文を抽出する。

    想定フォーマット: `# 【F-XXX】APIName — 説明文` （全角ダッシュ `—` 区切り）
    `—` 以降を説明文として返す。見つからない場合は空文字。
    """
    if not md_path:
        return ""
    try:
        p = Path(md_path)
        if not p.exists():
            return ""
        # 最初の `# ` 行を取得
        for line in p.read_text(encoding="utf-8", errors="ignore").split("\n")[:20]:
            line = line.strip()
            if line.startswith("# "):
                # `# 【F-XXX】APIName — 説明文` から説明文だけ取り出す
                for sep in (" — ", " – ", " - "):
                    if sep in line:
                        desc = line.split(sep, 1)[1].strip()
                        if desc:
                            return desc
                # `—` が無ければ `】` 以降をそのまま使う
                if "】" in line:
                    rest = line.split("】", 1)[1].strip()
                    if rest:
                        return rest
                break
    except Exception:
        pass
    return ""


# Salesforce 新規作成時のデフォルト javadoc（ノイズ扱いで除外）
_DEFAULT_JAVADOC_PATTERNS = [
    re.compile(r'^An apex (page )?controller that\b', re.IGNORECASE),
    re.compile(r'^An apex class that\b', re.IGNORECASE),
    re.compile(r'^A Lightning Component Bundle$', re.IGNORECASE),
]


def _is_default_javadoc(text: str) -> bool:
    """Salesforce が自動生成したボイラープレート javadoc か判定"""
    return any(p.search(text or "") for p in _DEFAULT_JAVADOC_PATTERNS)


def scan(project_dir: Path) -> list[dict]:
    force_app = project_dir / "force-app" / "main" / "default"
    docs_design = project_dir / "docs" / "design"
    ledger_path = project_dir / "docs" / ".sf" / "feature_ids.yml"
    ledger = load_ledger(ledger_path)

    features = []
    active_keys: set[str] = set()

    def _add(ftype: str, api_name: str, extra: dict):
        fid = resolve_id(ledger, ftype, api_name)
        active_keys.add(_make_key(ftype, api_name))
        entry = {
            "id":       fid,
            "type":     ftype,
            "api_name": api_name,
            **extra,
        }
        features.append(entry)

    # --- Apex / Batch ---
    base = force_app / "classes"
    if base.exists():
        for cls_file in sorted(base.glob("*.cls")):
            classified = classify_apex(cls_file)
            if classified is None:
                continue
            doc = get_design_doc(docs_design, cls_file.stem, classified)
            _add(classified, cls_file.stem, {
                "name":        cls_file.stem,
                "overview":    extract_javadoc(cls_file, cls_file.stem, doc),
                "source_file": cls_file.as_posix(),
                "design_doc":  doc,
            })

    # --- Trigger（ハンドラークラスに吸収）---
    base = force_app / "triggers"
    if base.exists():
        for trig_file in sorted(base.glob("*.trigger")):
            handler = extract_trigger_handler(trig_file)
            doc = get_design_doc(docs_design, trig_file.stem, "Trigger")
            _add("Trigger", trig_file.stem, {
                "name":        trig_file.stem,
                "overview":    extract_trigger_overview(trig_file, doc),
                "source_file": trig_file.as_posix(),
                "design_doc":  doc,
                "absorb_into": handler,   # ハンドラークラスの steps/prerequisites に吸収
            })

    # --- Flow ---
    base = force_app / "flows"
    if base.exists():
        for flow_file in sorted(base.glob("*.flow-meta.xml")):
            label, ptype, desc = get_flow_info(flow_file)
            flow_type = "画面フロー" if ptype == "Flow" and b"<screens>" in flow_file.read_bytes() else "Flow"
            api_name = flow_file.name.replace(".flow-meta.xml", "")
            # flow_file.stem だと "X.flow-meta" のように .flow-meta が残ってしまうので api_name を使う
            doc = get_design_doc(docs_design, api_name, flow_type)
            # 優先順: design_doc の title → description → label
            overview = extract_design_doc_title(doc) or clean_tech_business(desc.strip())
            if not overview and label and label != api_name:
                overview = clean_tech_business(label)
            _add(flow_type, api_name, {
                "name":        label,
                "overview":    overview,
                "source_file": flow_file.as_posix(),
                "design_doc":  doc,
            })

    # --- LWC（モーダルコンポーネントは親に吸収）---
    base = force_app / "lwc"
    if base.exists():
        lwc_names = {p.name for p in base.iterdir() if p.is_dir()}
        for comp_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            name = comp_dir.name
            # モーダル検出: 名前が "modal"（大文字小文字不問）で終わる
            parent_name = None
            if name.lower().endswith("modal"):
                candidate = name[:-5]   # "Modal" / "modal" = 5文字
                if candidate and candidate in lwc_names:
                    parent_name = candidate
            doc = get_design_doc(docs_design, name, "LWC")
            _add("LWC", name, {
                "name":        name,
                "overview":    extract_lwc_overview(comp_dir, doc),
                "source_file": comp_dir.as_posix(),
                "design_doc":  doc,
                "absorb_into": parent_name,   # None = 独立設計書を作る
            })

    # --- Aura ---
    base = force_app / "aura"
    if base.exists():
        for comp_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            doc = get_design_doc(docs_design, comp_dir.name, "Aura")
            _add("Aura", comp_dir.name, {
                "name":        comp_dir.name,
                "overview":    extract_aura_overview(comp_dir, doc),
                "source_file": comp_dir.as_posix(),
                "design_doc":  doc,
            })

    # --- Visualforce ---
    base = force_app / "pages"
    if base.exists():
        for page_file in sorted(base.glob("*.page-meta.xml")):
            api_name = page_file.name.replace(".page-meta.xml", "")
            if is_trivial_vf_page(page_file):
                # 空・雛形 VF: 機能一覧から除外。active_keys には残し
                # 誤った deprecated 化を防ぐ（実在はするため）
                active_keys.add(_make_key("Visualforce", api_name))
                print(f"[情報] 空/雛形VFを設計書対象外: {api_name}", file=sys.stderr)
                continue
            doc = get_design_doc(docs_design, api_name, "Visualforce")
            _add("Visualforce", api_name, {
                "name":        api_name,
                "overview":    extract_vf_overview(page_file, doc),
                "source_file": page_file.as_posix(),
                "design_doc":  doc,
            })

    # 今回見つからなかった機能は deprecated にする
    newly_deprecated = mark_deprecated(ledger, active_keys)
    if newly_deprecated:
        print(f"[情報] 削除検知: {len(newly_deprecated)}件 → 台帳で deprecated=true に更新",
              file=sys.stderr)
        for e in newly_deprecated:
            print(f"  - {e['id']} ({e['type']}) {e['api_name']}", file=sys.stderr)

    # 台帳保存（常に）
    save_ledger(ledger_path, ledger)

    return features


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", default=".", help="プロジェクトルート")
    parser.add_argument("--output",      default=None, help="出力JSONファイルパス（省略時はstdout）")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    features = scan(project_dir)
    out = json.dumps(features, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"スキャン完了: {len(features)}件 → {args.output}", file=sys.stderr)
    else:
        sys.stdout.buffer.write(out.encode("utf-8"))
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
