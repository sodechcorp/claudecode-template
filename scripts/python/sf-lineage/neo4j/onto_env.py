"""Salesforce の組織の地図を Neo4j で見る作業環境（DDD-Ontology の原本から new-onto-env.cmd で作ったもの）を、Claude Code の会話から操作する。

  python onto_env.py setup                      # 作業環境をソデック用にする（置き場所・名前空間・パスワードの環境変数）。何度実行してもよい
  python onto_env.py start                      # Neo4j を別のウィンドウで起動し、つながるまで待つ
  python onto_env.py stop                       # Neo4j を止める
  python onto_env.py status                     # 起動しているか・入っているシステムと件数
  python onto_env.py reset-db --yes [--password-env 名前]   # Neo4j の中身を全部消し、n10s の設定だけ作り直す
  python onto_env.py load --root <プロジェクト> --repo <識別子> --name-ja <日本語名>   # 地図 → 中間JSON → TTL → 取り込み → 検証
  python onto_env.py show --query ⑤ --set オブジェクト=<表示ラベル> [--shot <png>] [--keep]   # Claude 用のブラウザの窓で、ログイン・入力・実行まで行う（図がそのまま出る）
  python onto_env.py show --cypher-file <ファイル> [--shot <png>]   # その場で組み立てた Cypher を同じように実行する
  python onto_env.py open [--query ② --set 項目=<オブジェクト.項目> --set システム=<識別子>]   # （playwright が無いとき）枠をクリップボードに入れて普段のブラウザで開く
  python onto_env.py open --cypher-file <ファイル>   # その場で組み立てた Cypher をクリップボードに入れて開く（--cypher "<文>" でも可）
  python onto_env.py query "<Cypher>" | --file <ファイル> [--limit 200]   # 読み取り専用で問い合わせる（図の Cypher は「丸 -線-> 丸」で出る）
  python onto_env.py relations --repo <識別子> --map <地図のフォルダ>   # オブジェクトの関係（参照・主従）の線を足す（load が最後に行う）

共通の引数: --env <作業環境のフォルダ>（既定: 環境変数 ONTO_ENV、無ければ C:\\work\\Onto-sf-lineage → E:\\Onto-sf-lineage の順に探す）

- E: ドライブ（subst E: C:\\work）は不要。setup が作業環境の中のパスを実際の場所に書き換える。
  Neo4j は PC の起動時に立ち上げておく必要もない（show・open は止まっていれば自分で起動する。start でも可）

- パスワードはユーザー環境変数 SODECH_NEO4J_PASSWORD から読む（画面にもファイルにも出さない）。
  決める・変えるのは利用者が作業環境の set-neo4j-password.cmd で行う（Claude は実行しない）
- 原本（E:\\DDD-Ontology）は変えない。setup が書き換えるのは作業環境の中だけ
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SF_LINEAGE = os.path.dirname(HERE)
CYPHER_BOOK = os.path.join(HERE, "Salesforceの見方（Cypher）.txt")
EBISU = "https://ontology.use-ebisu.co.jp/"
SODECH = "https://ontology.sodech.co.jp/"
PASS_ENV = "SODECH_NEO4J_PASSWORD"
ORIGINAL_PASS_ENVS = ("LINEAGE_NEO4J_PASSWORD", "NEO4J_PASSWORD")
GRAPHCONFIG = "{handleVocabUris: 'SHORTEN', handleRDFTypes: 'LABELS', handleMultival: 'ARRAY', keepLangTag: true}"


# ---------- 作業環境 ----------
# 作業環境の置き場所の候補（--env・環境変数 ONTO_ENV が無いとき、上から順に探す）。
# new-onto-env は E: ドライブ（subst E: C:\work。PC を再起動すると外れる）を前提に作るので、実際の場所を先に見る
DEFAULT_ENVS = [r"C:\work\Onto-sf-lineage", r"E:\Onto-sf-lineage"]


def real_path(path: str) -> str:
    """subst で割り当てたドライブのパスを、実際の場所に直す（E:\\x → C:\\work\\x）。"""
    path = os.path.abspath(path)
    try:
        out = subprocess.run(["subst"], capture_output=True, text=True, encoding="cp932", errors="ignore").stdout
    except OSError:
        return path
    for line in out.splitlines():   # 例: E:\: => C:\work
        m = re.match(r"([A-Za-z]:)\\: => (.+)$", line.strip())
        if m and path.upper().startswith(m.group(1).upper()):
            return m.group(2).rstrip("\\") + path[2:]
    return path


class Env:
    def __init__(self, path: str) -> None:
        self.path = real_path(path)
        if not os.path.isfile(os.path.join(self.path, "start-neo4j.cmd")):
            sys.exit(f"作業環境が見つかりません: {self.path}（--env か環境変数 ONTO_ENV で指定する）")
        if os.path.normcase(os.path.basename(self.path)) == os.path.normcase("DDD-Ontology"):
            sys.exit("原本（DDD-Ontology）は操作しません。new-onto-env.cmd で作った作業環境を指定してください")
        self.core = os.path.join(self.path, "tools", "lineage-core")
        self.python = os.path.join(self.core, ".venv", "Scripts", "python.exe")
        conf = self.neo4j_conf()
        self.http_port = int(re.search(r"^server\.http\.listen_address=.*?:(\d+)", conf, re.M).group(1))
        self.bolt_port = int(re.search(r"^server\.bolt\.listen_address=.*?:(\d+)", conf, re.M).group(1))
        self.bolt = f"bolt://localhost:{self.bolt_port}"
        m = re.search(r"^baseIri:\s*(\S+)", open(os.path.join(self.core, "config.yaml"), encoding="utf-8-sig").read(), re.M)
        self.base = m.group(1) if m else SODECH

    def neo4j_home(self) -> str:
        base = os.path.join(self.path, "neo4j")
        for d in sorted(os.listdir(base)):
            if d.startswith("neo4j-community-"):
                return os.path.join(base, d)
        sys.exit("neo4j-community-* が見つかりません")

    def neo4j_conf(self) -> str:
        return open(os.path.join(self.neo4j_home(), "conf", "neo4j.conf"), encoding="utf-8", errors="ignore").read()

    def running(self) -> bool:
        with socket.socket() as s:
            s.settimeout(1.5)
            return s.connect_ex(("127.0.0.1", self.bolt_port)) == 0


def password(name: str = PASS_ENV) -> str:
    """ユーザー環境変数から読む（この会話のシェルより後に保存した値も読めるよう、レジストリを見る）。表示しない。"""
    v = os.environ.get(name)
    if not v and sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                v = winreg.QueryValueEx(k, name)[0]
        except OSError:
            v = None
    if not v:
        sys.exit(f"ユーザー環境変数 {name} がありません。作業環境の set-neo4j-password.cmd を利用者が実行して決める")
    return v


def need_neo4j_driver(argv: list[str], env: Env) -> None:
    """neo4j ドライバーが無い Python で呼ばれたら、作業環境の .venv の Python で動かし直す。"""
    try:
        import neo4j  # noqa: F401
    except ImportError:
        if not os.path.isfile(env.python):
            sys.exit(f"neo4j ドライバーも作業環境の .venv も見つかりません: {env.python}")
        sys.exit(subprocess.call([env.python, os.path.abspath(__file__), "--env", env.path] + argv,
                                 env=dict(os.environ, PYTHONIOENCODING="utf-8")))


def driver(env: Env, pass_env: str = PASS_ENV):
    from neo4j import GraphDatabase
    return GraphDatabase.driver(env.bolt, auth=("neo4j", password(pass_env)))


# ---------- setup ----------
def rewrite(path: str, pairs: list[tuple[str, str]]) -> bool:
    """文字コード（BOM の有無）と改行を保ったまま置き換える。変えたら True。"""
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
    new = text
    for a, b in pairs:
        new = new.replace(a, b)
    if new == text:
        return False
    open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + new.encode("utf-8"))
    return True


RELOCATE_SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", "jdk", "data", "logs", "lineage-output",
                      "browser-profile", "backup", "downloads", "node_modules", ".git"}
RELOCATE_EXTS = (".cmd", ".bat", ".ps1", ".yaml", ".yml", ".md", ".txt", ".json", ".py", ".toml", ".cfg", ".ini")


def baked_root(env: Env) -> str | None:
    """new-onto-env が作ったときの置き場所（start-neo4j.cmd の NEO4J_HOME から読む。例: E:\\Onto-sf-lineage）。"""
    text = open(os.path.join(env.path, "start-neo4j.cmd"), encoding="utf-8", errors="ignore").read()
    m = re.search(r'set "NEO4J_HOME=(.+?)\\neo4j\\neo4j-community-', text)
    return m.group(1) if m else None


def relocate(env: Env) -> list[str]:
    """作業環境に書き込まれた置き場所（E:\\Onto-sf-lineage など）を、実際の場所に書き換える。
    E: は subst で割り当てたドライブで PC を再起動すると外れるため、これをしないと Neo4j が起動できない。"""
    old = baked_root(env)
    if not old or os.path.normcase(old.rstrip("\\/")) == os.path.normcase(env.path.rstrip("\\/")):
        return []
    new = env.path.rstrip("\\/")
    pairs = [(old.replace("\\", "\\\\"), new.replace("\\", "\\\\")),   # JSON などの \\ 表記
             (old, new), (old.replace("\\", "/"), new.replace("\\", "/"))]
    changed = []
    for dp, dns, fns in os.walk(env.path):
        dns[:] = [d for d in dns if d not in RELOCATE_SKIP_DIRS]
        for fn in fns:
            if not fn.lower().endswith(RELOCATE_EXTS):
                continue
            p = os.path.join(dp, fn)
            try:
                if rewrite(p, pairs):
                    changed.append(os.path.relpath(p, env.path))
            except (UnicodeDecodeError, OSError):
                pass
    return changed


def cmd_setup(env: Env) -> None:
    changed = []
    # 0) 置き場所: E: ドライブ（subst）を前提に作られたパスを、実際の場所（例: C:\work\Onto-sf-lineage）に
    old_root = baked_root(env)
    moved = relocate(env)
    if moved:
        print(f"置き場所を {env.path} に書き換えたファイル {len(moved)} 件")
        changed += moved
    # 1) 名前空間: 語彙・検証の規則・設定・テスト・ビュー定義をソデック用に
    for sub in (os.path.join("tools", "lineage-core"), os.path.join("tools", "lineage-viewer")):
        top = os.path.join(env.path, sub)
        for dp, dns, fns in os.walk(top):
            dns[:] = [d for d in dns if d not in (".venv", "__pycache__", ".pytest_cache")]
            for fn in fns:
                if fn.endswith((".ttl", ".py", ".yaml", ".yml", ".json", ".cypher", ".md")):
                    p = os.path.join(dp, fn)
                    if rewrite(p, [(EBISU, SODECH)]):
                        changed.append(os.path.relpath(p, env.path))
    # 2) パスワードの環境変数を作業環境専用に（原本の LINEAGE_NEO4J_PASSWORD・NEO4J_PASSWORD を上書きしない）
    pw_files = {
        os.path.join("tools", "lineage-core", "config.yaml"): [("passwordEnv: LINEAGE_NEO4J_PASSWORD", f"passwordEnv: {PASS_ENV}")],
        "cypher-shell.cmd": [('"%LINEAGE_NEO4J_PASSWORD%"', f'"%{PASS_ENV}%"'),
                             ("LINEAGE_NEO4J_PASSWORD is not set", f"{PASS_ENV} is not set"),
                             ("=%LINEAGE_NEO4J_PASSWORD%", f"=%{PASS_ENV}%"),
                             ("REM  LINEAGE_NEO4J_PASSWORD (set it with", f"REM  {PASS_ENV} (set it with")],
        # find は Windows の find.exe を場所まで指定する（PATH に Git の find があると、そちらが呼ばれてパスワードを読めない）
        "mcp-neo4j.cmd": [("/v NEO4J_PASSWORD", f"/v {PASS_ENV}"), ('^| find "NEO4J_PASSWORD"', f'^| %SystemRoot%\\System32\\find.exe "{PASS_ENV}"'),
                          (f'^| find "{PASS_ENV}"', f'^| %SystemRoot%\\System32\\find.exe "{PASS_ENV}"'),
                          ("read NEO4J_PASSWORD from", f"read {PASS_ENV} from")],
        "set-neo4j-password.cmd": [("(LINEAGE_NEO4J_PASSWORD / NEO4J_PASSWORD)", f"({PASS_ENV}, for this environment only)")],
        "set-neo4j-password.ps1": [
            ("foreach ($name in 'LINEAGE_NEO4J_PASSWORD', 'NEO4J_PASSWORD')", f"foreach ($name in '{PASS_ENV}')"),
            ("'ユーザー環境変数 LINEAGE_NEO4J_PASSWORD と NEO4J_PASSWORD に保存しました。'",
             f"'ユーザー環境変数 {PASS_ENV} に保存しました（この作業環境専用。原本の LINEAGE_NEO4J_PASSWORD・NEO4J_PASSWORD は変えていません）。'"),
            ("# - 保存先はユーザー環境変数 LINEAGE_NEO4J_PASSWORD（共通基盤・run-core.ps1・cypher-shell.cmd が読む）と\n"
             "#   NEO4J_PASSWORD（Claude の Neo4j 用 MCP サーバーが読む）。",
             f"# - 保存先はユーザー環境変数 {PASS_ENV}（この作業環境専用。共通基盤・cypher-shell.cmd・mcp-neo4j.cmd が読む）。\n"
             "#   原本の LINEAGE_NEO4J_PASSWORD・NEO4J_PASSWORD は変えない。"),
            ("# - 保存先はユーザー環境変数 LINEAGE_NEO4J_PASSWORD（共通基盤・run-core.ps1・cypher-shell.cmd が読む）と\r\n"
             "#   NEO4J_PASSWORD（Claude の Neo4j 用 MCP サーバーが読む）。",
             f"# - 保存先はユーザー環境変数 {PASS_ENV}（この作業環境専用。共通基盤・cypher-shell.cmd・mcp-neo4j.cmd が読む）。\r\n"
             "#   原本の LINEAGE_NEO4J_PASSWORD・NEO4J_PASSWORD は変えない。"),
            ("'  - 開いているターミナル・PowerShell と Claude デスクトップを閉じて、開き直す（新しい値を読み込むため）'",
             "'  - Neo4j の MCP を使うときは、VS Code（Claude Code）を開き直す（新しい値を読み込むため）'"),
        ],
        "CLAUDE.md": [
            ("- パスワードは原本と同じ（データごとコピーしたため）。環境変数は原本と共用なので、パスワードを変えるときは、原本とこの環境の両方を同じ値にそろえる。",
             f"- **ソデック用（2026-11-11）**: 名前空間（baseIri・語彙・検証の規則）は `{SODECH}`。パスワードはこの環境専用で、"
             f"ユーザー環境変数 `{PASS_ENV}` に保存する（`set-neo4j-password.cmd`）。原本の `LINEAGE_NEO4J_PASSWORD`・`NEO4J_PASSWORD` は使わない。"
             "ふだんの操作（起動・取り込み・ブラウザで開く）は、Claude Code の会話から `scripts/python/sf-lineage/neo4j/onto_env.py`"
             "（大本テンプレートの各案件のフォルダ・日常業務 WS にある）で行う。"),
        ],
    }
    for rel, pairs in pw_files.items():
        p = os.path.join(env.path, rel)
        if os.path.isfile(p) and rewrite(p, pairs):
            changed.append(rel)
    # 3) 更新記録
    log = os.path.join(env.path, "更新記録.md")
    mark = "ソデック用（名前空間・パスワードの環境変数）"
    if os.path.isfile(log) and mark not in open(log, encoding="utf-8-sig").read():
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n| {time.strftime('%Y-%m-%d')} | 変更 | {mark} | 名前空間を {SODECH} に（tools/lineage-core の語彙・検証の規則・設定・テスト、"
                    f"tools/lineage-viewer）。パスワードの環境変数を {PASS_ENV} に（config.yaml・cypher-shell.cmd・mcp-neo4j.cmd・"
                    "set-neo4j-password）。onto_env.py setup で実行 |\n")
        changed.append("更新記録.md")
    mark2 = "置き場所を実際の場所に（E: ドライブ不要）"
    if moved and os.path.isfile(log) and mark2 not in open(log, encoding="utf-8-sig").read():
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n| {time.strftime('%Y-%m-%d')} | 変更 | {mark2} | {old_root or '元の場所'} を {env.path} に"
                    "（start-neo4j.cmd・cypher-shell.cmd・tools の config.yaml・adapter-config.yaml・run-core.ps1・説明書）。"
                    "subst E: が無くても起動できる。onto_env.py setup で実行 |\n")
    # 確かめる: 作業環境の中に既定の名前空間が残っていないか（lineage-core・viewer）
    left = []
    for sub in (os.path.join("tools", "lineage-core"), os.path.join("tools", "lineage-viewer")):
        for dp, dns, fns in os.walk(os.path.join(env.path, sub)):
            dns[:] = [d for d in dns if d not in (".venv", "__pycache__", ".pytest_cache")]
            for fn in fns:
                p = os.path.join(dp, fn)
                try:
                    if EBISU in open(p, encoding="utf-8", errors="ignore").read():
                        left.append(os.path.relpath(p, env.path))
                except OSError:
                    pass
    print(f"変えたファイル {len(changed)} 件" + ("" if not changed else "：" + "、".join(changed[:12]) + ("…" if len(changed) > 12 else "")))
    print("既定の名前空間の残り: " + ("なし" if not left else "、".join(left)))
    # 4) show 用の playwright を作業環境の .venv に入れる（show はどの Python から呼んでも、無ければこの .venv で動かし直す。ブラウザの取得は要らない）
    if os.path.isfile(env.python):
        has = subprocess.run([env.python, "-c", "import playwright"], capture_output=True).returncode == 0
        if not has:
            r = subprocess.run([env.python, "-m", "pip", "install", "-q", "playwright>=1.50"], capture_output=True, text=True,
                               encoding="utf-8", errors="ignore")
            has = r.returncode == 0
        print("show 用の playwright（作業環境の .venv）: " + ("あり" if has else "入れられませんでした（ネットワークを確かめて setup をやり直す）"))


# ---------- start / stop / status ----------
def cmd_start(env: Env) -> None:
    if env.running():
        print(f"もう起動しています（{env.bolt}）")
        return
    title = f"Neo4j {os.path.basename(env.path)}"
    # 別のウィンドウで動かす（この会話が終わっても止まらない。止めるときはそのウィンドウで Ctrl+C か onto_env.py stop）
    # 入出力を引き継がない（引き継ぐと、呼んだ側（Claude のコマンド）が Neo4j の窓を閉じるまで終わらない）
    subprocess.Popen(["cmd", "/c", "start", title, "cmd", "/k", os.path.join(env.path, "start-neo4j.cmd")], cwd=env.path,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    for _ in range(120):
        if env.running():
            print(f"起動しました（Browser http://localhost:{env.http_port} ・ {env.bolt}。ウィンドウ「{title}」）")
            return
        time.sleep(1)
    sys.exit("120 秒待ってもつながりません。起動のウィンドウの表示を確かめる")


def neo4j_pids(env: Env) -> list[int]:
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='java.exe'\" | "
          f"Where-Object {{ $_.CommandLine -like '*{os.path.basename(env.path)}*' }} | ForEach-Object {{ $_.ProcessId }}")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    return [int(x) for x in out.split() if x.isdigit()]


def cmd_stop(env: Env) -> None:
    pids = neo4j_pids(env)
    if not pids:
        print("動いていません")
        return
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    for _ in range(30):
        if not env.running() and not neo4j_pids(env):
            print("止めました（次に起動したとき、Neo4j がトランザクションのログから整える）")
            return
        time.sleep(1)
    sys.exit("止まりません。起動のウィンドウで Ctrl+C を押す")


def cmd_status(env: Env, argv: list[str]) -> None:
    if not env.running():
        print(f"止まっています（{env.bolt}）。起動: onto_env.py start")
        return
    need_neo4j_driver(argv, env)
    with driver(env) as d:
        rows, _, _ = d.execute_query(
            "MATCH (r:cod__Repository) WITH r, substring(r.uri, 0, size(r.uri) - size('repository')) AS sys "
            "OPTIONAL MATCH (n) WHERE n.uri STARTS WITH sys "
            "RETURN r.表示名 AS name, sys AS uri, count(n) AS c ORDER BY uri")
        ns, _, _ = d.execute_query("CALL n10s.nsprefixes.list() YIELD prefix, namespace WHERE prefix = 'cod' RETURN namespace")
    print(f"起動しています（Browser http://localhost:{env.http_port} ・ {env.bolt}）。語彙の名前空間: {ns[0]['namespace'] if ns else '未登録'}")
    for r in rows:
        repo = r["uri"].rstrip("/").rsplit("/", 1)[-1]
        ttl = os.path.join(env.path, "lineage-output", repo, "ttl", f"code-data-{repo}-latest.ttl")
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(ttl))) if os.path.isfile(ttl) else "不明"
        print(f"  {r['name']}（{repo}）: {r['c']} ノード・TTL の作成 {when}")
    if not rows:
        print("  システムはまだ入っていません")


# ---------- relations（オブジェクトの関係） ----------
def cmd_relations(env: Env, argv: list[str]) -> None:
    """参照・主従の項目 → 参照先のオブジェクトの線（sf__referenceTo）を足す。共通基盤の語彙にオブジェクトどうしの参照が無いため、
    取り込みのあとに作業環境の Neo4j にだけ足す（取り込み直すと消えるので load の最後に毎回足す）。"""
    repo, mapdir = opt(argv, "--repo"), opt(argv, "--map")
    if not (repo and mapdir):
        sys.exit("使い方: onto_env.py relations --repo <識別子> --map <地図のフォルダ>")
    fields = json.load(open(os.path.join(mapdir, "fields.json"), encoding="utf-8"))
    rows = [{"obj": o, "fld": f, "ref": i["referenceTo"]} for o, fs in fields.items() for f, i in fs.items()
            if i.get("type") in ("Lookup", "MasterDetail", "Hierarchy") and i.get("referenceTo")]
    need_neo4j_driver(argv, env)
    db = f"{env.base}code-data/db/{repo}/"
    with driver(env) as d:
        pre = {r["prefix"]: r["namespace"] for r in d.execute_query("CALL n10s.nsprefixes.list() YIELD prefix, namespace RETURN prefix, namespace").records}
        if "sf" not in pre:
            d.execute_query("CALL n10s.nsprefixes.add('sf', $ns)", ns=f"{env.base}sf/")
        d.execute_query("MATCH (t:cod__Table)-[:cod__hasColumn]->(:cod__Column)-[r:sf__referenceTo]->() WHERE t.uri STARTS WITH $db DELETE r", db=db)
        res = d.execute_query(
            "UNWIND $rows AS x "
            "MATCH (t:cod__Table)-[:cod__hasColumn]->(c:cod__Column) "
            "WHERE t.uri STARTS WITH $db AND head(t.cod__physicalName) = x.obj AND head(c.cod__physicalName) = x.fld "
            "MATCH (t2:cod__Table) WHERE t2.uri STARTS WITH $db AND head(t2.cod__physicalName) = x.ref "
            "MERGE (c)-[:sf__referenceTo]->(t2) RETURN count(*) AS n", rows=rows, db=db).records
    print(f"オブジェクトの関係の線 {res[0]['n']} 本（参照・主従の項目 {len(rows)} 件のうち、両方のオブジェクトが入っているもの）")


# ---------- props（自動処理の性質） ----------
MNS = "{http://soap.sforce.com/2006/04/metadata}"


def _x(path: str):
    import xml.etree.ElementTree as ET
    try:
        return ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None


def _t(el, tag: str) -> str | None:
    if el is None:
        return None
    c = el.find(MNS + tag)
    return c.text.strip() if c is not None and c.text and c.text.strip() else None


def _short(s: str | None, n: int = 300) -> str | None:
    return " ".join(s.split())[:n] if s else None


STATUS = {"Active": "有効", "Draft": "下書き", "Obsolete": "無効", "InvalidDraft": "下書き（エラーあり）", "Inactive": "無効",
          "Deleted": "削除済み", "true": "有効", "false": "無効"}
RTT = {"Create": "作成時", "Update": "更新時", "CreateAndUpdate": "作成・更新時", "Delete": "削除時"}


def metadata_props(fa: str) -> dict[str, dict]:
    """force-app から、部品（qualifiedName）ごとの性質を作る。値は文字列だけ（空は入れない）。"""
    out: dict[str, dict] = {}

    def put(qn, **kv):
        out.setdefault(qn, {}).update({k: v for k, v in kv.items() if v})

    # フロー
    d = os.path.join(fa, "flows")
    for fn in (os.listdir(d) if os.path.isdir(d) else []):
        if not fn.endswith(".flow-meta.xml"):
            continue
        r = _x(os.path.join(d, fn))
        if r is None:
            continue
        name, st = fn[: -len(".flow-meta.xml")], r.find(MNS + "start")
        pt, tt, rt = _t(r, "processType"), _t(st, "triggerType"), _t(st, "recordTriggerType")
        kind = ("画面フロー" if pt == "Flow" else "プロセスビルダー" if pt == "Workflow"
                else "レコードトリガーフロー" if tt in ("RecordBeforeSave", "RecordAfterSave", "RecordBeforeDelete")
                else "スケジュールトリガーフロー" if tt == "Scheduled" else "プラットフォームイベントトリガーフロー" if tt == "PlatformEvent"
                else "自動起動フロー（呼ばれたときに動く）")
        when = {"RecordBeforeSave": "保存前", "RecordAfterSave": "保存後", "RecordBeforeDelete": "削除前"}.get(tt)
        if when:
            when += f"（{_t(st, 'object')}・{RTT.get(rt, rt or '')}）"
        elif tt == "Scheduled":
            sc = st.find(MNS + "schedule")
            when = f"スケジュール（{_t(sc, 'frequency')}・{_t(sc, 'startDate')} {_t(sc, 'startTime') or ''}）".strip()
        conds = []
        for f in (st.iter(MNS + "filters") if st is not None else []):
            v = f.find(MNS + "value")
            val = next((c.text for c in v) if v is not None else iter([]), None)
            conds.append(f"{_t(f, 'field')} {_t(f, 'operator')} {val}")
        cond = _t(st, "filterFormula") or ((f" {_t(st, 'filterLogic') or 'and'} ".join(conds)) if conds else None)
        put(f"flow:{name}", 種類=kind, 動く時=when, 順番=_t(r, "triggerOrder"), 状態=STATUS.get(_t(r, "status"), _t(r, "status")),
            開始条件=_short(cond), 説明=_short(_t(r, "description")), APIバージョン=_t(r, "apiVersion"))
    # Apex トリガ・クラス
    for sub, ext, meta in (("triggers", ".trigger", ".trigger-meta.xml"), ("classes", ".cls", ".cls-meta.xml")):
        d = os.path.join(fa, sub)
        for fn in (os.listdir(d) if os.path.isdir(d) else []):
            if not fn.endswith(ext):
                continue
            name = fn[: -len(ext)]
            src = open(os.path.join(d, fn), encoding="utf-8", errors="ignore").read()
            m = _x(os.path.join(d, name + meta))
            if sub == "triggers":
                h = re.search(r"trigger\s+\w+\s+on\s+(\w+)\s*\(([^)]*)\)", src, re.I)
                ev = []
                for e in (h.group(2).split(",") if h else []):
                    w = e.strip().lower().split()
                    if len(w) == 2:
                        ev.append({"before": "保存前", "after": "保存後"}.get(w[0], w[0]) + "・"
                                  + {"insert": "作成", "update": "更新", "delete": "削除", "undelete": "復元"}.get(w[1], w[1]))
                put(f"trigger:{name}", 種類="Apex トリガ", 動く時=(f"{h.group(1)}: " + "、".join(ev)) if h else None,
                    状態=STATUS.get(_t(m, "status"), _t(m, "status")), APIバージョン=_t(m, "apiVersion"))
            else:
                how = [lab for pat, lab in ((r"@AuraEnabled", "画面（LWC・Aura）"), (r"@InvocableMethod", "フロー・プロセス"),
                                            (r"implements\s+[^{]*\bSchedulable\b", "スケジュール"), (r"Database\.Batchable", "バッチ"),
                                            (r"@RestResource", "REST API"), (r"\bwebservice\b", "SOAP API"),
                                            (r"@future", "非同期（future）"), (r"implements\s+[^{]*\bQueueable\b", "非同期（Queueable）"))
                       if re.search(pat, src, re.I)]
                put(f"apex:{name}", 種類="Apex クラス", 呼ばれ方="・".join(how), 状態=STATUS.get(_t(m, "status"), _t(m, "status")),
                    APIバージョン=_t(m, "apiVersion"))
    # 入力規則・数式項目・積み上げ集計
    od = os.path.join(fa, "objects")
    for obj in (os.listdir(od) if os.path.isdir(od) else []):
        vd = os.path.join(od, obj, "validationRules")
        for fn in (os.listdir(vd) if os.path.isdir(vd) else []):
            r = _x(os.path.join(vd, fn))
            name = fn.split(".")[0]
            put(f"vr:{obj}.{name}", 種類="入力規則", 動く時=f"保存前（{obj}・作成・更新時）", 状態=STATUS.get(_t(r, "active"), _t(r, "active")),
                説明=_short(_t(r, "description")), エラーの表示先=_t(r, "errorDisplayField"))
        fd = os.path.join(od, obj, "fields")
        for fn in (os.listdir(fd) if os.path.isdir(fd) else []):
            r = _x(os.path.join(fd, fn))
            name = fn.split(".")[0]
            if _t(r, "summaryOperation"):
                put(f"rollup:{obj}.{name}", 種類="積み上げ集計項目", 動く時=f"子（{_t(r, 'summaryForeignKey') or ''}）の保存のあと",
                    説明=_short(_t(r, "description")), ヘルプ=_short(_t(r, "inlineHelpText")))
            elif _t(r, "formula"):
                put(f"formula:{obj}.{name}", 種類="数式項目", 動く時="読むたびに計算（保存はしない）", データ型=_t(r, "type"),
                    説明=_short(_t(r, "description")), ヘルプ=_short(_t(r, "inlineHelpText")))
    # 項目自動更新（ワークフローのルールから＝保存時／承認プロセスから＝申請・承認・却下・取り下げ時）
    wd = os.path.join(fa, "workflows")
    calls: dict[str, list[str]] = {}
    for fn in (os.listdir(wd) if os.path.isdir(wd) else []):
        r = _x(os.path.join(wd, fn))
        obj = fn.split(".")[0]
        for ru in (r.iter(MNS + "rules") if r is not None else []):
            for a in ru.iter(MNS + "actions"):
                if _t(a, "type") == "FieldUpdate":
                    calls.setdefault(f"{obj}.{_t(a, 'name')}", []).append(
                        f"ワークフロールール「{_t(ru, 'fullName')}」（{STATUS.get(_t(ru, 'active'), '')}）の保存時")
    ad = os.path.join(fa, "approvalProcesses")
    for fn in (os.listdir(ad) if os.path.isdir(ad) else []):
        r = _x(os.path.join(ad, fn))
        obj = fn.split(".")[0]
        lab = _t(r, "label") or fn
        for sec, when in (("initialSubmissionActions", "申請時"), ("finalApprovalActions", "最終承認時"), ("finalRejectionActions", "最終却下時"),
                          ("recallActions", "取り下げ時")):
            for s in (r.iter(MNS + sec) if r is not None else []):
                for a in s.iter(MNS + "action"):
                    if _t(a, "type") == "FieldUpdate":
                        calls.setdefault(f"{obj}.{_t(a, 'name')}", []).append(f"承認プロセス「{lab}」の{when}")
        for step in (r.iter(MNS + "approvalStep") if r is not None else []):
            for sec, when in (("approvalActions", "承認時"), ("rejectionActions", "却下時")):
                for s in step.iter(MNS + sec):
                    for a in s.iter(MNS + "action"):
                        if _t(a, "type") == "FieldUpdate":
                            calls.setdefault(f"{obj}.{_t(a, 'name')}", []).append(f"承認プロセス「{lab}」のステップ「{_t(step, 'label')}」の{when}")
    for fn in (os.listdir(wd) if os.path.isdir(wd) else []):
        r = _x(os.path.join(wd, fn))
        obj = fn.split(".")[0]
        for fu in (r.iter(MNS + "fieldUpdates") if r is not None else []):
            name, op = _t(fu, "fullName"), _t(fu, "operation")
            val = _t(fu, "formula") if op == "Formula" else _t(fu, "literalValue") if op == "Literal" else _t(fu, "lookupValue") or op
            put(f"wf:{obj}.{name}", 種類="項目自動更新", 動く時="、".join(dict.fromkeys(calls.get(f"{obj}.{name}", []))) or "（呼んでいるものが見つからない）",
                設定する項目=_t(fu, "field"), 設定する値=_short(val), 説明=_short(_t(fu, "description")),
                設定後にワークフローを再評価="する" if _t(fu, "reevaluateOnChange") == "true" else None)
    # 画面・ボタン
    qd = os.path.join(fa, "quickActions")
    for fn in (os.listdir(qd) if os.path.isdir(qd) else []):
        r = _x(os.path.join(qd, fn))
        name = fn[: -len(".quickAction-meta.xml")]
        put(f"action:{name}", 種類=f"クイックアクション（{_t(r, 'type')}）",
            開くもの=_t(r, "flowDefinition") or _t(r, "lightningComponent") or _t(r, "page") or _t(r, "targetObject"))
    ld = os.path.join(fa, "lwc")
    for name in (os.listdir(ld) if os.path.isdir(ld) else []):
        r = _x(os.path.join(ld, name, f"{name}.js-meta.xml"))
        if r is None:
            continue
        tg = r.find(MNS + "targets")
        targets = [t.text.replace("lightning__", "") for t in (tg if tg is not None else []) if t.text]
        put(f"lwc:{name}", 種類="LWC", 置ける場所="・".join(targets), 公開="する" if _t(r, "isExposed") == "true" else "しない",
            説明=_short(_t(r, "description")), APIバージョン=_t(r, "apiVersion"))
    pd = os.path.join(fa, "pages")
    for fn in (os.listdir(pd) if os.path.isdir(pd) else []):
        if fn.endswith(".page-meta.xml"):
            r = _x(os.path.join(pd, fn))
            put(f"vf:{fn[: -len('.page-meta.xml')]}", 種類="Visualforce ページ", 説明=_short(_t(r, "description")), APIバージョン=_t(r, "apiVersion"))
    return out


QN_OF = {"ApexClass": "apex", "ApexTrigger": "trigger", "Visualforce": "vf", "LWC": "lwc", "Aura": "aura", "Flow": "flow",
         "QuickAction": "action", "ValidationRule": "vr", "WorkflowFieldUpdate": "wf"}


def modified_props(mapdir: str | None) -> tuple[dict[str, dict], list[dict]]:
    """lineage.py modified で取った最終更新 → 部品（qualifiedName）ごと・項目ごとの性質。"""
    if not mapdir:
        return {}, []
    sys.path.insert(0, SF_LINEAGE)
    from modified import load_all, org_label
    fn_p: dict[str, dict] = {}
    col_p: dict[tuple, dict] = {}
    for d in load_all(mapdir):
        key = f"最終更新（{org_label(d)}）"
        for k, x in d["items"].items():
            if not x.get("lastModifiedDate"):
                continue
            st, name = k.split(":", 1)
            val = f"{x['lastModifiedDate'][:10]} {x.get('lastModifiedByName') or ''}".strip()
            if st in QN_OF:
                fn_p.setdefault(f"{QN_OF[st]}:{name}", {})[key] = val
            elif st == "CustomField" and "." in name:
                for kind in ("formula", "rollup"):
                    fn_p.setdefault(f"{kind}:{name}", {})[key] = val
                o, f = name.split(".", 1)
                col_p.setdefault((o, f), {})[key] = val
    return fn_p, [{"o": o, "f": f, "p": p} for (o, f), p in col_p.items()]


def cmd_props(env: Env, argv: list[str]) -> None:
    """部品（メソッド）に、Salesforce の自動処理としての性質と、組織での最終更新（lineage.py modified で取ってあれば）を足す。
    項目にも最終更新を足す。Neo4j にだけ足す（取り込み直すと消えるので load の最後に毎回足す）。"""
    root, repo = opt(argv, "--root"), opt(argv, "--repo")
    if not (root and repo):
        sys.exit("使い方: onto_env.py props --root <プロジェクトのルート> --repo <識別子> [--map <地図のフォルダ>]")
    props = metadata_props(os.path.join(root, "force-app", "main", "default"))
    fn_mod, col_rows = modified_props(opt(argv, "--map"))
    for qn, p in fn_mod.items():
        props.setdefault(qn, {}).update(p)
    rows = [{"qn": k, "p": v} for k, v in props.items()]
    need_neo4j_driver(argv, env)
    with driver(env) as d:
        res = d.execute_query(
            "UNWIND $rows AS x MATCH (fn:cod__Function) WHERE fn.uri STARTS WITH $sys AND head(fn.cod__qualifiedName) = x.qn "
            "SET fn += x.p RETURN count(fn) AS n", rows=rows, sys=f"{env.base}code-data/{repo}/").records
        cres = d.execute_query(
            "UNWIND $rows AS x MATCH (t:cod__Table)-[:cod__hasColumn]->(c:cod__Column) "
            "WHERE t.uri STARTS WITH $db AND head(t.cod__physicalName) = x.o AND head(c.cod__physicalName) = x.f "
            "SET c += x.p RETURN count(c) AS n", rows=col_rows, db=f"{env.base}code-data/db/{repo}/").records
    print(f"自動処理の性質を {res[0]['n']} 個の部品に足した（メタデータから作った {len(rows)} 件のうち、地図に入っている部品）"
          + (f"。組織での最終更新を項目 {cres[0]['n']} 個にも足した" if col_rows else "。組織での最終更新は未取得（lineage.py modified）"))


# ---------- reset-db ----------
def cmd_reset_db(env: Env, argv: list[str], pass_env: str) -> None:
    if "--yes" not in argv:
        sys.exit("作業環境の Neo4j の中身を全部消します。よければ --yes を付けて実行する")
    if not env.running():
        sys.exit("Neo4j が止まっています。onto_env.py start で起動してから")
    need_neo4j_driver(argv, env)
    with driver(env, pass_env) as d:
        keep, _, _ = d.execute_query("CALL n10s.nsprefixes.list() YIELD prefix, namespace RETURN prefix, namespace")
        keep = [r for r in keep if not r["namespace"].startswith(EBISU) and not r["namespace"].startswith(SODECH)]
        with d.session(database="neo4j") as s:
            s.run("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 10000 ROWS").consume()
        d.execute_query(f"CALL n10s.graphconfig.init({GRAPHCONFIG})")
        for r in keep:
            d.execute_query("CALL n10s.nsprefixes.add($p, $ns)", p=r["prefix"], ns=r["namespace"])
        cnt, _, _ = d.execute_query("MATCH (n) RETURN count(n) AS c")
        cons, _, _ = d.execute_query("SHOW CONSTRAINTS YIELD name RETURN collect(name) AS names")
    print(f"消しました（残りのノード {cnt[0]['c']}。n10s の設定を作り直し、標準の接頭辞 {len(keep)} 件を残した。"
          f"一意制約: {', '.join(cons[0]['names']) or 'なし'}）")


# ---------- load ----------
def opt(argv: list[str], name: str, default: str | None = None) -> str | None:
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def cmd_load(env: Env, argv: list[str]) -> None:
    root, repo, name_ja = opt(argv, "--root"), opt(argv, "--repo"), opt(argv, "--name-ja")
    if not (root and repo and name_ja):
        sys.exit("使い方: onto_env.py load --root <プロジェクトのルート> --repo <識別子> --name-ja <日本語名> [--map <地図のフォルダ>]")
    mapdir = os.path.abspath(opt(argv, "--map") or os.path.join(root, ".lineage"))
    dest = os.path.join(mapdir, f"intermediate-{repo}.json")
    py_env = dict(os.environ, PYTHONIOENCODING="utf-8")
    steps = [
        ("中間JSON", [sys.executable, os.path.join(SF_LINEAGE, "lineage.py"), "export", "--root", root, "--out", mapdir,
                     "--repo", repo, "--name-ja", name_ja, "--json", dest]),
        ("TTL", [env.python, os.path.join(env.core, "lineage.py"), "build", "--repo", repo, "--input", dest]),
        ("取り込み", [env.python, os.path.join(env.core, "lineage.py"), "load", "--repo", repo]),
        ("検証", [env.python, os.path.join(env.core, "lineage.py"), "validate", "--repo", repo]),
    ]
    for label, cmd in steps:
        e = dict(py_env)
        if label != "中間JSON":
            e[PASS_ENV] = password()
        r = subprocess.run(cmd, env=e, capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and not l.startswith("[情報]")]
        key = next((l for l in lines if l.startswith("SHACL 検証")), None) if label == "検証" else None
        print(f"[{label}] " + (key or (lines[-1] if lines else "")))
        if r.returncode != 0:
            print("\n".join(lines[-15:]))
            sys.exit(f"{label}で止まりました")
    # オブジェクトの関係（参照・主従）の線を足す
    r = subprocess.run([env.python, os.path.abspath(__file__), "--env", env.path, "relations", "--repo", repo, "--map", mapdir],
                       env=dict(py_env, **{PASS_ENV: password()}), capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("[関係] " + ((r.stdout.strip().splitlines() or [""])[-1] if r.returncode == 0 else (r.stdout + r.stderr)[-500:]))
    # 自動処理の性質（いつ動くか・有効か・開始条件など）を足す
    r = subprocess.run([env.python, os.path.abspath(__file__), "--env", env.path, "props", "--root", root, "--repo", repo, "--map", mapdir],
                       env=dict(py_env, **{PASS_ENV: password()}), capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("[性質] " + ((r.stdout.strip().splitlines() or [""])[-1] if r.returncode == 0 else (r.stdout + r.stderr)[-500:]))


# ---------- open / query ----------
def cypher_blocks() -> dict[str, str]:
    text = open(CYPHER_BOOK, encoding="utf-8").read()
    blocks = [b.strip() for b in re.split(r"^=+\s*$", text, flags=re.M)]
    out = {}
    for b in blocks:
        m = re.match(r"// (\S+)", b)
        if m:
            out[m.group(1)] = b
    return out


def fill(block: str, sets: list[str]) -> str:
    for kv in sets:
        k, v = kv.split("=", 1)
        if re.fullmatch(r"\d+", v):
            block, n = re.subn(rf"\b\d+ AS {re.escape(k)}\b", f"{v} AS {k}", block, count=1)
        else:
            block, n = re.subn(rf"'[^']*' AS {re.escape(k)}\b", "'" + v.replace("'", "\\'") + f"' AS {k}", block, count=1)
        if not n:
            sys.exit(f"枠の中に「AS {k}」がありません")
    return block


def to_clipboard(text: str) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write(text)
        p = f.name
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Get-Content -Raw -Encoding UTF8 -LiteralPath '{p}' | Set-Clipboard"], check=True)
    finally:
        os.remove(p)


def cmd_open(env: Env, argv: list[str]) -> None:
    if not env.running():
        cmd_start(env)
    url = f"http://localhost:{env.http_port}/browser/?dbms=neo4j://neo4j@localhost:{env.bolt_port}"
    q = opt(argv, "--query")
    text = opt(argv, "--cypher")
    if opt(argv, "--cypher-file"):
        text = open(opt(argv, "--cypher-file"), encoding="utf-8-sig").read()
    if text:   # Claude がその場で組み立てた Cypher
        to_clipboard(text.strip())
        print("Cypher をクリップボードに入れました。Neo4j Browser の入力欄に Ctrl+V → Ctrl+Enter")
    elif q:
        blocks = cypher_blocks()
        key = next((k for k in blocks if k == q or k.startswith(q)), None)
        if not key:
            sys.exit(f"Cypher 集に「{q}」がありません（あるもの: {'、'.join(blocks)}）")
        sets = [argv[i + 1] for i, a in enumerate(argv) if a == "--set" and i + 1 < len(argv)]
        to_clipboard(fill(blocks[key], sets))
        print(f"Cypher 集の {key} をクリップボードに入れました。Neo4j Browser の入力欄に Ctrl+V → Ctrl+Enter")
    os.startfile(url)
    print(f"開きました: {url}（初回だけパスワードでログイン）")


# ---------- show（Claude 用のブラウザで、入力・実行まで行う） ----------
CDP_PORT = 9333
BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]


def port_up(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def cmd_show(env: Env, argv: list[str]) -> None:
    """Claude 用のブラウザの窓（専用のプロファイル。普段のブラウザとは別）で Neo4j Browser を開き、ログイン・Cypher の入力・実行まで行う。
    パスワードは環境変数から読んでログイン欄に入れるだけで、表示しない。--shot <png> で実行後の画面を保存する（Claude が見て確かめる用）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # この Python に無ければ、作業環境の .venv の Python で動かし直す（neo4j ドライバーと playwright を入れてある）
        if os.path.isfile(env.python) and os.path.normcase(sys.executable) != os.path.normcase(env.python):
            sys.exit(subprocess.call([env.python, os.path.abspath(__file__), "--env", env.path] + argv,
                                     env=dict(os.environ, PYTHONIOENCODING="utf-8")))
        sys.exit(f"Python の playwright がありません（{env.python} -m pip install playwright。ブラウザの取得は要らない）。"
                 "代わりに onto_env.py open（クリップボードに入れて開く）を使う")
    text = cypher_text(argv)
    if not env.running():
        cmd_start(env)
    url = f"http://localhost:{env.http_port}/browser/?dbms=neo4j://neo4j@localhost:{env.bolt_port}"
    n_nodes = 0
    if text:   # 先に読み取りで流して、0 件なら開かない。丸の数で見せ方（拡大）を決める
        try:
            from neo4j import READ_ACCESS
            with driver(env) as d, d.session(database="neo4j", default_access_mode=READ_ACCESS) as s:
                res = list(s.run(text))
            if not res:
                sys.exit("結果が 0 件なので開きませんでした（名前の書き方を確かめる。Cypher 集の⓪で探せる）")
            n_nodes = len({(tuple(sorted(x.labels)), x.get("name") or x.element_id) for r in res for x in r.values() if hasattr(x, "labels")})
        except ImportError:
            pass
    if not port_up(CDP_PORT):
        exe = next((b for b in BROWSERS if os.path.isfile(b)), None)
        if not exe:
            sys.exit("Chrome も Edge も見つかりません")
        profile = os.path.join(env.path, "browser-profile")
        subprocess.Popen([exe, f"--remote-debugging-port={CDP_PORT}", f"--user-data-dir={profile}", "--no-first-run",
                          "--no-default-browser-check", "--new-window", url], creationflags=0x00000008)  # 会話と切り離して動かす
        for _ in range(40):
            if port_up(CDP_PORT):
                break
            time.sleep(0.5)
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        ctx = b.contexts[0]
        page = next((pg for pg in ctx.pages if f":{env.http_port}/browser" in pg.url), None)
        if page is None:
            page = ctx.pages[0] if ctx.pages and ctx.pages[0].url in ("about:blank", "chrome://newtab/") else ctx.new_page()
            page.goto(url)
        page.bring_to_front()
        try:   # 窓を前に出して最大化する（一度しまってから戻すと、ほかの窓の後ろにあっても前に出る）
            cdp = ctx.new_cdp_session(page)
            wid = cdp.send("Browser.getWindowForTarget")["windowId"]
            # 最小化から直接は最大化できない（Chrome の決まり）ので、通常に戻してから最大化する
            for state in ("minimized", "normal", "maximized"):
                cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"windowState": state}})
        except Exception as e:  # noqa: BLE001
            print(f"（窓を前に出せませんでした: {str(e)[:120]}）")
        page.wait_for_load_state("domcontentloaded")

        def login(wait_ms: int) -> bool:
            """ログインの欄が出ていれば、環境変数のパスワードを入れて接続する（表示しない）。ログインしたら True。"""
            pwd = page.locator("input[type=password]")
            try:
                pwd.first.wait_for(state="visible", timeout=wait_ms)
            except Exception:  # noqa: BLE001  ログイン済み
                return False
            pwd.first.fill(password())
            page.get_by_role("button", name="Connect", exact=True).click()
            page.locator("input[type=password]").first.wait_for(state="hidden", timeout=15000)
            page.wait_for_timeout(2500)   # 接続の直後はデータベースの選択が終わっていない（すぐ実行すると No active database）
            return True

        login(4000)
        for _ in range(3):   # はじめて開いたときの案内を閉じる
            d = page.get_by_role("button", name="Dismiss", exact=True)
            if d.count() and d.first.is_visible():
                d.first.click()
                page.wait_for_timeout(300)
        sb = page.get_by_role("button", name="Collapse Sidebar", exact=True)   # 左の欄を閉じて図を広くする
        if sb.count() and sb.first.is_visible():
            sb.first.click()
        if text and "--keep" not in argv:   # 前の結果を片付ける（--keep で残す。前の問い合わせは History から開ける）
            rm = page.get_by_role("button", name="Remove frame", exact=True)
            for _ in range(rm.count()):
                if rm.count() and rm.first.is_visible():
                    rm.first.click()
                    page.wait_for_timeout(150)
        if text:
            ed = page.locator(".cm-editor .cm-content").first
            ed.wait_for(state="visible", timeout=10000)

            def run() -> None:
                ed.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                page.keyboard.insert_text(text.strip())
                page.keyboard.press("Control+Enter")

            run()
            # Neo4j を起動し直したあとの古いタブは、実行して初めてログインの欄が出る。そのときはログインしてやり直す
            if login(2000):
                run()
            page.wait_for_timeout(int(float(opt(argv, "--wait", "6")) * 1000))
            if page.get_by_text("No active database").count():   # それでも間に合わなかったら、失敗の枠を消して 1 回やり直す
                rm = page.get_by_role("button", name="Remove frame", exact=True)
                if rm.count():
                    rm.first.click()
                page.wait_for_timeout(1500)
                run()
                page.wait_for_timeout(int(float(opt(argv, "--wait", "6")) * 1000))
            # 入力欄を空にして小さくし、結果の図が見えるようにする（問い合わせ文は結果の枠の見出しに残る）
            ed.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.wait_for_timeout(800)
            # 丸が多いと縮小されて名前が消えるので、右の一覧の欄を閉じて広げ、1段拡大する（はみ出した所は本人がドラッグ・ホイールで見る）
            if n_nodes > 15:
                ov = page.get_by_text("Results overview", exact=True)   # 開け閉めの状態はブラウザが覚えているので、開いているときだけ閉じる
                if ov.count() and ov.first.is_visible():
                    page.get_by_role("button", name="Toggle graph details panel", exact=True).first.click()
                    page.wait_for_timeout(700)
                zi = page.get_by_role("button", name="Zoom in", exact=True)
                if zi.count() and zi.first.is_visible():
                    zi.first.click()
                    page.wait_for_timeout(700)
            top = page.get_by_role("button", name="Remove frame", exact=True)   # 結果の枠の頭を見える位置に戻す
            if top.count():
                top.first.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
        shot = opt(argv, "--shot")
        if shot:
            page.screenshot(path=shot)
        b.close()   # 接続を切るだけ。窓はそのまま残る
    print(("実行しました" if text else "開きました") + f"（Claude 用のブラウザの窓。{url}）" + (f"・丸 {n_nodes} 個" if n_nodes else "")
          + (f"。画面: {shot}" if shot else ""))


def cypher_text(argv: list[str]) -> str | None:
    """--cypher / --cypher-file / --query（＋--set）から Cypher を作る。"""
    if opt(argv, "--cypher-file"):
        return open(opt(argv, "--cypher-file"), encoding="utf-8-sig").read()
    if opt(argv, "--cypher"):
        return opt(argv, "--cypher")
    q = opt(argv, "--query")
    if q:
        blocks = cypher_blocks()
        key = next((k for k in blocks if k == q or k.startswith(q)), None)
        if not key:
            sys.exit(f"Cypher 集に「{q}」がありません（あるもの: {'、'.join(blocks)}）")
        return fill(blocks[key], [argv[i + 1] for i, a in enumerate(argv) if a == "--set" and i + 1 < len(argv)])
    return None


def show(v) -> str:
    """ノード・関係（仮のものも）を読める形にする。"""
    if hasattr(v, "labels"):
        return f"[{'/'.join(sorted(v.labels))}] {v.get('name') or v.get('表示名') or ''}"
    if hasattr(v, "type") and hasattr(v, "start_node"):
        return f"-{v.type}->"
    return str(v)


def cmd_query(env: Env, argv: list[str]) -> None:
    """読み取り専用。図の Cypher（a・rel・b を返すもの）は「丸 -線-> 丸」の形で出るので、開く前の確かめにも使う。"""
    q = open(opt(argv, "--file"), encoding="utf-8-sig").read() if opt(argv, "--file") else (argv[1] if len(argv) > 1 else None)
    if not q:
        sys.exit('使い方: onto_env.py query "<Cypher>"  または  query --file <Cypherのファイル> [--limit 200]')
    limit = int(opt(argv, "--limit", "200"))
    need_neo4j_driver(argv, env)
    from neo4j import READ_ACCESS
    with driver(env) as d, d.session(database="neo4j", default_access_mode=READ_ACCESS) as s:
        res = list(s.run(q))
    if not res:
        print("（0 行）")
        return
    keys = list(res[0].keys())
    # 仮の丸（apoc.create.vNode）は行ごとに ID が変わるので、種類と名前で数える
    nodes = {(tuple(sorted(x.labels)), x.get("name") or x.get("表示名") or x.element_id) for r in res for x in r.values() if hasattr(x, "labels")}
    print("\t".join(keys))
    for r in res[:limit]:
        print("\t".join(show(r[k]) for k in keys))
    print(f"（{len(res)} 行" + (f"・丸 {len(nodes)} 個" if nodes else "") + (f"。先頭の {limit} 行だけ表示" if len(res) > limit else "") + "）")


def main() -> None:
    argv = sys.argv[1:]
    env_path = (opt(argv, "--env") or os.environ.get("ONTO_ENV")
                or next((p for p in DEFAULT_ENVS if os.path.isfile(os.path.join(p, "start-neo4j.cmd"))), DEFAULT_ENVS[0]))
    if "--env" in argv:
        i = argv.index("--env"); del argv[i:i + 2]
    if not argv:
        print(__doc__)
        return
    env = Env(env_path)
    cmd = argv[0]
    # Neo4j を使うコマンドは、止まっていれば先に起動する（PC の起動時に立ち上げておかなくてよい）
    if cmd in ("load", "query", "relations", "props", "open", "show") and not env.running():
        cmd_start(env)
    if cmd == "setup":
        cmd_setup(env)
    elif cmd == "start":
        cmd_start(env)
    elif cmd == "stop":
        cmd_stop(env)
    elif cmd == "status":
        cmd_status(env, argv)
    elif cmd == "reset-db":
        cmd_reset_db(env, argv, opt(argv, "--password-env", PASS_ENV))
    elif cmd == "load":
        cmd_load(env, argv)
    elif cmd == "open":
        cmd_open(env, argv)
    elif cmd == "query":
        cmd_query(env, argv)
    elif cmd == "relations":
        cmd_relations(env, argv)
    elif cmd == "show":
        cmd_show(env, argv)
    elif cmd == "props":
        cmd_props(env, argv)
    else:
        print(__doc__)
        sys.exit(f"知らないコマンドです: {cmd}")


if __name__ == "__main__":
    main()
