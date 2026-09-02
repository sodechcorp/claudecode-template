// =============================================================================
// pre-operation.js — Claude Code PreToolUse hook
//
// 5つの保護レイヤを提供する:
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
//
// (5) Apex/LWC コード品質スキャン: 警告のみ（permissionDecision は返さず systemMessage のみ）
//     Write / Edit / MultiEdit で .cls / .trigger / .page / lwc配下 .js を書く際、
//     FLS/CRUD漏れ・SOQLインジェクション・ハードコードID・SOQL in loop を正規表現で簡易スキャン。
//     処理は止めない（人間のレビュー・reviewer.md の詳細チェックを代替しない簡易検出）。
// =============================================================================

const fs = require('fs');

// ---- .prod-aliases: プロジェクト固有の本番エイリアス追加パターン ----
// プロジェクト直下 .prod-aliases（1行1 alias、# コメント可）が存在する場合に読み込む。
// *prod*/*production* 命名規約に一致しない本番 alias（例: gf-main）を追加保護する。
// .upgrade-keep と同じ「プロジェクト固有ファイルで上書きせず拡張する」パターン。
// ファイル自体はプロジェクト直下に置くため /upgrade の対象外＝上書きで消えない。
function loadCustomProdAliases() {
  try {
    const content = fs.readFileSync('.prod-aliases', 'utf8');
    return content.split('\n')
      .map(l => l.trim())
      .filter(l => l && !l.startsWith('#'));
  } catch (e) {
    // ファイルが無い場合は従来通り *prod*/*production* 判定のみ
    return [];
  }
}

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
    // *prod*/*production* に一致しないプロジェクト固有 alias（.prod-aliases 参照）
    const targetOrgValRe = /(?:--target-org|-o)\s+(\S+)/i;
    const customProdAliases = loadCustomProdAliases();

    const prodBlocked = segs.some(s => {
      const t = s.trim();
      if (!dangerousCmdRe.test(t)) return false;
      if (targetProdRe.test(t)) return true;
      if (customProdAliases.length > 0) {
        const m = t.match(targetOrgValRe);
        if (m && customProdAliases.includes(m[1])) return true;
      }
      return false;
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

  // ---- Check 5: Apex/LWC コード品質スキャン（警告のみ・deny しない） ----
  // Write/Edit/MultiEdit で .cls/.trigger/.page/.js（lwc配下）を書く際に、
  // FLS/CRUD漏れ・SOQLインジェクション・ハードコードID・SOQL in loop を正規表現で簡易スキャンする。
  // 検出しても処理は止めない（systemMessage のみ・permissionDecision は返さない）。
  // 根拠: security-guidance(A2) / Salesforce Development Plugin(B28) のデプロイ検証Hookの思想。
  // 制約: 正規表現ベースの簡易検出のため見逃し・誤検知があり得る。reviewer.md の詳細レビューを代替しない。
  if (toolName === 'Write' || toolName === 'Edit' || toolName === 'MultiEdit') {
    const filePath = input.file_path || '';
    const isApexOrPage = /\.(cls|trigger|page)$/i.test(filePath);
    const isLwcJs = /\.js$/i.test(filePath) && /[\\/]lwc[\\/]/i.test(filePath);

    if (isApexOrPage || isLwcJs) {
      let code = '';
      if (toolName === 'Write') {
        code = input.content || '';
      } else if (toolName === 'Edit') {
        code = input.new_string || '';
      } else if (toolName === 'MultiEdit') {
        code = (input.edits || []).map(e => e.new_string || '').join('\n');
      }

      const findings = [];

      // (a) SOQLインジェクション: SELECT と FROM を含む行に + 連結があり、
      //     escapeSingleQuotes による対策が見当たらない
      //     （クォート境界の厳密パースはエスケープされた ' の扱いが崩れるため、行単位のキーワード共起で判定）
      const soqlConcatLineRe = /^(?=.*\bSELECT\b)(?=.*\bFROM\b).*\+.*$/im;
      if (soqlConcatLineRe.test(code) && !/escapeSingleQuotes/.test(code)) {
        findings.push('SOQLインジェクションの疑い: SOQL文字列らしきリテラルが + で連結されており、String.escapeSingleQuotes が見当たりません');
      }

      // (b) ハードコードID: 標準オブジェクト(00始まり)/カスタムオブジェクト(a+数字始まり)の
      //     15桁/18桁IDリテラル（reviewer.md パターン4と同一パターン）
      const hardcodedIdRe = /['"](00[0-9A-Za-z]|a[0-9][0-9A-Za-z])[0-9A-Za-z]{12}([0-9A-Za-z]{3})?['"]/;
      if (hardcodedIdRe.test(code)) {
        findings.push('ハードコードIDの疑い: 15桁/18桁のSalesforce ID文字列リテラルが含まれています');
      }

      // (c) SOQL in loop: for/whileループの「本体」でSOQLクエリを発行している
      //     （ループ宣言の for (x : [SELECT ...]) 形式は1回しか評価されないため対象外）
      const lines = code.split('\n');
      let depth = 0;
      const loopStartDepths = [];
      let soqlInLoop = false;
      for (const line of lines) {
        if ((/\[\s*SELECT\b/i.test(line) || /Database\.(?:query|getQueryLocator)\s*\(/.test(line)) && loopStartDepths.length > 0) {
          soqlInLoop = true;
        }
        if (/\b(?:for|while)\s*\(/.test(line)) {
          loopStartDepths.push(depth);
        }
        depth += (line.match(/\{/g) || []).length;
        depth -= (line.match(/\}/g) || []).length;
        while (loopStartDepths.length > 0 && depth <= loopStartDepths[loopStartDepths.length - 1]) {
          loopStartDepths.pop();
        }
      }
      if (soqlInLoop) {
        findings.push('SOQL in loopの疑い: for/whileループの本体でSOQLクエリを発行しています');
      }

      // (d) FLS/CRUD漏れ: DML/SOQLがあるのに、ファイル内にFLS/CRUDチェックの形跡が見当たらない
      const hasDml = /\b(?:insert|update|delete|upsert|undelete)\s+\w/.test(code) ||
                     /Database\.(?:insert|update|delete|upsert|undelete)\s*\(/.test(code);
      const hasSoql = /\[\s*SELECT\b/i.test(code) || /Database\.query\s*\(/.test(code);
      const hasFlsCheck = /Security\.stripInaccessible|\.isAccessible\s*\(\)|\.isCreateable\s*\(\)|\.isUpdateable\s*\(\)|\.isDeletable\s*\(\)|WITH\s+SECURITY_ENFORCED|WITH\s+USER_MODE|AccessLevel\.USER_MODE/i.test(code);
      if ((hasDml || hasSoql) && !hasFlsCheck) {
        findings.push('FLS/CRUDチェック漏れの疑い: DML/SOQLがありますが、isAccessible等・WITH SECURITY_ENFORCED・Security.stripInaccessible等が見当たりません');
      }

      if (findings.length > 0) {
        console.log(JSON.stringify({
          hookSpecificOutput: {
            hookEventName: 'PreToolUse',
            systemMessage: '[Check5: コード品質スキャン警告] ' + filePath + '\n- ' + findings.join('\n- ') + '\n※ 正規表現ベースの簡易検出です。誤検知の可能性があり、人間のレビューを代替しません。'
          }
        }));
        return;
      }
    }
  }
});
