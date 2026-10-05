// =============================================================================
// post-query-reminder.js — Claude Code PostToolUse hook
//
// 目的: sf data query / count / tree 等を「非本番組織」に向けて実行した直後、
//       「この結果を本番の件数・存在・有無の根拠にしてはいけない」ことを
//       additionalContext で Claude に思い出させる。
//
// 発火条件:
//   - ツール: Bash・PowerShell
//   - コマンドに "sf data query / count / tree" が含まれる
//   - かつ接続先（org 指定の値。無ければ既定の接続先）が prod / production・.prod-aliases に「一致しない」
//
// 非発火条件:
//   - prod / production 宛（本番で実査済みのためリマインダー不要）
//   - 接続先が分からない（org 指定も既定の接続先も無い）
//   - sf data query 以外のコマンド
//
// 根拠ルール: .claude/CLAUDE.md §環境スコープの確認
// =============================================================================

// 接続先の読み取りは pre-operation.js Check 1 と同じもの
const { loadCustomProdAliases, isProdOrg, sfCommands, cmdWords, targetOrgs } = require('./pre-operation');

let buf = '';
process.stdin.on('data', c => (buf += c));
process.stdin.on('end', () => {
  // pre-operation.js が関数を持たない古い版（.upgrade-keep 等で残った場合）なら何もしない
  if (typeof cmdWords !== 'function') return;

  let d;
  try {
    d = JSON.parse(buf);
  } catch (e) {
    // パース失敗時は何もしない（hook エラーで処理を止めない）
    return;
  }

  const toolName = d.tool_name || '';
  const command  = (d.tool_input && d.tool_input.command) || '';

  // Bash・PowerShell 以外は何もしない
  if (toolName !== 'Bash' && toolName !== 'PowerShell') return;

  // sf data query / count / tree（単語の順番・別名 force:data:soql:query を問わない）の呼び出し
  const call = sfCommands(command, toolName === 'Bash' ? '\\' : '`').find(c => {
    const w = cmdWords(c.cmd);
    return w.has('data') && ['query', 'count', 'tree'].some(x => w.has(x)) && !w.has('import');
  });
  if (!call) return;

  const orgs = targetOrgs(call, command);
  if (!orgs.length) return; // 接続先が分からない → リマインダー対象外

  // prod / production・.prod-aliases のカスタム本番 alias 宛なら発火しない
  const customProdAliases = loadCustomProdAliases();
  if (orgs.some(o => isProdOrg(o, customProdAliases))) return;

  // ---- 非本番クエリ検知 → additionalContext でリマインダー注入 ----
  const message = [
    `[非本番クエリ検知: ${orgs.join(', ')}]`,
    `この結果（件数・レコード存在・項目の有無）を本番の事実として断定しないこと。`,
    `本番について述べるときに本番で実査できなければ、必ず **[要確認: 本番データ未確認]** を付けること。`,
    `（根拠: .claude/CLAUDE.md §環境スコープの確認）`,
  ].join(' ');

  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: message }
  }));
});
