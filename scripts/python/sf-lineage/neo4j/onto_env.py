"""Salesforce の組織の地図を Neo4j で見る作業環境（DDD-Ontology の原本から new-onto-env.cmd で作ったもの）を、Claude Code の会話から操作する。

  python onto_env.py setup                      # 作業環境をソデック用にする（名前空間・パスワードの環境変数）。何度実行してもよい
  python onto_env.py start                      # Neo4j を別のウィンドウで起動し、つながるまで待つ
  python onto_env.py stop                       # Neo4j を止める
  python onto_env.py status                     # 起動しているか・入っているシステムと件数
  python onto_env.py reset-db --yes [--password-env 名前]   # Neo4j の中身を全部消し、n10s の設定だけ作り直す
  python onto_env.py load --root <プロジェクト> --repo <識別子> --name-ja <日本語名>   # 地図 → 中間JSON → TTL → 取り込み → 検証
  python onto_env.py open [--query ② --set 項目=見積明細.単価 --set システム=gf_uat]   # Cypher 集の枠をクリップボードに入れて Neo4j Browser を開く
  python onto_env.py query "<Cypher>"           # 読み取り専用で問い合わせて表で出す

共通の引数: --env <作業環境のフォルダ>（既定: 環境変数 ONTO_ENV、無ければ E:\\Onto-sf-lineage）

- パスワードはユーザー環境変数 SODECH_NEO4J_PASSWORD から読む（画面にもファイルにも出さない）。
  決める・変えるのは利用者が作業環境の set-neo4j-password.cmd で行う（Claude は実行しない）
- 原本（E:\\DDD-Ontology）は変えない。setup が書き換えるのは作業環境の中だけ
"""
from __future__ import annotations

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
class Env:
    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
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


def cmd_setup(env: Env) -> None:
    changed = []
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
        "mcp-neo4j.cmd": [("/v NEO4J_PASSWORD", f"/v {PASS_ENV}"), ('find "NEO4J_PASSWORD"', f'find "{PASS_ENV}"'),
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


# ---------- start / stop / status ----------
def cmd_start(env: Env) -> None:
    if env.running():
        print(f"もう起動しています（{env.bolt}）")
        return
    title = f"Neo4j {os.path.basename(env.path)}"
    # 別のウィンドウで動かす（この会話が終わっても止まらない。止めるときはそのウィンドウで Ctrl+C か onto_env.py stop）
    subprocess.Popen(["cmd", "/c", "start", title, "cmd", "/k", os.path.join(env.path, "start-neo4j.cmd")], cwd=env.path)
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
        print(f"  {r['name']}（{r['uri'].rstrip('/').rsplit('/', 1)[-1]}）: {r['c']} ノード")
    if not rows:
        print("  システムはまだ入っていません")


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
    if not env.running():
        sys.exit("Neo4j が止まっています。onto_env.py start で起動してから")
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
    if q:
        blocks = cypher_blocks()
        key = next((k for k in blocks if k == q or k.startswith(q)), None)
        if not key:
            sys.exit(f"Cypher 集に「{q}」がありません（あるもの: {'、'.join(blocks)}）")
        sets = [argv[i + 1] for i, a in enumerate(argv) if a == "--set" and i + 1 < len(argv)]
        to_clipboard(fill(blocks[key], sets))
        print(f"Cypher 集の {key} をクリップボードに入れました。Neo4j Browser の入力欄に Ctrl+V → Ctrl+Enter")
    os.startfile(url)
    print(f"開きました: {url}（初回だけパスワードでログイン）")


def cmd_query(env: Env, argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit('使い方: onto_env.py query "<Cypher>"')
    need_neo4j_driver(argv, env)
    from neo4j import READ_ACCESS
    with driver(env) as d, d.session(database="neo4j", default_access_mode=READ_ACCESS) as s:
        res = list(s.run(argv[1]))
    if not res:
        print("（0 行）")
        return
    keys = list(res[0].keys())
    print("\t".join(keys))
    for r in res[:200]:
        print("\t".join(str(r[k]) for k in keys))
    print(f"（{len(res)} 行{'。先頭の 200 行だけ表示' if len(res) > 200 else ''}）")


def main() -> None:
    argv = sys.argv[1:]
    env_path = opt(argv, "--env") or os.environ.get("ONTO_ENV") or r"E:\Onto-sf-lineage"
    if "--env" in argv:
        i = argv.index("--env"); del argv[i:i + 2]
    if not argv:
        print(__doc__)
        return
    env = Env(env_path)
    cmd = argv[0]
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
    else:
        print(__doc__)
        sys.exit(f"知らないコマンドです: {cmd}")


if __name__ == "__main__":
    main()
