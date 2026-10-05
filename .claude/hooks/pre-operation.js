// =============================================================================
// pre-operation.js — Claude Code PreToolUse hook
//
// 5つの保護レイヤを提供する:
//
// (1) 本番組織へのコマンド: ハードブロック（permissionDecision: deny、Bash・PowerShell）
//     sf project deploy / data ops / apex run / package / org delete を
//     --target-org *prod* / *production* で実行しようとするとブロック。
//     PowerShell はこの hook だけで止める。settings.json の deny に PowerShell(...) を足すと、
//     Bash の deny で無効になっていた PowerShell ツールが全利用者で有効になる（公式 tools-reference）。
//
// (2) G:\共有ドライブ（Google Drive マウント）への削除操作: ハードブロック
//     Bash・PowerShell: rm / rmdir / del / mv（移動も実質削除）/ Remove-Item 等 / Python rmtree・unlink を検出
//     Write / Edit / MultiEdit は通過（書き込みはエージェントが日本語警告を出してから実行）
//
// (3) Backlog 書き込み系 MCP: ハードブロック（permissionDecision: deny）
//     add / update / delete / mark / reset で始まるツール名をブロック。
//     コメント投稿・課題更新・PR操作等は人間が Backlog UI から手動で実施。
//     get / count / list 等の読み取り系は対象外。
//
// (4) スクラッチパッド絶対パスの壊れた形式: ハードブロック（Bash・PowerShell）
//     POSIX ドライブ形式（/c/Users/...AppData...）、または Bash ではバックスラッシュ形式（C:\Users\...）も
//     含む場合はブロック。C:\c フォルダや文字化けゴミファイルの生成を防ぐ。
//     forward-slash 形式（C:/Users/...AppData/...）は通過。
//
// (5) Apex/LWC コード品質スキャン: 警告のみ（permissionDecision は返さず additionalContext のみ）
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

  const isShell = toolName === 'Bash' || toolName === 'PowerShell';

  // ---- Check 1: 本番組織コマンドのハードブロック（Bash・PowerShell） ----
  if (isShell) {
    const command = input.command || '';
    const segs = command.split(/&&|\|\||;/);

    // 書き込み・変更を伴う sf サブコマンド
    // data resume: 非同期 bulk DML の再開も本番では危険なため対象に含める
    // metadata deploy: sf project deploy とは別の旧来型コマンド
    // org assign/enable/disable: 本番の権限・機能設定変更
    // sf は区切りの直後に限らない（CI=true sf・$(sf …)・PowerShell の & sf・if ($?) { sf … }・"…\sf.cmd"）。
    // 引用符の中の言及（git commit -m・grep のパターン等）でも止まる（安全側）
    const dangerousCmdRe = /(?:^|[\s&({"'`\\\/])sf(?:\.cmd|\.exe|\.ps1)?["']?\s+(?:project\s+deploy|metadata\s+deploy|data\s+(?:upsert|delete|update|create|import|bulk|resume)|apex\s+run|package\s+(?:install|uninstall)|org\s+(?:delete|assign|enable|disable))/i;

    // 本番エイリアス検出: --target-org と -o 短縮形の両方に対応
    const targetProdRe = /(?:--target-org|-o)\s+\S*(?:prod|production)/i;
    // *prod*/*production* に一致しないプロジェクト固有 alias（.prod-aliases 参照）
    // 改行で文を続ける書き方（PowerShell）では1区切りに複数の org 指定が入るため、全ての値を見る
    const targetOrgValRe = /(?:--target-org|-o)\s+(\S+)/gi;
    const customProdAliases = loadCustomProdAliases();

    const prodBlocked = segs.some(s => {
      const t = s.trim();
      if (!dangerousCmdRe.test(t)) return false;
      if (targetProdRe.test(t)) return true;
      for (const m of t.matchAll(targetOrgValRe)) {
        if (customProdAliases.includes(m[1])) return true;
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

  if (isShell) {
    const command = input.command || '';
    if (sharedDriveRe.test(command)) {
      // 削除・移動のみブロック。書き込み（cp/copy/redirect/shutil.copy2 等）は通過させる
      // mv は移動先に上書きするため削除を伴う → ブロック対象に含める
      // rd/ri/mi/move は PowerShell の Remove-Item・Move-Item の別名（rd・move は cmd でも同じ）。
      // パスの一部（G:\共有ドライブ\RD部 等）と区別するため、直後に空白がある形だけを拾う
      // Clear-Content（clc）は truncate、[IO.File]::Delete・.Delete() は unlink に当たる PowerShell の書き方
      // Python ワンライナー経由の shutil.rmtree / pathlib.unlink も捕捉する
      const deleteRe = /\b(rm|rmdir|del|erase|mv|truncate)\b|\b(?:rd|ri|mi|move|clc)\s|Remove-Item|Move-Item|Clear-Content|::Delete\s*\(|\.Delete\s*\(\s*\)|shutil\.rmtree|\.unlink\s*\(|Path\s*\([^)]*\)\.unlink/i;
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

  // ---- Check 4: 壊れたスクラッチパッド絶対パスのハードブロック（Bash・PowerShell） ----
  // C:\c\... や CWD 直下の文字化けファイル（C:Users...AppData...）の生成を防ぐ。
  // 原因: スクラッチパッド絶対パスを mangle-prone な形式で渡している。
  //   - POSIX ドライブ形式 /c/Users/...AppData... → native exe が C:\c\... を生成（PowerShell も C:\c\... と解釈する）
  //   - バックスラッシュ形式 C:\Users\...AppData... → bash で区切りが消失（PowerShell では正しいパスなので Bash のみ）
  // 安全な唯一の形式は forward-slash の C:/Users/...AppData/...（bash・native 両対応）。
  if (isShell) {
    const command = input.command || '';
    const posixDrivePath   = /(?:^|[\s"'=(>])\/[a-zA-Z]\/Users\/[^\s"']*AppData/;  // /c/Users/...AppData
    const backslashWinPath = /[a-zA-Z]:\\Users\\[^\s"']*AppData/;                  // C:\Users\...AppData
    if (posixDrivePath.test(command) || (toolName === 'Bash' && backslashWinPath.test(command))) {
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
  // 検出しても処理は止めない（additionalContext のみ・permissionDecision は返さない）。
  // 根拠: security-guidance(A2) / Salesforce Development Plugin(B28) のデプロイ検証Hookの思想。
  // 制約: 正規表現ベースの簡易検出のため見逃し・誤検知があり得る。reviewer.md の詳細レビューを代替しない。
  if (toolName === 'Write' || toolName === 'Edit' || toolName === 'MultiEdit') {
    const filePath = input.file_path || '';
    const isApexOrPage = /\.(cls|trigger|page)$/i.test(filePath);
    const isLwcJs = /\.js$/i.test(filePath) && /[\\/]lwc[\\/]/i.test(filePath);

    if (isApexOrPage || isLwcJs) {
      // 書き込み前のファイル（Edit/MultiEdit の置換位置とテストクラスの判定に使う）
      let disk = '';
      if (toolName !== 'Write') {
        try { disk = fs.readFileSync(filePath, 'utf8'); } catch (e) { /* 読めなければ new_string だけで判定 */ }
      }
      // 置換位置がブロックコメント（ApexDoc 等）の中なら、断片の先頭に /* を補ってコメントとして扱う
      const inBlockComment = old => {
        const i = old ? disk.indexOf(old) : -1;
        if (i < 0) return false;
        const before = disk.slice(0, i);
        return before.lastIndexOf('/*') > before.lastIndexOf('*/');
      };
      const fragment = e => (inBlockComment(e.old_string) ? '/*' : '') + (e.new_string || '');
      let fragments = [];
      if (toolName === 'Write') {
        fragments = [input.content || ''];
      } else if (toolName === 'Edit') {
        fragments = [fragment(input)];
      } else if (toolName === 'MultiEdit') {
        fragments = (input.edits || []).map(fragment);
      }

      const findings = [];

      // コメントは全項目で、文字列リテラルは (c)(d) のキーワード判定で読み飛ばす
      // （文字列中の // をコメントと誤らないよう、左から1つの正規表現で拾う。行は残す。閉じていないブロックコメントは断片の末尾まで）
      const tokenRe = /\/\*[\s\S]*?(?:\*\/|$)|\/\/[^\n]*|'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"/g;
      const stripComments = s => s.replace(tokenRe, m => (m[0] === '/' ? m.replace(/[^\n]/g, '') : m));
      const stripCode = s => s.replace(tokenRe, m => (m[0] === '/' ? m.replace(/[^\n]/g, '') : "''"));
      const noComments = fragments.map(stripComments).join('\n');
      const codeOnly = fragments.map(stripCode).join('\n');

      // (a) SOQLインジェクション: SELECT と FROM を含む行で文字列リテラルが + 連結されており、
      //     escapeSingleQuotes による対策が見当たらない
      //     （クォート境界の厳密パースはエスケープされた ' の扱いが崩れるため、行単位のキーワード共起で判定。
      //      + は ' の直前・直後にあるものだけを連結とみなす。i++ 等は対象外）
      const soqlConcatLineRe = /^(?=.*\bSELECT\b)(?=.*\bFROM\b)(?=.*(?:'\s*\+|\+=?\s*')).*$/im;
      if (soqlConcatLineRe.test(noComments) && !/escapeSingleQuotes/.test(noComments)) {
        findings.push('SOQLインジェクションの疑い: SOQL文字列らしきリテラルが + で連結されており、String.escapeSingleQuotes が見当たりません');
      }

      // (b) ハードコードID: 標準オブジェクト(00始まり)/カスタムオブジェクト(a+数字始まり)の
      //     15桁/18桁IDリテラル（reviewer.md パターン4と同一パターン）
      const hardcodedIdRe = /['"](00[0-9A-Za-z]|a[0-9][0-9A-Za-z])[0-9A-Za-z]{12}([0-9A-Za-z]{3})?['"]/;
      if (hardcodedIdRe.test(noComments)) {
        findings.push('ハードコードIDの疑い: 15桁/18桁のSalesforce ID文字列リテラルが含まれています');
      }

      // (c) SOQL in loop: for/whileループの「本体」でSOQLクエリを発行している
      //     （ループ宣言の for (x : [SELECT ...]) 形式は1回しか評価されないため対象外）
      const lines = codeOnly.split('\n');
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
      //     テストクラス（@isTest / testMethod）はテストデータ作成の DML が主なため対象外。
      //     Edit/MultiEdit の new_string には @isTest が無いことが多いため、書き込み前のファイルも見る
      const hasDml = /\b(?:insert|update|delete|upsert|undelete)\s+\w/.test(codeOnly) ||
                     /Database\.(?:insert|update|delete|upsert|undelete)\s*\(/.test(codeOnly);
      const hasSoql = /\[\s*SELECT\b/i.test(codeOnly) || /Database\.query\s*\(/.test(codeOnly);
      const hasFlsCheck = /Security\.stripInaccessible|\.isAccessible\s*\(\)|\.isCreateable\s*\(\)|\.isUpdateable\s*\(\)|\.isDeletable\s*\(\)|WITH\s+SECURITY_ENFORCED|WITH\s+USER_MODE|AccessLevel\.USER_MODE|\b(?:insert|update|upsert|delete|undelete|merge)\s+as\s+user\b/i.test(noComments);
      const isTestClass = () => /@isTest\b|\btestMethod\b/i.test(codeOnly + '\n' + stripCode(disk));
      if ((hasDml || hasSoql) && !hasFlsCheck && !isTestClass()) {
        findings.push('FLS/CRUDチェック漏れの疑い: DML/SOQLがありますが、isAccessible等・WITH SECURITY_ENFORCED・Security.stripInaccessible等が見当たりません');
      }

      if (findings.length > 0) {
        console.log(JSON.stringify({
          hookSpecificOutput: {
            hookEventName: 'PreToolUse',
            additionalContext: '[Check5: コード品質スキャン警告] ' + filePath + '\n- ' + findings.join('\n- ') + '\n※ 正規表現による簡易検出のため誤検知がある。実際に問題かは文脈で判断し、問題でも依頼の範囲外なら直さず、派生事項として報告に添えること。'
          }
        }));
        return;
      }
    }
  }
});
