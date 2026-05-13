# 新メンバー向けセットアップチェックリスト

Claude Code + SF テンプレートの初期設定。順番に実施する。

---

## 1. 前提ツールの確認

```bash
python -V      # 3.10+ を確認。"python: command not found" なら下記参照
node -v        # hook 用。Node.js 18+ を確認
git --version  # 2.0+
```

### Python が "command not found" になる場合

Windows の場合、Git Bash では `python` コマンドが PATH に含まれないことがある。

**確認**:
```powershell
# PowerShell または cmd で確認
where python
```

**対処（Git Bash で使えるようにする）**:
1. Python インストール時に「Add Python to PATH」にチェックを入れ直す
2. または `~/.bashrc` に追加（パスは自環境に合わせて）:
   ```bash
   export PATH="/c/Users/{ユーザー名}/AppData/Local/Programs/Python/Python3XX:$PATH"
   ```
3. Git Bash を再起動して `python -V` が通ることを確認

---

## 2. Python 依存パッケージのインストール

```bash
pip install -r scripts/python/requirements.txt
```

---

## 3. Claude Code のインストール・認証

```bash
# インストール（Node.js が必要）
npm install -g @anthropic-ai/claude-code

# 認証（初回のみ）
claude login
```

---

## 4. Salesforce 組織の認証

```bash
# プロジェクトフォルダで実行
/sf-setup
```

認証が完了すると `CLAUDE.md` に接続組織情報が記録される。

---

## 5. `.backlog_config.yml` の初期作成

`/backlog` コマンドを初めて実行すると、xlsx の保存先フォルダを聞かれる。
絶対パスで回答すると `docs/.backlog_config.yml` が自動生成される。

手動で作成する場合:
```yaml
report_dir: C:/work/backlog_records
```

---

## 6. 動作確認

```bash
# Claude Code を起動して基本確認
claude

# チャットで確認
> python が動くか確認して
> /backlog  # 実際の課題IDを使ってテスト
```

---

## トラブルシュート

- Bash 出力が変 / `{xlsx_folder}` がリテラルで出る → [backlog-placeholders.md](../troubleshooting/backlog-placeholders.md) を参照
- hook エラーが出る → Node.js のインストールを確認 (`node -v`)
- `openpyxl not found` → `pip install openpyxl` を実行
