#!/usr/bin/env python3
"""hook（.claude/hooks/pre-operation.js・post-query-reminder.js）の回帰テスト。

テンプレート開発者が hook・settings.json の deny を直したら、コミット前に実行する:
    python3 scripts/check_hooks.py              # HEAD の版の pre-operation.js とも比べる
    python3 scripts/check_hooks.py --base path/to/pre-operation.js

確かめること（1件でも食い違えば exit 1。最後の行だけでなく、各行の判定を見る）:
- settings.json の hook の起動が、作業フォルダを移しても見つかる形（${CLAUDE_PROJECT_DIR} 基準）で、PreToolUse は失敗したら止めるか
- 代表的な入力で、止めるべき操作が止まり（block）、通すべき操作が通る（pass）か
- HEAD の版で止まっていたケースが、今の版で止まらなくなっていないか（弱まった）
- settings.json の deny の各行に当たるコマンドを、hook も Bash・PowerShell の両方で止めるか
  （deny は Bash の書いたとおりの形しか止めないので、PowerShell・言い換え・hook が動かない場合の守りの穴になる）
テスト入力に本番向けのコマンド文字列が入るので、ケースは Bash に直接書かず、このファイルに置く。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"
B, P, W = "block", "pass", "warn"


def bash(cmd: str, **kw) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, **kw}


def ps(cmd: str, **kw) -> dict:
    return {"tool_name": "PowerShell", "tool_input": {"command": cmd}, **kw}


def tool(name: str, **inp) -> dict:
    return {"tool_name": name, "tool_input": inp}


# (名前, 入力, 期待)。入力の cwd（Claude の作業フォルダ）と proc_cwd（hook のプロセスの作業フォルダ。既定は cwd と同じ）は
# 作業用のプロジェクト（proj）からの相対（既定は proj 直下）。proj: .prod-aliases に gf-main、既定の接続先は gf-dev（Sandbox）。
# proj/sub: .prod-aliases に sub-main。prodproj: .prod-aliases に pp-main、既定の接続先が acme_prod。loose: sfdx-project.json の無いフォルダ
CASES: list[tuple[str, object, str]] = [
    # 本番組織への変更（止める）
    ("prod: --target-org", bash("sf project deploy start --target-org acme_prod"), B),
    ("prod: -o・=・旧名 -u", bash("sf project deploy start -o=acme_prod && sf apex run -f a.apex -u acme_prod"), B),
    ("prod: パイプの後ろ", bash("echo y | sf data delete record -s Account -i 001000000000001 -o acme_prod"), B),
    ("prod: 環境変数の前置き・sfdx", bash("CI=true sfdx force:apex:execute -f a.apex -u production"), B),
    ("prod: $(sf …) の入れ子", bash('echo "$(sf data update record -s Account -i 001 -v "Name=x" -o acme_prod)"'), B),
    ("prod: executeAnonymous", bash("sf api request rest '/services/data/v62.0/tooling/executeAnonymous/?anonymousBody=x' --target-org acme_prod"), B),
    ("prod: .prod-aliases の別名", bash("sf data upsert bulk -s Account -f a.csv -i Id -o gf-main"), B),
    ("prod: サブフォルダから .prod-aliases の別名", bash("sf project deploy start -o gf-main", cwd="sub"), B),
    ("prod: 作業フォルダの .prod-aliases", bash("sf project deploy start -o sub-main", cwd="sub"), B),
    ("prod: 別のプロジェクトのサブフォルダからそこの .prod-aliases", bash("sf project deploy start -o pp-main", cwd="../prodproj/sub"), B),
    ("prod: 別のフォルダからセッションの .prod-aliases", bash("sf project deploy start -o gf-main", cwd="../loose"), B),
    ("prod: cd 先の .prod-aliases", bash("cd ../prodproj && sf project deploy start -o pp-main"), B),
    ("prod: PowerShell でサブフォルダから", ps("sf project deploy start -o gf-main", cwd="sub"), B),
    ("prod: 既定の接続先（org 指定なし）", bash("sf project deploy start -d force-app", cwd="../prodproj"), B),
    ("prod: hook がホームで動いても入力の cwd で", bash("sf project deploy start -d force-app", cwd="../prodproj", proc_cwd="../home"), B),
    ("prod: cd 先の既定の接続先", bash("cd ../prodproj && sf apex run -f a.apex"), B),
    ("prod: PowerShell & sf", ps("& sf data update record -s Account -i 001 -v \"Name='x'\" -o production"), B),
    ("prod: PowerShell if ($?)", ps("Get-Date; if ($?) { sf apex run -f a.apex --target-org acme_prod }"), B),
    # 本番の読み取り・Sandbox（通す）
    ("read: data query", bash('sf data query -q "SELECT Id FROM Account LIMIT 1" -o acme_prod'), P),
    ("read: api request rest GET", bash("sf api request rest /services/data/v62.0/limits -o acme_prod"), P),
    ("read: project retrieve", bash("sf project retrieve start -m ApexClass:Foo -r C:/tmp/bk -o acme_prod"), P),
    ("read: PowerShell data query", ps('sf data query -q "SELECT Id FROM Account" -o acme_prod'), P),
    ("sandbox: deploy", bash("sf project deploy start -d force-app -o gf-dev"), P),
    ("sandbox: dry-run", bash("sf project deploy start --dry-run -d force-app -o gf-dev"), P),
    ("sandbox: 既定の接続先（org 指定なし）", bash("sf apex run -f a.apex"), P),
    # 共有ドライブ（削除・移動だけ止める）
    ("drive: rm", bash('rm -rf "G:/共有ドライブ/資料/old"'), B),
    ("drive: PowerShell Remove-Item", ps('Remove-Item "G:\\共有ドライブ\\資料\\old" -Recurse'), B),
    ("drive: python shutil.rmtree", bash("python -c \"import shutil; shutil.rmtree(r'G:\\共有ドライブ\\資料\\old')\""), B),
    ("drive: cp（書き込み）", bash('cp a.xlsx "G:/共有ドライブ/資料/a.xlsx"'), P),
    ("drive: RD部（パスの一部）", bash('cp a.xlsx "G:/共有ドライブ/RD部/a.xlsx"'), P),
    ("drive: Write", tool("Write", file_path="G:\\共有ドライブ\\資料\\a.md", content="x"), P),
    # Backlog・Claude in Chrome
    ("backlog: add comment", tool("mcp__backlog__add_issue_comment"), B),
    ("backlog: get issue", tool("mcp__backlog__get_issue"), P),
    ("chrome: Salesforce", tool("mcp__claude-in-chrome__navigate", url="https://acme.my.salesforce.com/lightning"), B),
    ("chrome: Google ドキュメント", tool("mcp__claude-in-chrome__navigate", url="https://docs.google.com/document/d/x"), P),
    # スクラッチパッドのパスの形
    ("path: /c/Users/...AppData", bash("ls /c/Users/u/AppData/Local/Temp"), B),
    ("path: C:\\Users\\...AppData（Bash）", bash("ls C:\\Users\\u\\AppData\\Local\\Temp"), B),
    ("path: C:/Users/...AppData", bash("ls C:/Users/u/AppData/Local/Temp"), P),
    ("path: PowerShell の C:\\Users\\...AppData", ps("Get-ChildItem C:\\Users\\u\\AppData\\Local\\Temp"), P),
    # Apex のコード品質（警告だけ・止めない）
    ("apex: SOQL in loop", tool("Write", file_path="force-app/main/default/classes/A.cls",
                               content="public class A {\n  void f(List<Id> ids) {\n    for (Id i : ids) {\n"
                                       "      Account a = [SELECT Id FROM Account WHERE Id = :i WITH USER_MODE];\n    }\n  }\n}"), W),
    ("apex: 問題なし", tool("Write", file_path="force-app/main/default/classes/B.cls", content="public class B { Integer n = 1; }"), P),
    # ふだんの操作（通す）
    ("normal: git status", bash("git status"), P),
    ("normal: PowerShell Get-Date", ps("Get-Date"), P),
    ("normal: Edit", tool("Edit", file_path="docs/a.md", old_string="a", new_string="b"), P),
]

# post-query-reminder.js: 非本番に向けたクエリの後だけ、本番の根拠にしない旨を Claude に伝える
REMINDER_CASES: list[tuple[str, object, str]] = [
    ("reminder: Sandbox のクエリ", bash('sf data query -q "SELECT Id FROM Account" -o gf-dev'), W),
    ("reminder: 本番のクエリ", bash('sf data query -q "SELECT Id FROM Account" -o acme_prod'), P),
    ("reminder: .prod-aliases の別名", bash('sf data query -q "SELECT Id FROM Account" -o gf-main', cwd="sub"), P),
    ("reminder: cd 先の .prod-aliases", bash('cd ../prodproj && sf data query -q "SELECT Id FROM Account" -o pp-main'), P),
    ("reminder: hook が別のフォルダで動いても入力の cwd で", bash('sf data query -q "SELECT Id FROM Account"', proc_cwd="../prodproj"), W),
]


def make_fixture(base: Path) -> tuple[Path, Path]:
    proj, prodproj, home = base / "proj", base / "prodproj", base / "home"
    for d in (proj / "sub", proj / ".sf", prodproj / "sub", prodproj / ".sf", base / "loose", home):
        d.mkdir(parents=True, exist_ok=True)
    (proj / "sub" / ".prod-aliases").write_text("sub-main\n", encoding="utf-8")
    for p, org, alias in ((proj, "gf-dev", "gf-main"), (prodproj, "acme_prod", "pp-main")):
        (p / "sfdx-project.json").write_text("{}", encoding="utf-8")
        (p / ".sf" / "config.json").write_text(json.dumps({"target-org": org}), encoding="utf-8")
        (p / ".prod-aliases").write_text(f"# 本番\n{alias}\n", encoding="utf-8")
    return proj, home


def run(hook: Path, payload: dict, proj: Path, home: Path) -> str:
    payload = dict(payload)
    cwd = (proj / payload.pop("cwd", ".")).resolve()
    proc_cwd = (proj / payload.pop("proc_cwd")).resolve() if "proc_cwd" in payload else cwd
    env = {k: v for k, v in os.environ.items() if k not in ("SF_TARGET_ORG", "SFDX_DEFAULTUSERNAME")}
    env.update(CLAUDE_PROJECT_DIR=str(proj), USERPROFILE=str(home), HOME=str(home))
    r = subprocess.run(["node", str(hook)], input=json.dumps({**payload, "cwd": str(cwd)}, ensure_ascii=False).encode("utf-8"),
                       capture_output=True, timeout=30, cwd=str(proc_cwd), env=env)
    out = r.stdout.decode("utf-8", errors="replace").replace(" ", "")
    if r.returncode == 2 or '"permissionDecision":"deny"' in out:
        return B
    if r.returncode != 0:
        return f"error(exit {r.returncode})"
    return W if '"additionalContext"' in out else P


def deny_cases(settings: Path) -> list[tuple[str, object, str]]:
    """deny の各行から、その行に当たるコマンド（または道具）を作る。hook も止めるはずのもの"""
    cases = []
    for rule in json.loads(settings.read_text(encoding="utf-8"))["permissions"].get("deny", []):
        m = re.fullmatch(r"Bash\((.*)\)", rule)
        if m:
            sample = re.sub(r"\s+", " ", m.group(1).replace("*prod*", " acme_prod ").replace("*", " ")).strip()
            glob = "^" + ".*".join(re.escape(x) for x in m.group(1).split("*")) + "$"
            if not re.match(glob, sample, re.S):
                raise SystemExit(f"deny の行から作ったコマンドがその行に当たらない: {rule} → {sample}")
            cases += [(f"deny {rule}", bash(sample), B), (f"deny {rule}（PowerShell）", ps(sample), B)]
        elif rule.startswith("mcp__"):
            cases.append((f"deny {rule}", tool(rule), B))
    return cases


def settings_problems(settings: Path) -> list[str]:
    """hook の起動の書き方: 作業フォルダを移しても見つかる（${CLAUDE_PROJECT_DIR} 基準・ファイルがある）か、PreToolUse は失敗したら止めるか"""
    problems = []
    for event, groups in json.loads(settings.read_text(encoding="utf-8")).get("hooks", {}).items():
        for h in (h for g in groups for h in g.get("hooks", [])):
            m = re.fullmatch(r'node "\$\{CLAUDE_PROJECT_DIR\}/(\.claude/hooks/[\w.-]+\.js)"', h.get("command", ""))
            if h.get("command", "").startswith("node") and not (m and (ROOT / m.group(1)).is_file()):
                problems.append(f"{event}: {h['command']}（node \"${{CLAUDE_PROJECT_DIR}}/.claude/hooks/….js\" の形で、ファイルがあること）")
            if event == "PreToolUse" and h.get("onFailure") != "block":
                problems.append(f"{event}: {h.get('command')} に \"onFailure\": \"block\" が無い（hook が動かないと黙って通る）")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="比べる前の版の pre-operation.js。省略時は git の HEAD の版")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        proj, home = make_fixture(tmp / "fx")
        base = Path(args.base) if args.base else None
        if base is None:
            src = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:.claude/hooks/pre-operation.js"], capture_output=True)
            if src.returncode == 0:
                base = tmp / "base" / "pre-operation.js"
                base.parent.mkdir()
                base.write_bytes(src.stdout)
            else:
                print("（HEAD の版が取れないため、前の版との比較は省きます）")

        groups = [(HOOKS / "pre-operation.js", CASES + deny_cases(ROOT / ".claude" / "settings.json")),
                  (HOOKS / "post-query-reminder.js", REMINDER_CASES)]
        mismatches, regressions, total = settings_problems(ROOT / ".claude" / "settings.json"), [], 0
        print("== settings.json の hook の起動\n" + ("\n".join(f"{p}  <- 期待と違う" for p in mismatches) or "OK"))
        for hook, cases in groups:
            print(f"\n== {hook.name}\n{'ケース':<58} 期待   前の版  今の版")
            for name, payload, expect in cases:
                total += 1
                after = run(hook, payload, proj, home)
                before = run(base, payload, proj, home) if base and hook.name == "pre-operation.js" else "-"
                mark = "" if after == expect else "  <- 期待と違う"
                if before == B and after != B:
                    mark += "  <- 弱まった"
                    regressions.append(name)
                if after != expect:
                    mismatches.append(name)
                if mark or not name.startswith("deny "):
                    print(f"{name:<58} {expect:<6} {before:<7} {after}{mark}")
            denied = [c for c in cases if c[0].startswith("deny ")]
            if denied:
                bad = [c for c in denied if c[0] in mismatches]
                print(f"settings.json の deny の各行（Bash の行は PowerShell でも）: {len(denied) - len(bad)} / {len(denied)} 件を hook も止めた")
    print(f"\n期待と違う: {len(mismatches)} 件 / 前の版より弱まった: {len(regressions)} 件 / 全 {total} 件")
    return 1 if (mismatches or regressions) else 0


if __name__ == "__main__":
    sys.exit(main())
