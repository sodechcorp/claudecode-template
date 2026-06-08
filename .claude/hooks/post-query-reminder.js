// =============================================================================
// post-query-reminder.js — Claude Code PostToolUse hook
//
// 目的: sf data query / count / tree 等を「非本番組織」に向けて実行した直後、
//       「この結果を本番の件数・存在・有無の根拠にしてはいけない」ことを
//       systemMessage で Claude に思い出させる。
//
// 発火条件:
//   - ツール: Bash
//   - コマンドに "sf data query / count / tree" が含まれる
//   - かつ --target-org / -o の値が prod / production に「一致しない」
//
// 非発火条件:
//   - prod / production 宛（本番で実査済みのためリマインダー不要）
//   - org 指定なし（デフォルト組織が不明なためノイズ化を防ぐ）
//   - sf data query 以外の Bash コマンド
//
// 根拠ルール: .claude/CLAUDE.md §環境スコープの確認
// =============================================================================

let buf = '';
process.stdin.on('data', c => (buf += c));
process.stdin.on('end', () => {
  let d;
  try {
    d = JSON.parse(buf);
  } catch (e) {
    // パース失敗時は何もしない（hook エラーで処理を止めない）
    return;
  }

  const toolName = d.tool_name || '';
  const command  = (d.tool_input && d.tool_input.command) || '';

  // Bash 以外は何もしない
  if (toolName !== 'Bash') return;

  // sf data query / count / tree のいずれかを含むか
  if (!/sf\s+data\s+(query|count|tree)\b/.test(command)) return;

  // --target-org / -o の値を抽出
  const match = command.match(/(?:--target-org|-o)\s+([^\s]+)/);
  if (!match) return; // org 指定なし → リマインダー対象外

  const orgAlias = match[1].toLowerCase();

  // prod / production 宛なら発火しない
  if (/prod(uction)?$/.test(orgAlias)) return;

  // ---- 非本番クエリ検知 → systemMessage でリマインダー注入 ----
  const message = [
    `[非本番クエリ検知: ${orgAlias}]`,
    `この結果（件数・レコード存在・項目の有無）を本番の事実として断定しないこと。`,
    `本番で実査できない場合は必ず **[要確認: 本番データ未確認]** を付けること。`,
    `（根拠: .claude/CLAUDE.md §環境スコープの確認）`,
  ].join(' ');

  process.stdout.write(JSON.stringify({ systemMessage: message }));
});
