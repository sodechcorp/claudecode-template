// =============================================================================
// pre-operation.js — Claude Code PreToolUse hook
//
// 5つの保護レイヤを提供する:
//
// (1) 本番組織へのコマンド: ハードブロック（permissionDecision: deny、Bash・PowerShell）
//     sf project deploy / data ops / apex run / package / org delete を
//     *prod* / *production* / .prod-aliases の org に向けて実行しようとするとブロック。
//     org 指定が無いコマンドは既定の接続先（SF_TARGET_ORG・.sf/config.json 等）で判定する。
//     PowerShell はこの hook だけで止める。settings.json の deny に PowerShell(...) を足すと、
//     Bash の deny で無効になっていた PowerShell ツールが全利用者で有効になる（公式 tools-reference）。
//
// (2) G:\共有ドライブ（Google Drive マウント）への削除操作: ハードブロック
//     Bash・PowerShell: rm / rmdir / del / mv（移動も実質削除）/ Remove-Item 等 / robocopy /MIR 等 / Python・Node の削除・移動を検出
//     Write / Edit / MultiEdit は通過（書き込みは確認不要。shared-folder-protection.md）
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
const os = require('os');
const path = require('path');

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

// ---- sf コマンドの接続先（Check 1 と post-query-reminder.js が使う） ----
const isProdOrg = (org, customProdAliases) => /prod|production/i.test(org) || customProdAliases.some(a => a.toLowerCase() === org.toLowerCase());

// 区切り（&& || ; | 改行）で文に分ける。引用符の中・$( ) や ( ) の中（nest が false なら数えない。Bash はバッククォートの中も）と
// 行継続（esc: Bash は \、PowerShell は ` の直後の改行）では分けない。
// 行継続は空白にし、コメント（行頭・空白等の後の # から行末）は捨てる（コメントの中の ' で引用符を取り違えないため）
function splitStatements(command, esc, nest = true) {
  const segs = [];
  let cur = '';
  let quote = '';
  let depth = 0;
  for (let i = 0; i < command.length; i++) {
    const c = command[i];
    if (c === esc && quote !== "'") {
      const nl = command.startsWith('\r\n', i + 1) ? 2 : command[i + 1] === '\n' ? 1 : 0;
      cur += nl ? ' ' : command.slice(i, i + 2);
      i += nl || 1;
    } else if (quote) {
      if (c === quote) quote = '';
      cur += c;
    } else if (c === "'" || c === '"' || (c === '`' && esc === '\\')) {
      quote = c;
      cur += c;
    } else if (c === '#' && (i === 0 || /[\s;|&(]/.test(command[i - 1]))) {
      const j = command.indexOf('\n', i);
      cur += ' ';
      i = (j < 0 ? command.length : j) - 1;
    } else if (depth === 0 && (c === ';' || c === '\n' || c === '|' || (c === '&' && command[i + 1] === '&'))) {
      segs.push(cur);
      cur = '';
      if (command[i + 1] === c) i++;
    } else {
      if (nest && c === '(') depth++;
      if (nest && c === ')' && depth > 0) depth--;
      cur += c;
    }
  }
  segs.push(cur);
  return segs;
}

// sf の呼び出しの位置（sfdx は sf の別名の実行ファイル）
const sfInvokeRe = /(?:^|[\s&({"'`\\\/])sf(?:dx)?(?:\.cmd|\.exe|\.ps1)?["']?(?=[\s"'@(,]|$)/gi;

// 文に分けたうえで、文の中の sf の呼び出しごとに切り出す（org 指定を、それが付いた呼び出しに結び付けるため）。
// 呼び出し（cmd）は括弧の深さに関係なく次の区切りまで、rest は括弧を数えた文の後ろ（$(sf …) の入れ子の外側の続き等）
function sfCommands(command, esc) {
  return splitStatements(command, esc).flatMap(s => {
    const starts = [...s.matchAll(sfInvokeRe)].map(m => m.index);
    return starts.map((p, i) => ({
      cmd: splitStatements(s.slice(p, starts[i + 1]), esc, false).find(x => x.trim()) || '',
      rest: s.slice(starts[i + 1] ?? s.length),
    }));
  });
}

// sf の後のコマンドの単語（フラグより前の英小文字の語。sf は単語の順番を問わず〔flexibleTaxonomy〕、
// force:apex:execute 等の別名もコロンで区切った単語として扱う。Start-Process は -ArgumentList の後ろから読む）
function cmdWords(cmd) {
  const words = [];
  const args = cmd.match(/\s-(?:ArgumentList|Args)\b([\s\S]*)/i);
  const tail = args ? args[1] : cmd.replace(/^[\s&({"'`\\\/]?sf(?:dx)?(?:\.cmd|\.exe|\.ps1)?["']?/i, '');
  for (const t of tail.split(/[\s"',:@()]+/).filter(Boolean)) {
    if (t.startsWith('-')) {
      if (words.length) break;
      continue;
    }
    if (!/^[a-z][a-z-]*$/i.test(t) || words.length === 5) break;
    words.push(t.toLowerCase());
  }
  return new Set(words);
}

// org 指定: --target-org x・-o x・--target-org=x・引用符付き・Start-Process の '-o','x'・旧名の -u / --targetusername（sf の別名）。
// 短いフラグに値を直結した -ox・束ねた -co x と、引用符の中の指定（-v "Subject='use -o flag'" 等。Start-Process の
// -ArgumentList '…' は引用符の中が引数なので除く）は弱い指定（文中の語と区別できないため、既定の接続先の判定を止めない）。
// 大文字小文字は sf と同じく区別する
const orgFlagRe = /(?<![\w-])(?:(--(?:target-org|targetusername|u))(?:=|[\s"',]+)|(-[a-z]{0,3}[ou])(=|[\s"',]+|(?=[^\s"',=-])))["']?(?!-)(\$\{\w+\}|[^\s"',;|&(){}]+)/g;
function orgFlags(seg) {
  const strong = [];
  const weak = [];
  const head = (seg.match(/^[\s&({"'`\\\/]?sf(?:dx)?(?:\.cmd|\.exe|\.ps1)?["']?/i) || [''])[0].length;
  const quoted = [];
  let q = '';
  for (let i = 0; i < seg.length; i++) {
    if (i >= head) {
      if (q) {
        if (seg[i] === q) q = '';
      } else if (seg[i] === '"' || seg[i] === "'") {
        q = seg[i];
      }
    }
    quoted[i] = !!q;
  }
  const startProcess = /\s-(?:ArgumentList|Args)\b/i.test(seg);
  for (const m of seg.matchAll(orgFlagRe)) {
    ((m[1] || (m[2].length === 2 && m[3])) && (startProcess || !quoted[m.index]) ? strong : weak).push(m[4]);
  }
  return { strong, weak };
}
const orgValClass = `[^\\s"',;|&(){}]+`;

// 同じコマンドの中の cd・Set-Location・pushd 等の移動先（別の案件フォルダに移ってから sf を実行する場合）
const cdRe = /(?:^|[\s;&|({])(?:cd|chdir|pushd|Set-Location|sl|Push-Location)(?:\s+(?:\/d|-Path|-LiteralPath))?\s+("[^"]*"|'[^']*'|[^\s;&|)}]+)/gi;

// sf がプロジェクトの設定を読むフォルダ（sfdx-project.json のあるフォルダまで上にたどる。無ければそのフォルダ）
function projectRoot(dir) {
  for (let d = path.resolve(dir); ; d = path.dirname(d)) {
    if (fs.existsSync(path.join(d, 'sfdx-project.json'))) return d;
    if (path.dirname(d) === d) return path.resolve(dir);
  }
}

// org 指定が無いときに sf が使う接続先: 同じコマンド内の SF_TARGET_ORG=・sf config set target-org と、
// 環境変数 → プロジェクト（hook の作業フォルダと cd 先）の設定 → ホームの設定のうち最初に見つかったもの。
// 設定は .sf/config.json と .sfdx/sfdx-config.json の両方を見る（sf は更新の新しい方を使うため）
function defaultOrgs(command) {
  const inline = [...command.matchAll(new RegExp(`(?:SF_TARGET_ORG|SFDX_DEFAULTUSERNAME)\\s*=\\s*["']?(${orgValClass})|config\\s+set\\s+(?:-\\S+\\s+)*target-org(?:=|\\s+)["']?(${orgValClass})`, 'gi'))]
    .map(m => m[1] || m[2]);
  const readOrgs = dir => [path.join(dir, '.sf', 'config.json'), path.join(dir, '.sfdx', 'sfdx-config.json')]
    .map(file => {
      try {
        const j = JSON.parse(fs.readFileSync(file, 'utf8'));
        return j['target-org'] || j.defaultusername;
      } catch (e) {
        return '';
      }
    })
    .filter(Boolean);
  const dirs = ['.'].concat([...command.matchAll(cdRe)].map(m => m[1]
    .replace(/^["']|["']$/g, '')
    .replace(/^\/([a-z])(?=\/|$)/i, '$1:')
    .replace(/^~(?=[\\\/]|$)/, os.homedir())));
  const env = process.env.SF_TARGET_ORG || process.env.SFDX_DEFAULTUSERNAME;
  const local = dirs.flatMap(dir => readOrgs(projectRoot(dir)));
  return inline.concat(env ? [env] : local.length ? local : readOrgs(os.homedir()));
}

// org 指定の値が変数（$X・${X}・$env:X）なら、変数名（$PROD_ALIAS 等）と同じコマンド内の代入の値（無ければ既定の接続先）
function resolveOrg(v, command) {
  if (!v.startsWith('$')) return [v];
  const name = (v.match(/^\$\{?(?:env:)?(\w+)\}?$/i) || [])[1];
  const assigned = name
    ? [...command.matchAll(new RegExp(`(?:^|[\\s;&|({])(?:\\$(?:env:)?)?${name}\\s*=\\s*["']?([^\\s"',;|&(){}$]+)`, 'gi'))].map(m => m[1])
    : [];
  return [v].concat(assigned.length ? assigned : defaultOrgs(command));
}

// sf が使う接続先の候補。org 指定が無い（弱い指定だけの）呼び出しは、弱い指定の値・同じ文の後ろの org 指定・既定の接続先をすべて候補にする（安全側）
function targetOrgs({ cmd, rest }, command) {
  const own = orgFlags(cmd);
  if (own.strong.length) return own.strong.concat(own.weak).flatMap(v => resolveOrg(v, command));
  const after = orgFlags(rest);
  return own.weak.concat(after.strong, after.weak).flatMap(v => resolveOrg(v, command)).concat(defaultOrgs(command));
}

module.exports = { loadCustomProdAliases, isProdOrg, sfCommands, cmdWords, targetOrgs };

if (require.main === module) {
  let buf = '';
  process.stdin.on('data', c => buf += c);
  process.stdin.on('end', () => onInput(buf));
}

function onInput(buf) {
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

    // 書き込み・変更を伴う sf サブコマンド（sf の後の単語の組み合わせで判定。単語の順番・コロン区切り・別名を問わない）
    // data resume: 非同期 bulk DML の再開も本番では危険なため対象に含める（data export bulk 等の読み取りは除く）
    // metadata deploy・deploy metadata: sf project deploy の旧来型・別名
    // apex execute: apex run の別名（force:apex:execute）
    // org assign/enable/disable: 本番の権限・機能設定変更。env delete: org delete の別名
    // sf は区切りの直後に限らない（CI=true sf・$(sf …)・PowerShell の & sf・if ($?) { sf … }・"…\sf.cmd"・
    // Start-Process sf -ArgumentList '…' / @('…','…')）。
    // 引用符の中の言及（git commit -m・grep のパターン等）でも止まる（安全側）
    const isDangerous = w => (w.has('deploy') && (w.has('project') || w.has('metadata'))) ||
      (w.has('data') && ['upsert', 'delete', 'update', 'create', 'import', 'bulk', 'resume'].some(x => w.has(x)) && !['export', 'query', 'get', 'search'].some(x => w.has(x))) ||
      (w.has('apex') && (w.has('run') || w.has('execute'))) ||
      (w.has('package') && (w.has('install') || w.has('uninstall'))) ||
      (w.has('org') && ['delete', 'assign', 'enable', 'disable'].some(x => w.has(x))) ||
      (w.has('env') && w.has('delete'));
    const customProdAliases = loadCustomProdAliases();

    let prodOrgs = [];
    let byDefault = false;
    for (const c of sfCommands(command, toolName === 'Bash' ? '\\' : '`')) {
      if (!isDangerous(cmdWords(c.cmd))) continue;
      prodOrgs = [...new Set(targetOrgs(c, command).filter(o => isProdOrg(o, customProdAliases)))];
      byDefault = !orgFlags(c.cmd).strong.length;
      if (prodOrgs.length) break;
    }
    if (prodOrgs.length) {
      console.log(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: '[HARD-BLOCK] 本番組織（' + prodOrgs.join(', ') + '）への変更操作はブロックされています。' +
            (byDefault ? 'org 指定が無いため、既定の接続先と同じ文の後ろの org 指定で判定しました（Sandbox に向けるなら --target-org を付ける。コマンド文字列の中の言及だけなら Grep ツールや git commit -F を使う）。' : '') +
            '\n対象コマンド: ' + command
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
      // 削除・移動のみブロック。書き込み（cp/copy/redirect/shutil.copy2・/MIR 等の無い robocopy 等）は通過させる
      // mv・名前の変更は移動先に上書きし移動元を消すため削除を伴う → ブロック対象に含める
      // rd/ri/mi/move/rni/ren は PowerShell の Remove-Item・Move-Item・Rename-Item の別名（rd・move・ren は cmd でも同じ）。
      // パスの一部（G:\共有ドライブ\RD部 等）と区別するため、直後に空白がある形だけを拾う
      // Clear-Content（clc）は truncate、[IO.File]::Delete・::DeleteFile・.Delete()・.Delete($true) は unlink、::Move・.MoveTo は mv に当たる PowerShell の書き方
      // robocopy の /MIR・/PURGE はコピー先の余分なファイルを、/MOV・/MOVE はコピー元を消す（行継続で次の行に書いた形も）。find -delete・rsync --delete・shred・git clean も同じ
      // Python・Node のワンライナー経由の削除・移動（shutil.rmtree/move・os.remove/rename 等・pathlib の unlink/rmdir/rename/replace・fs.rmSync・fs/promises の rename 等）も捕捉する
      const deleteRe = /\b(rm|rmdir|del|erase|mv|truncate|unlink|shred)\b|\b(?:rd|ri|mi|move|clc|rni|ren)\s|Remove-Item|Move-Item|Rename-Item|Clear-Content|::(?:Delete|Move)\w*\s*\(|\.Delete\s*\(\s*(?:\$?true\s*)?\)|\.MoveTo\s*\(|\brobocopy\b[\s\S]*\s\/{1,2}(?:MIR|PURGE|MOVE?)\b|\s--?delete\b|--remove-(?:source-)?files|\bgit(?:\s+-[cC]\s+\S+)*\s+clean\b|shutil\.(?:rmtree|move)|\bos\.(?:remove|removedirs|rename|renames|replace)\s*\(|Path\s*\([^)]*\)\.(?:rename|replace)\s*\(|\b(?:rm|rmdir|unlink|rename)Sync\s*\(|(?:\bfs\w*|\bpromises['"]?\)?)\.rename\s*\(/i;
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
}
