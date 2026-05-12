"""
テキスト日本語化の共通ユーティリティ。

詳細設計書（generate_detail_design.py）の日本語化ロジックから、
メタデータ非依存の定数・関数を切り出したモジュール。
機能一覧（scan_features.py / generate_feature_list.py）から参照する。

NOTE: _SF_OBJ_LABELS / _SF_FIELD_LABELS はカスタムオブジェクト/フィールドの日本語ラベルマップ。
メタデータ非依存原則により、このモジュールでは直接ロードせず呼び出し側から
set_sf_labels(obj_labels, field_labels) で注入する。注入なし（空辞書）の場合は
既存の削除フォールバック（_TECH_REPL_BIZ）に委ねる。
"""

import re as _re

# ---------------------------------------------------------------------------
# 標準オブジェクト API名 → 日本語ラベル
# ---------------------------------------------------------------------------
_STD_OBJ_LABELS = {
    "ContentDocumentLink": "コンテンツ紐付けレコード",
    "ContentDocument":     "コンテンツドキュメント",
    "ContentVersion":      "コンテンツファイル",
    "EmailMessage":        "メールメッセージ",
    "Attachment":          "添付ファイル",
    "Opportunity":         "商談",
    "Contact":             "取引先責任者",
    "Account":             "取引先",
    "Lead":                "リード",
    "Case":                "ケース",
    "Task":                "ToDo",
    "Event":               "行動",
    "User":                "ユーザー",
    "Quote":               "見積",
    "FeedItem":            "フィード投稿",
    "FeedComment":         "フィードコメント",
}

# ---------------------------------------------------------------------------
# トリガー events → 日本語マップ
# ---------------------------------------------------------------------------
_TRIGGER_EVENTS_JA = {
    "before insert":  "登録前",
    "after insert":   "登録後",
    "before update":  "更新前",
    "after update":   "更新後",
    "before delete":  "削除前",
    "after delete":   "削除後",
    "after undelete": "復元後",
}

# ---------------------------------------------------------------------------
# カスタムオブジェクト/フィールド 日本語ラベル（set_sf_labels で注入）
# ---------------------------------------------------------------------------
_SF_OBJ_LABELS:   dict = {}  # {obj_api: ja_label}
_SF_FIELD_LABELS: dict = {}  # {obj_api: {field_api: ja_label}}

# ---------------------------------------------------------------------------
# 定数 (generate_detail_design.py からのコピー)
# ---------------------------------------------------------------------------
_A  = _re.ASCII
_AI = _re.ASCII | _re.IGNORECASE

# Object__c.Field__c 形式と単独 Object__c の検出パターン
_DOT_CUSTOM_PAT = _re.compile(
    r'(?<![A-Za-z0-9_])([A-Z][A-Za-z0-9]*)__c\.([A-Z][A-Za-z0-9]*)__c(?![A-Za-z0-9_])',
    _A,
)
_SINGLE_OBJ_PAT = _re.compile(
    r'(?<![A-Za-z0-9_])[A-Z][A-Za-z0-9]*__c(?![A-Za-z0-9_.])',
    _A,
)

_JARGON_JA: list[tuple] = [
    # Apex トリガー複合表現（単体 insert/delete/update より先に処理）
    (_re.compile(r'\bbefore\s+insert\b', _AI), '処理前（新規）'),
    (_re.compile(r'\bafter\s+insert\b',  _AI), '処理後（新規）'),
    (_re.compile(r'\bbefore\s+update\b', _AI), '処理前（更新）'),
    (_re.compile(r'\bafter\s+update\b',  _AI), '処理後（更新）'),
    (_re.compile(r'\bbefore\s+delete\b', _AI), '処理前（削除）'),
    (_re.compile(r'\bafter\s+delete\b',  _AI), '処理後（削除）'),
    # SF API / 外部サービス
    (_re.compile(r'\bOPROARTS\s+API\b', _A), '外部帳票サービス'),
    (_re.compile(r'\bOPROARTS\b', _A), '外部帳票サービス'),
    # コレクション型
    (_re.compile(r'\bList<Id>\b', _A), 'IDリスト'),
    (_re.compile(r'\bList<[A-Za-z]+>\b', _A), 'リスト'),
    # データ型
    (_re.compile(r'\bBlob\b', _A), 'バイナリデータ'),
    (_re.compile(r'\bvoid\b', _A), 'なし'),
    # DML 操作（単体）
    (_re.compile(r'\binsert\b', _AI), '新規作成'),
    (_re.compile(r'\bupsert\b', _AI), '登録・更新'),
    (_re.compile(r'\bdelete\b', _AI), '削除'),
    (_re.compile(r'\bupdate\b', _AI), '更新'),
    (_re.compile(r'\bquery\b',  _AI), '参照'),
    # Apex 固有クラス名・アノテーション
    (_re.compile(r'\bCustomerUser\b', _A), 'カスタマーユーザー'),
    (_re.compile(r'\b[A-Z][A-Za-z]*Tmp\b', _A), '一時データ'),
    (_re.compile(r'\bInvocableMethod\b', _A), 'フローアクション'),
    (_re.compile(r'\bAuraEnabled\b', _A), 'LWC公開メソッド'),
    # Apex 非同期アノテーション
    (_re.compile(r'@future(?:で非同期実行する|で実行される?)?'), '非同期で実行する'),
    (_re.compile(r'@\w+', _A), ''),
]

_TECH_REPL = [
    (_re.compile(r'@InvocableMethod[としてで\s]*'), 'フローから呼び出され、'),
    (_re.compile(r'@フローアクション(?:として)?(?:Flowから呼ばれ)?[、\s]*'), 'フローから呼び出され、'),
    (_re.compile(r'@AuraEnabled[としてで\s]*'), 'LWCから呼び出され、'),
    (_re.compile(r'@LWC公開メソッド(?:として)?[、\s]*'), 'LWCから呼び出され、'),
    (_re.compile(r'@RemoteAction[としてで\s]*'), '非同期処理として呼び出され、'),
    (_re.compile(r'@\w+[としてで\s]*'), ''),
    (_re.compile(r'SELECT\s+.+?\s+FROM\s+\w+(?:\s+WHERE\s+[^。\n]+)?', _re.DOTALL | _re.IGNORECASE), ''),
    (_re.compile(r':\w+'), ''),
    (_re.compile(r'[A-Z]{2,6}→\d{3}→[A-Z]{2,6}'), ''),
    (_re.compile(r'[（(](?:is|has)[A-Z]\w*[）)]'), ''),
    (_re.compile(r'(?:is|has)[A-Z]\w*が(?:false|true|null)(?:の場合[はに]?)?'), ''),
    (_re.compile(r'(?<![A-Za-z])(?:is|has)[A-Z][A-Za-z]+(?![A-Za-z])'), ''),
    (_re.compile(r'(?<![A-Za-z])[a-z][a-zA-Z]{3,}(?=[をがはにでへのもと])'), ''),
    (_re.compile(r'[A-Z][a-zA-Z0-9]{6,}(?=[ぁ-ん一-龥ァ-ヶーをがはにでへのもと]|により|によって)'), ''),
    (_re.compile(r'[A-Z][A-Za-z0-9]+\.[A-Za-z]\w+\([^)]*\)'), ''),
    (_re.compile(r'[A-Z][A-Za-z0-9]+\.[A-Za-z]\w+'), ''),
    (_re.compile(r'[^\s。]{2,20}(?:作成|更新|削除)時（処理前（(?:新規|更新|削除)）(?:/処理後（(?:新規|更新|削除)）)?）[にので]?'), ''),
    (_re.compile(r'のサーバーサイドロジック'), ''),
    (_re.compile(r'のメインコンポーネント'), ''),
    (_re.compile(r'単一責務クラス'), 'クラス'),
    (_re.compile(r'(呼び出され)[、\s]{0,2}Flow[^\s、。]{0,20}から呼ばれ[、\s]*'), r'\1、'),
    (_re.compile(r'([^\s（]{4,30})（\1）'), r'\1'),
    (_re.compile(r'(メソッド){2,}'), 'メソッド'),
    (_re.compile(r'（\s*）'), ''),
    (_re.compile(r'\(\s*\)'), ''),
    (_re.compile(r'[・、/]\s*による[^\s、。]{1,20}'), ''),
    (_re.compile(r'/作成'), '・作成'),
    (_re.compile(r'(?:・作成){2,}'), '・作成'),
    (_re.compile(r'[・、]\s*を[ぁ-ん一-龥A-Za-z]{1,10}て(?=の)'), ''),
    (_re.compile(r'[はがをにでへのも][。．]'), '。'),
    (_re.compile(r'^[、。\s]+'), ''),
    (_re.compile(r'[ \t]{2,}'), ' '),
    (_re.compile(r'[・、]{2,}'), '・'),
    (_re.compile(r'(、){2,}'), '、'),
    (_re.compile(r'(。){2,}'), '。'),
]

_TECH_REPL_BIZ = [
    (_re.compile(r'@InvocableMethod[としてで\s]*'), ''),
    (_re.compile(r'@AuraEnabled[としてで\s]*'), ''),
    (_re.compile(r'@RemoteAction[としてで\s]*'), ''),
    (_re.compile(r'@\w+'), ''),
    (_re.compile(r'SELECT\s+.+?\s+FROM\s+\w+(?:\s+WHERE\s+[^。\n]+)?', _re.DOTALL | _re.IGNORECASE), ''),
    (_re.compile(r':\w+'), ''),
    (_re.compile(r'[A-Z]{2,6}→\d{3}→[A-Z]{2,6}'), ''),
    (_re.compile(r'[（(](?:is|has)[A-Z]\w*[）)]'), ''),
    (_re.compile(r'(?:is|has)[A-Z]\w*が(?:false|true|null)(?:の場合[はに]?)?'), ''),
    (_re.compile(r'(?<![A-Za-z])(?:is|has)[A-Z][A-Za-z]+(?![A-Za-z])'), ''),
    (_re.compile(r'(?<![A-Za-z])[a-z][a-zA-Z]{3,}(?=[をがはにでへのもと])'), ''),
    (_re.compile(r'[A-Z][A-Za-z0-9]+\.[A-Za-z]\w+\([^)]*\)'), ''),
    (_re.compile(r'[A-Z][A-Za-z0-9]+\.[A-Za-z]\w+'), ''),
    (_re.compile(r'のサーバーサイドロジック'), ''),
    (_re.compile(r'のメインコンポーネント'), ''),
    (_re.compile(r'単一責務クラス'), 'クラス'),
    (_re.compile(r'List<[A-Z][A-Za-z0-9]*__[cepr]>'), 'レコードリスト'),
    (_re.compile(r'List<[A-Za-z]+>'), 'リスト'),
    (_re.compile(r'（trigger\s+\w+）'), ''),
    (_re.compile(r'\(trigger\s+\w+\)'), ''),
    (_re.compile(r'\b[A-Z][A-Za-z0-9]*__[cepr]\b'), ''),
    (_re.compile(r'\b[A-Z][A-Za-z0-9]{2,}(?:Controller|Service|Handler|Manager|Batch|Trigger)\b'), ''),
    (_re.compile(r'（[A-Z@#][^）]{0,60}）'), ''),
    (_re.compile(r'\([A-Z@#][^)]{0,60}\)'), ''),
    (_re.compile(r'([^\s（]{4,30})（\1）'), r'\1'),
    (_re.compile(r'(メソッド){2,}'), 'メソッド'),
    (_re.compile(r'（\s*）'), ''),
    (_re.compile(r'\(\s*\)'), ''),
    (_re.compile(r'[（(]\s*[:：][^）)]{0,30}[）)]\s*。?\s*'), ''),
    (_re.compile(r'[・、/]\s*による[^\s、。]{1,20}'), ''),
    (_re.compile(r'/作成'), '・作成'),
    (_re.compile(r'(?:・作成){2,}'), '・作成'),
    (_re.compile(r'[A-Za-z][A-Za-z0-9_]*(?:__c|__r|__C|__R)(?![A-Za-z0-9_])'), ''),
    (_re.compile(r'の(?=[等や・、。\s])'), ''),
    (_re.compile(r'[ \t]{2,}'), ' '),
    (_re.compile(r'[・、]{2,}'), '・'),
    (_re.compile(r'(、){2,}'), '、'),
    (_re.compile(r'^[、。・/\s]+|[、。・/\s]+$'), ''),
]

_EC_PLACEHOLDER = "\x01EC\x01"

# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------

def set_sf_labels(obj_labels: dict, field_labels: dict) -> None:
    """カスタムオブジェクト/フィールドの日本語ラベル辞書を注入する。
    generate_feature_list.py / scan_features.py の main() から呼ぶ。"""
    global _SF_OBJ_LABELS, _SF_FIELD_LABELS
    _SF_OBJ_LABELS   = obj_labels   or {}
    _SF_FIELD_LABELS = field_labels or {}


def translate_sf_custom(text: str) -> str:
    """カスタムオブジェクト/フィールド API 名を日本語ラベルに置換する（注入辞書使用）。
    辞書ミスの場合は元の文字列を返し、後続の _TECH_REPL_BIZ 削除フォールバックに任せる。"""
    if not _SF_OBJ_LABELS and not _SF_FIELD_LABELS:
        return text

    def _dot_repl(m: _re.Match) -> str:
        obj_api = m.group(1) + "__c"
        fld_api = m.group(2) + "__c"
        obj_ja  = _SF_OBJ_LABELS.get(obj_api)
        fld_ja  = (_SF_FIELD_LABELS.get(obj_api) or {}).get(fld_api)
        if obj_ja and fld_ja:
            return f"{obj_ja}.{fld_ja}"
        if obj_ja:
            return f"{obj_ja}.{fld_api}"
        return m.group(0)  # 辞書ミス → フォールバックへ

    text = _DOT_CUSTOM_PAT.sub(_dot_repl, text)

    if _SF_OBJ_LABELS:
        def _obj_repl(m: _re.Match) -> str:
            return _SF_OBJ_LABELS.get(m.group(0), m.group(0))
        text = _SINGLE_OBJ_PAT.sub(_obj_repl, text)

    return text


def translate_sf_objects(text: str) -> str:
    """Salesforce 標準オブジェクト API名を日本語ラベルに置換する（標準オブジェクトのみ）。"""
    for api, ja in _STD_OBJ_LABELS.items():
        text = _re.sub(
            rf'(?<![A-Za-z0-9_]){_re.escape(api)}(?![A-Za-z0-9_])',
            ja, text,
        )
    return text


def translate_jargon(text: str) -> str:
    """技術英語ジャーゴンを日本語に変換する。"""
    for pat, repl in _JARGON_JA:
        text = pat.sub(repl, text)
    return text


def clean_tech(text: str) -> str:
    """役割・説明文用: アノテーション・クラス名.メソッド名を除去して日本語説明にする。"""
    for pattern, repl in _TECH_REPL:
        text = pattern.sub(repl, text)
    return text.strip()


def clean_tech_business(text: str) -> str:
    """業務フロー・タイトル・概要用: SF標準オブジェクトを日本語化→技術用語を全除去する。"""
    if not text:
        return text
    text = text.replace("Experience Cloud", _EC_PLACEHOLDER)
    text = translate_sf_objects(text)
    text = translate_sf_custom(text)
    text = translate_jargon(text)
    for pattern, repl in _TECH_REPL_BIZ:
        text = pattern.sub(repl, text)
    text = text.replace(_EC_PLACEHOLDER, "Experience Cloud")
    return text.strip()


def translate_trigger_events(events: str) -> str:
    """`before insert, after update` → `登録前・更新後` に変換する。"""
    parts = [e.strip().lower() for e in events.split(",") if e.strip()]
    ja = [_TRIGGER_EVENTS_JA.get(p, p) for p in parts]
    return "・".join(ja)
