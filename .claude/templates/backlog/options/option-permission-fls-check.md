# option-permission-fls-check

## 何をするか

権限セット・プロファイル・FLS（Field-Level Security）・オブジェクト権限（CRUD）への影響を確認する。課題の原因または修正の影響として権限が関与していないか調査する。

## 実行手順

1. 変更対象のオブジェクト・フィールドを確定する
2. FLS 設定を確認する（`<field>` タグでオブジェクト・フィールドを一意に絞り込み、前後の `editable`/`readable` を一緒に見る）:
   ```bash
   Grep pattern: <field>{オブジェクト API 名}\.{フィールド API 名}</field>
   ファイル: force-app/main/default/permissionsets/**/*.xml
   前後行: -B 2 -A 1（editable が前・readable が後ろに並ぶ）
   ```
3. プロファイルの FLS 設定を確認する:
   ```bash
   Grep pattern: <field>{オブジェクト API 名}\.{フィールド API 名}</field>
   ファイル: force-app/main/default/profiles/**/*.profile-meta.xml
   前後行: -B 2 -A 1
   ```
4. オブジェクト権限（CRUD）設定を確認する（`<object>` タグで絞り込む。オブジェクト API 名単独の Grep はフィールド権限（`{Object}.{Field}`）にも大量にヒットし判定を誤るため使わない）:
   ```bash
   Grep pattern: <object>{オブジェクト API 名}</object>
   ファイル: force-app/main/default/permissionsets/**/*.xml, force-app/main/default/profiles/**/*.profile-meta.xml
   前後行: -B 5（allowCreate/allowDelete/allowEdit/allowRead が前に並ぶ）
   ```
5. 対象フィールド・オブジェクトが以下のどのアクセスを持つか確認する:
   - フィールド（FLS）: `readable: true / false` / `editable: true / false`
   - オブジェクト（CRUD）: `allowCreate / allowRead / allowEdit / allowDelete`
6. **組織問い合わせが必須のケース**: 以下のいずれかに該当する場合、ローカルの `permissionset`/`profile` の値だけで判定を終えず、対象組織に問い合わせて確認する:
   - ローカルの `permissionset`/`profile` に対象の `fieldPermissions`/`objectPermissions` エントリが1件もない場合（「権限なし」を意味するとは限らない。`sf project retrieve` は同時に取得した範囲外の権限エントリを省略することがある）:
     ```bash
     sf data query -q "SELECT Parent.Name, PermissionsCreate, PermissionsRead, PermissionsEdit, PermissionsDelete FROM ObjectPermissions WHERE SobjectType = '{オブジェクト API 名}'" --target-org <alias> --json
     sf data query -q "SELECT Parent.Name, PermissionsRead, PermissionsEdit FROM FieldPermissions WHERE Field = '{オブジェクト API 名}.{フィールド API 名}'" --target-org <alias> --json
     ```
   - 上記、または手順2・4で権限を付与していると判明した権限セットが所属する PermissionSetGroup に `<mutingPermissionSets>` が設定されている場合（`force-app/main/default/permissionsetgroups/**/*.xml` で確認。Muting Permission Set 本体は通常 `scripts/sf-retrieve.sh` の取得対象外でローカルに存在しない）: 上記クエリで返る構成権限セット単体の行は Muting 適用前の値のため、グループ経由でアクセス権を得るユーザー1名の実効権限を直接問い合わせる（対象ユーザーは課題報告者、または `SELECT AssigneeId FROM PermissionSetAssignment WHERE PermissionSetGroupId IN (SELECT Id FROM PermissionSetGroup WHERE DeveloperName = '{グループ名}')` で特定）:
     ```bash
     sf data query -q "SELECT DurableId, IsReadable, IsEditable, IsCreatable, IsDeletable FROM UserEntityAccess WHERE UserId = '{対象ユーザーID}' AND EntityDefinition.QualifiedApiName = '{オブジェクト API 名}'" --target-org <alias> --json
     ```
     フィールド単位は `UserFieldAccess.DurableId` がカスタム項目では `{オブジェクトAPI名}.{フィールドAPI名}` ではなく内部形式になり0件またはエラーになるため、先に `FieldDefinition` で解決してから問い合わせる:
     ```bash
     sf data query -q "SELECT DurableId FROM FieldDefinition WHERE EntityDefinition.QualifiedApiName = '{オブジェクト API 名}' AND QualifiedApiName = '{フィールド API 名}'" --target-org <alias> --json
     sf data query -q "SELECT DurableId, IsAccessible, IsUpdatable FROM UserFieldAccess WHERE DurableId = '{直前のクエリで取得した DurableId}.{対象ユーザーID}'" --target-org <alias> --json
     ```
   組織に問い合わせられない場合は「無関係」と断定せず `**[要確認: 権限未確認（組織問い合わせ不可、または権限セットグループの Muting 未確認）]**` を付ける。
7. 課題の症状（見えない・保存できない・作成できない・削除できない・エラーになる）と FLS / オブジェクト権限の関係を評価する:
   - FLS またはオブジェクト権限が原因の場合 → 修正方針を「権限設定変更」方向に更新
   - 組織問い合わせも含めて確認しどちらも無関係と判明した場合のみ → 「FLS・オブジェクト権限 確認済み・無関係」と記録
8. 修正で新規フィールド・オブジェクトを追加する場合は、必要な権限セット・プロファイルのデフォルト設定を検討する

## 出力

investigation.md「影響範囲」または「根本原因」セクションに追記:

| 権限セット / プロファイル | 対象（フィールド / オブジェクト） | 種別 | アクセス権 | 影響判定 |
|---|---|---|---|---|
| ... | {フィールド API 名} | FLS | readable / editable = true/false | 原因 / 無関係 / 要修正 / 要確認 |
| ... | {オブジェクト API 名} | CRUD | allowCreate/allowRead/allowEdit/allowDelete = true/false | 原因 / 無関係 / 要修正 / 要確認 |
