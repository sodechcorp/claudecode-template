// =============================================================================
// pre-operation.js — Claude Code PreToolUse hook
//
// 4つの保護レイヤを提供する:
//
// (1) 本番組織へのコマンド: ハードブロック（permissionDecision: deny）
//     sf project deploy / data ops / apex run / package / org delete を
//     --target-org *prod* / *production* で実行しようとするとブロック。
//
// (2) G:\共有ドライブ（Google Drive マウント）への削除操作: ハードブロック
//     Bash: rm / rmdir / del / mv（移動も実質削除）/ Python rmtree・unlink を検出
//     Write / Edit / MultiEdit は通過（書き込みはエージェントが日本語警告を出してから実行）
//
// (3) Backlog 書き込み系 MCP: ハードブロック（permissionDecision: deny）
//     add / update / delete / mark / reset で始まるツール名をブロック。
//     コメント投稿・課題更新・PR操作等は人間が Backlog UI から手動で実施。
//     get / count / list 等の読み取り系は対象外。
//
// (4) スクラッチパッド絶対パスの壊れた形式: ハードブロック（Bash のみ）
//     POSIX ドライブ形式（/c/Users/...AppData...）またはバックスラッシュ形式（C:\Users\...）を
//     Bash に含む場合はブロック。C:\c フォルダや文字化けゴミファイルの生成を防ぐ。
//     forward-slash 形式（C:/Users/...AppData/...）は通過。
// =============================================================================

let buf = '';
process.stdin.on('data', c => buf += c);
process.stdin.on('end', () => {
  let d;
  try {
    d = JSON.parse(buf);
  } catch (e) {
    // パース失敗時は通過させる（hook エラーで全操作ブロックを避ける）
    return;
  }

  const toolName = d.tool_name || '';
  const input = d.tool_input || {};

  // ---- Check 3: Backlog 書き込み系 MCP のハードブロック ----
  // add/update/delete/mark/reset 系（コメント投稿・課題更新・PR操作等）をブロック。
  // get/count/list 系（読み取り）は対象外。文面案はチャットで提示し、
  // 投稿・更新は人間が Backlog UI から手動で実施する。
  if (/^mcp__backlog__(add|update|delete|mark|reset)/i.test(toolName)) {
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        permissionDecision: 'deny',
        permissionDecisionReason: '[HARD-BLOCK] Backlog への書き込み（コメント投稿・課題更新等）はブロックされています。文面案はチャットで提示し、投稿・更新は人間が Backlog UI から手動で実施してください。\n対象ツール: ' + toolName
      }
    }));
    return;
  }

  // ---- Check 1: 本番組織コマンドのハードブロック（Bash のみ） ----
  if (toolName === 'Bash') {
    const command = input.command || '';
    const segs = command.split(/&&|\|\||;/);

    // 書き込み・変更を伴う sf サブコマンド
    // data resume: 非同期 bulk DML の再開も本番では危険なため対象に含める
    // metadata deploy: sf project deploy とは別の旧来型コマンド
    // org assign/enable/disable: 本番の権限・機能設定変更
    const dangerousCmdRe = /^sf\s+(?:project\s+deploy|metadata\s+deploy|data\s+(?:upsert|delete|update|create|import|bulk|resume)|apex\s+run|package\s+(?:install|uninstall)|org\s+(?:delete|assign|enable|disable))/i;

    // 本番エイリアス検出: --target-org と -o 短縮形の両方に対応
    const targetProdRe = /(?:--target-org|-o)\s+\S*(?:prod|production)/i;

    const prodBlocked = segs.some(s => {
      const t = s.trim();
      return dangerousCmdRe.test(t) && targetProdRe.test(t);
    });
    if (prodBlocked) {
      console.log(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: '[HARD-BLOCK] 本番組織への変更操作はブロックされています。\n対象コマンド: ' + command
        }
      }));
      return;
    }
  }

  // ---- Check 2: G:\共有ドライブ への破壊的操作のハードブロック ----
  // 検出パターン: G:\共有ドライブ\... / G:\Shared drives\... （大小文字・スラッシュ両対応）
  const sharedDriveRe = /g:[\\\/](?:共有ドライブ|shared\s+drives)[\\\/]/i;

  if (toolName === 'Bash') {
    const command = input.command || '';
    if (sharedDriveRe.test(command)) {
      // 削除・移動のみブロック。書き込み（cp/copy/redirect/shutil.copy2 等）は通過させる
      // mv は移動先に上書きするため削除を伴う → ブロック対象に含める
      // Python ワンライナー経由の shutil.rmtree / pathlib.unlink も捕捉する
      const deleteRe = /\b(rm|rmdir|del|erase|mv|truncate)\b|Remove-Item|Move-Item|shutil\.rmtree|\.unlink\s*\(|Path\s*\([^)]*\)\.unlink/i;
      if (deleteRe.test(command)) {
        console.log(JSON.stringify({
          hookSpecificOutput: {
            hookEventName: 'PreToolUse',
            permissionDecision: 'deny',
            permissionDecisionReason: 'G:\\共有ドライブ への削除操作はブロックされました。共有データの誤削除を防ぐためです。本当に削除が必要な場合は、エクスプローラから手動で実施してください。\n対象コマンド: ' + command
          }
        }));
        return;
      }
    }
  }

  // ---- Check 4: 壊れたスクラッチパッド絶対パスのハードブロック（Bash のみ） ----
  // C:\c\... や CWD 直下の文字化けファイル（C:Users...AppData...）の生成を防ぐ。
  // 原因: スクラッチパッド絶対パスを mangle-prone な形式で渡している。
  //   - POSIX ドライブ形式 /c/Users/...AppData... → native exe が C:\c\... を生成
  //   - バックスラッシュ形式 C:\Users\...AppData... → bash で区切りが消失
  // 安全な唯一の形式は forward-slash の C:/Users/...AppData/...（bash・native 両対応）。
  if (toolName === 'Bash') {
    const command = input.command || '';
    const posixDrivePath   = /(?:^|[\s"'=(>])\/[a-zA-Z]\/Users\/[^\s"']*AppData/;  // /c/Users/...AppData
    const backslashWinPath = /[a-zA-Z]:\\Users\\[^\s"']*AppData/;                  // C:\Users\...AppData
    if (posixDrivePath.test(command) || backslashWinPath.test(command)) {
      console.log(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: '[HARD-BLOCK] スクラッチパッド絶対パスが壊れた形式です。C:\\c や文字化けファイルの生成を防ぐためブロックしました。forward-slash 形式（例: C:/Users/{user}/AppData/Local/Temp/claude/.../scratchpad/...）で渡し直してください。\n対象コマンド: ' + command
        }
      }));
      return;
    }
  }
});
