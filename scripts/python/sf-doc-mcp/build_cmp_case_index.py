"""
build_cmp_case_index.py — /sf-memory cat6 Step 8 で呼ぶ。
docs/knowledge/case-index.md の各行から CMP（__c / .cls / .trigger / .flow）→ 課題ID（第2列）の
マップを作り、docs/.sf/_cmp_case_index.json に保存する。cat4* が設計書の「過去の不具合」に転記する。
Usage: python build_cmp_case_index.py {project_dir}
"""
import json, re, sys
from pathlib import Path


def main():
    proj = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    index_path = proj / 'docs' / 'knowledge' / 'case-index.md'
    if not index_path.exists():
        print('[_cmp_case_index] case-index.md not found, skip')
        return
    text = index_path.read_text(encoding='utf-8')
    cmp_map = {}
    for row in text.splitlines():
        cells = row.split('|')[1:-1]
        issue_ids = re.findall(r'\b([A-Z][A-Z0-9_]*-\d+)\b', cells[1]) if len(cells) > 1 else []
        cmps = re.findall(r'\b([A-Za-z][A-Za-z0-9_]*(?:__c|\.cls|\.trigger|\.flow))\b', row)
        for cmp in cmps:
            cmp_key = cmp.replace('.cls', '').replace('.trigger', '').replace('.flow', '')
            cmp_map.setdefault(cmp_key, [])
            for issue_id in issue_ids:
                if issue_id not in cmp_map[cmp_key]:
                    cmp_map[cmp_key].append(issue_id)
    out = proj / 'docs' / '.sf' / '_cmp_case_index.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cmp_map, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[_cmp_case_index] {len(cmp_map)} CMPs → {out}')


if __name__ == "__main__":
    main()
