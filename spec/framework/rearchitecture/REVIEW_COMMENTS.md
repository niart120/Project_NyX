# フレームワーク再設計ドキュメント レビューコメント

> **対象**: `spec\framework\rearchitecture\*.md`  
> **レビュー観点**: `framework-spec-writing` の必須構成、公開 API の一貫性、正本の所在、依存方向、後方互換性、テスト方針  
> **結論**: 全 12 ファイルに必須 6 セクションは存在する。一方で、実装前に解消すべき正本衝突と API シグネチャ不整合が残っている。

## 1. 総評

再設計の責務分割、後方互換性、テスト方針は広く記述されている。特に `MacroExecutor` を互換対象外にし、既存ユーザーマクロの `MacroBase` / `Command` 互換を守る方針は明確である。

実装リスクが高い箇所は、同じ概念が複数ドキュメントで「正本」として定義されている点である。`RunResult`、`ExecutionContext`、Resource Port、`MacroSettingsResolver` は、シグネチャやフィールド名が文書間でずれている。ここを残したまま実装に入ると、GUI/CLI、Runtime、Logger、Resource I/O の結合部で判断が分岐する。

### 1.1 レビュー後の意思決定メモ

次の方針を採用する。

| 対象 | 採用方針 |
|------|----------|
| R-001 `RunResult` | `RunResult` は `macro_id` と `macro_name` の両方を持つ。経過時間 property は `duration_seconds` に統一し、`ok` は property として持つ |
| R-002 `ExecutionContext` | `MacroRuntimeBuilder.build()` が完全な `ExecutionContext` を組み立てる。`MacroRuntime` は `run(context)` / `start(context)` に集中する |
| R-004 `MacroSettingsResolver` | `resolve()` は `MacroSettingsSource | None` を返し、settings の出所をログ・診断・移行警告へ使えるようにする |
| R-005 識別子 | `macro_id` は安定 ID、`macro_name` は表示名、`entrypoint` は import / manifest 起点として分離する |
| R-007 `UserEvent` | 旧 handler へ `UserEvent` 互換を流さない。GUI は `GuiLogSink` へ移行し、旧 handler は技術ログ専用とする |
| R-008 optional capability | `@runtime_checkable Protocol` で表し、`CommandFacade` が capability の有無を判定する |
| R-010 settings lookup | settings も破壊的変更を許容する。`Path.cwd()` fallback と `static\<macro_name>\settings.toml` 互換は削除候補とし、manifest / project_root 明示へ寄せる |
| R-011 `DefaultCommand` 旧コンストラクタ | 既存マクロは `DefaultCommand` を直接生成しない前提とし、旧コンストラクタ互換は残さない |
| R-012 single-file macro | single-file での実行自体は許容してよい。ただし legacy 自動探索・legacy import 互換を残すための特別対応は破棄する |
| R-013 移行ガイド | マクロ側の修正を要求するため、移行ガイド仕様書を別途作成する |

R-003 Resource I/O は、ユーザー側でマクロ修正を許容できるため、既存 `static\<macro_name>` パス互換を無理に維持しない方向で再検討する。`ResourceRef` は採用候補のままだが、`legacy_static_write` や旧 static 読み書きの互換モードは削除候補とする。

## 2. レビューコメント

### R-001: `RunResult` の正本とフィールド名が衝突している

**重大度**: 重大  
**対象**:

- `RUNTIME_AND_IO_PORTS.md:3`, `RUNTIME_AND_IO_PORTS.md:313-324`
- `ERROR_CANCELLATION_LOGGING.md:3`, `ERROR_CANCELLATION_LOGGING.md:218-232`
- `FW_REARCHITECTURE_OVERVIEW.md:467-478`

**問題**:

`RUNTIME_AND_IO_PORTS.md` は `RunResult` の正本を名乗り、`RunResult` に `macro_name` と `duration_sec` を定義している。一方、`ERROR_CANCELLATION_LOGGING.md` も `RunResult` への失敗情報変換の正本を名乗り、`RunResult` に `macro_id`、`ok`、`duration_seconds` を定義している。Overview も `macro_name` / `duration_sec` 側の定義を持つ。

この状態では、GUI/CLI の `CliPresenter`、ログ相関、テスト fixture が `macro_id` と `macro_name` のどちらを参照すべきか決められない。`duration_sec` と `duration_seconds` も同じ値を指す別 API になり、テスト名と実装が分岐する。

**修正案**:

`RunResult` の値オブジェクト定義は `RUNTIME_AND_IO_PORTS.md` に一元化する。`ERROR_CANCELLATION_LOGGING.md` は `ErrorInfo`、`ErrorKind`、error code catalog、例外から `RunResult.error` への変換規則だけを定義し、`RunResult` 本体は参照に留める。`macro_id` と `macro_name` の両方が必要なら、`RunResult` または `RunLogContext` のどちらに保持するかを明記する。

### R-002: `ExecutionContext` と `MacroRuntime.create_context()` のシグネチャが組み立て不能である

**重大度**: 重大  
**対象**:

- `RUNTIME_AND_IO_PORTS.md:275-289`, `RUNTIME_AND_IO_PORTS.md:357-370`
- `FW_REARCHITECTURE_OVERVIEW.md:442-455`, `FW_REARCHITECTURE_OVERVIEW.md:511-523`
- `RUNTIME_AND_IO_PORTS.md:144-159`

**問題**:

`RUNTIME_AND_IO_PORTS.md` の `ExecutionContext` は `cancellation_token` と `artifacts` を必須フィールドとして持つ。しかし同じ文書の `MacroRuntime.create_context()` には `cancellation_token` 引数がない。Overview 側の `create_context()` は `cancellation_token` を受け取るが、`controller`、`frame_source`、`resources`、`artifacts`、`notifications`、`logger` を受け取らない。Overview の `ExecutionContext` 定義には `artifacts` もない。

さらに `MacroRuntimeBuilder.build()` のフローでは、Port 群を生成してから `MacroRuntime.create_context(...)` を呼ぶとされている。このままでは Builder が生成した `RunArtifactStore` と `CancellationToken` を `ExecutionContext` に渡す手段が文書上確定しない。

**修正案**:

`MacroRuntime.create_context()` の完全な公開シグネチャを `RUNTIME_AND_IO_PORTS.md` に一元化する。最低限、`cancellation_token` の扱い、`artifacts` を含む全 Port、`run_log_context` の生成責務、`macro_id` / `macro_name` の保持方針を明記する。Overview は詳細シグネチャを重複記載せず、正本への参照に切り替える。

### R-003: Resource Port の戻り値型と保存オプションが文書間で不一致である

**重大度**: 重大  
**対象**:

- `RUNTIME_AND_IO_PORTS.md:466-481`
- `RESOURCE_FILE_IO.md:214-248`, `RESOURCE_FILE_IO.md:300`

**問題**:

`RUNTIME_AND_IO_PORTS.md` の `ResourceStorePort.resolve_asset_path()` と `RunArtifactStore.save_image()` は `Path` を返す。一方、`RESOURCE_FILE_IO.md` は同じ Port に対して `ResourceRef` を返し、`RunArtifactStore.save_image()` には `overwrite` と `atomic` を持たせている。`RESOURCE_FILE_IO.md` では新 API の戻り値も `ResourceRef` と明記している。

Runtime 側の簡略シグネチャを正として実装すると、path guard、legacy scope、atomic write、debug log へ記録する保存先情報の扱いが欠落する。

**修正案**:

Resource Port の正本を `RESOURCE_FILE_IO.md` に置くなら、`RUNTIME_AND_IO_PORTS.md` の Port シグネチャを `ResourceRef` / `OverwritePolicy` / `atomic` 付きに同期する。逆に Runtime 側を正本にするなら、`RESOURCE_FILE_IO.md` の詳細仕様を Runtime の型へ合わせ、`ResourceRef` を内部型に限定する。

**追加判断**:

リソースパスについては破壊的変更を許容する。既存 `static\<macro_name>` 読み書き、`legacy_static_write=True`、`resource.write_mode = "legacy_static"`、`filename` 先頭が macro ID の場合の互換解釈は削除候補とする。標準モデルは `resources\<macro_id>\assets` と `runs\<run_id>\outputs` に寄せ、マクロ側を修正して移行する。

`ResourceRef` を採用する場合は、用途と由来を混同しないため、`ResourceKind` と `ResourceSource` を分ける。

```python
class ResourceKind(StrEnum):
    ASSET = "asset"
    OUTPUT = "output"


class ResourceSource(StrEnum):
    STANDARD_ASSETS = "standard_assets"
    MACRO_PACKAGE = "macro_package"
    RUN_OUTPUTS = "run_outputs"


@dataclass(frozen=True)
class ResourceRef:
    kind: ResourceKind
    source: ResourceSource
    path: Path
    relative_path: Path
    macro_id: str
    run_id: str | None = None
```

### R-004: `MacroSettingsResolver` の `resolve()` 戻り値が統一されていない

**重大度**: 中  
**対象**:

- `CONFIGURATION_AND_RESOURCES.md:171-181`
- `MACRO_COMPATIBILITY_AND_REGISTRY.md:271-276`
- `RUNTIME_AND_IO_PORTS.md:144-159`

**問題**:

`CONFIGURATION_AND_RESOURCES.md` は `MacroSettingsResolver.resolve()` の戻り値を `MacroSettingsSource | None` とし、`path`、`legacy`、`source` を持つ構造化結果を定義している。`MACRO_COMPATIBILITY_AND_REGISTRY.md` は同じメソッドを `Path | None` としている。`RUNTIME_AND_IO_PORTS.md` は Builder が `MacroSettingsResolver.load()` を呼ぶフローを正としているため、settings の出所情報を Builder が利用できるかどうかが文書によって変わる。

**修正案**:

`MacroSettingsResolver` の API 正本を 1 つに決める。設定ファイルの出所をログや診断に使う設計なら、`MacroSettingsSource | None` を採用し、`MACRO_COMPATIBILITY_AND_REGISTRY.md` は参照だけにする。出所情報を使わないなら、`MacroSettingsSource` を削除し、`Path | None` と `dict[str, Any]` の単純な契約に寄せる。

### R-005: `macro_id` / `macro_name` / `entrypoint` の責務境界がまだ曖昧である

**重大度**: 中  
**対象**:

- `RUNTIME_AND_IO_PORTS.md:379-402`
- `RUNTIME_AND_IO_PORTS.md:543-560`
- `LOGGING_FRAMEWORK.md:189-192`, `LOGGING_FRAMEWORK.md:335`

**問題**:

`RuntimeBuildRequest` は `macro_id` と `entrypoint` を持つが、`ExecutionContext` と `MacroRuntime.run()` の説明では `macro_name` を使って registry 解決している。Logging 側は `RunLogContext(run_id, macro_id, macro_name, entrypoint)` を作成するとしている。

`macro_id` が安定識別子、`macro_name` が表示名、`entrypoint` が import 先であるなら、Runtime がどの段階でどの値を正として registry 解決・ログ相関・GUI 表示に渡すかを固定する必要がある。

**修正案**:

`MacroDefinition`、`RuntimeBuildRequest`、`ExecutionContext`、`RunResult`、`RunLogContext` のフィールド対応表を追加する。特に「registry 解決キー」「ログ相関キー」「ユーザー表示名」「import entrypoint」を別列にし、同じ値を別名で扱わないようにする。

### R-006: 廃止・移行ゲートのテスト名とファイル名が同期していない

**重大度**: 中  
**対象**:

- `DEPRECATION_AND_MIGRATION.md:210-228`, `DEPRECATION_AND_MIGRATION.md:230-239`
- `TEST_STRATEGY.md:112`, `TEST_STRATEGY.md:312`
- `IMPLEMENTATION_PLAN.md:153`, `IMPLEMENTATION_PLAN.md:333`

**問題**:

`DEPRECATION_AND_MIGRATION.md` のテスト方針表は `test_no_gui_cli_reference_to_macro_executor` などを挙げているが、最小ゲートの PowerShell コマンドは `tests\integration\test_macro_runtime_legacy_executor.py` を参照している。他の文書では `test_macro_executor_removed` と `test_gui_cli_do_not_import_macro_executor` が削除ゲートとして使われている。

実装時に「どのテストを追加すれば廃止条件を満たすか」が判断しにくい。

**修正案**:

廃止ゲートはテストファイル名とテスト関数名をセットで統一する。例として、`tests\integration\test_macro_executor_removed.py::test_macro_executor_removed` と `tests\integration\test_gui_cli_runtime_adapter.py::test_gui_cli_do_not_import_macro_executor` のように、文書横断で同じ名前に揃える。

### R-007: `LegacyStringSink` が `UserEvent` を無視する移行影響が明記されていない

**重大度**: 軽微  
**対象**:

- `LOGGING_FRAMEWORK.md:354-362`
- `OBSERVABILITY_AND_GUI_CLI.md:187-202`

**問題**:

`LegacyStringSink` は `TechnicalLog` だけを旧 handler へ流し、`UserEvent` は処理しないとされている。一方、GUI 表示は `GuiLogSink` が `UserEvent` を Qt Signal へ変換する設計である。旧 handler 経由で GUI ログ表示を維持していた経路がある場合、移行後は `GuiLogSink` 登録が必須になる。

**修正案**:

`LOGGING_FRAMEWORK.md` に「旧 handler では `UserEvent` を受け取れないため、GUI のユーザー表示は `GuiLogSink` へ移行する必要がある」と明記する。あわせて GUI 起動時に `GuiLogSink` を登録し、CLI 起動時は登録しないフローを `OBSERVABILITY_AND_GUI_CLI.md` に短く追記する。

### R-008: Optional capability の実装手順が型安全性の観点で不足している

**重大度**: 軽微  
**対象**:

- `RUNTIME_AND_IO_PORTS.md:520-535`
- `RUNTIME_AND_IO_PORTS.md:580-603`

**問題**:

`ControllerOutputPort` は基本契約と optional capability を分け、`touch*()` と `disable_sleep()` は capability の有無を検査するとしている。しかし `TouchInputCapability` / `SleepControlCapability` を `Protocol` にするのか、ABC にするのか、`isinstance()` 可能な `@runtime_checkable` Protocol にするのかが記載されていない。

**修正案**:

`TouchInputCapability` と `SleepControlCapability` の Python シグネチャを追加し、`CommandFacade.touch*()` がどの型判定で `NotImplementedError` を送出するかをコード例で示す。

### R-009: Resource I/O の互換モードが残りすぎている

**重大度**: 重大  
**対象**:

- `RESOURCE_FILE_IO.md:78-84`
- `RESOURCE_FILE_IO.md:107-126`
- `RESOURCE_FILE_IO.md:130-136`
- `RESOURCE_FILE_IO.md:292-318`

**問題**:

Resource I/O 仕様は標準モデルを `resources\<macro_id>\assets` / `runs\<run_id>\outputs` としつつ、`static\<macro_name>` を read path と write path の両方で互換維持している。さらに `legacy_static_write=True`、`resource.write_mode = "legacy_static"`、`filename` 先頭が macro ID の場合の prefix 除去など、複数の互換分岐が残っている。

リソースパスの再設計では、旧配置互換を厚く残すほど `cmd.save_img()` の保存先が実行オプションに依存し、ログ・GUI 表示・成果物管理・テスト fixture の期待値が増える。ユーザー見解として、リソースパスは破壊的変更を許容し、マクロ側修正で吸収する。

**修正案**:

Resource I/O 仕様から write 側の legacy 互換を削除する。`cmd.save_img()` と新 `RunArtifactStore.save_image()` は常に `runs\<run_id>\outputs` に保存する。`legacy_static_write`、`resource.write_mode = "legacy_static"`、`LegacyStaticResourceStore` の write 経路、prefix 除去の互換分岐は削除する。

read 側も `static\<macro_name>` fallback を残すかどうかを再判断する。移行を単純化するなら `resources\<macro_id>\assets` と `macros\<macro_id>\assets` だけを許可し、既存 `static` assets はマクロ修正と同時に移動する。

### R-010: settings lookup の legacy / cwd fallback は Resource I/O とは別に棚卸しが必要である

**重大度**: 中  
**対象**:

- `MACRO_COMPATIBILITY_AND_REGISTRY.md:121-132`
- `CONFIGURATION_AND_RESOURCES.md:220-231`
- `DEPRECATION_AND_MIGRATION.md:175`, `DEPRECATION_AND_MIGRATION.md:188-195`

**問題**:

`static\<macro_name>\settings.toml` lookup と `Path.cwd()\static\<macro_name>\settings.toml` fallback が互換対象として残っている。これは画像リソース I/O とは責務が分離されているが、ユーザーから見ると同じ `static` 旧配置であり、Resource I/O だけを破壊的変更にしても settings 側に legacy static が残る。

特に `cwd` fallback は実行場所に依存し、GUI/CLI、テスト、インストール後実行で挙動が変わりやすい。

**修正案**:

settings についても破壊的変更を許容する。`Path.cwd()` fallback は削除し、`project_root` 明示と manifest settings path に寄せる。`static\<macro_name>\settings.toml` 互換も削除候補とし、既存マクロは manifest または新 settings 配置へ移行する。移行期間中に自動 fallback を残すのではなく、移行ガイドと検出エラーで修正箇所を明示する。

### R-011: `DefaultCommand` 旧コンストラクタ互換が Builder 経由への移行を弱めている

**重大度**: 中  
**対象**:

- `RUNTIME_AND_IO_PORTS.md:170-177`
- `RUNTIME_AND_IO_PORTS.md:599`
- `TEST_STRATEGY.md:107-110`

**問題**:

`DefaultCommand` は旧形式 `DefaultCommand(serial_device=..., capture_device=..., resource_io=..., protocol=..., ct=..., notification_handler=...)` を移行後 1 minor 以上 `DeprecationWarning` なしで維持するとされている。一方で、再設計の主目的は GUI/CLI の個別 `DefaultCommand` 構築をやめ、`MacroRuntimeBuilder.build()` を入口にすることである。

旧コンストラクタを警告なしで維持すると、Builder を迂回して一時 `ExecutionContext` を組み立てる経路が残る。Resource I/O の破壊的変更を許容する方針とも相性が悪い。

**修正案**:

既存マクロは GUI/CLI 経路から生成された `DefaultCommand` を受け取る前提であり、`DefaultCommand` を直接生成しない。旧コンストラクタ互換は公開互換契約から外し、`DefaultCommand(context=...)` または `CommandFacade(context)` だけを新経路として定義する。GUI/CLI とテストは同じ移行単位で `MacroRuntimeBuilder` 経由へ移し、旧形式 `DefaultCommand(serial_device=..., capture_device=...)` は残さない。

### R-012: legacy macro loader の互換範囲を明示的に決める必要がある

**重大度**: 中  
**対象**:

- `TEST_STRATEGY.md:62-64`
- `MACRO_COMPATIBILITY_AND_REGISTRY.md:127-132`
- `DEPRECATION_AND_MIGRATION.md:176`

**問題**:

仕様上は legacy package / legacy single-file macro fixture と scoped `sys.path` 管理が残っている。現リポジトリにも `macros\sample_turbo_a_macro.py` と `macros\test_ocr_init.py` の single-file 形式が存在するため、これを残すか、パッケージ形式へ移行して単純化するかを決める必要がある。

リソースパスの破壊的変更を許容するなら、マクロ配置形式も同時に移行対象へ入れられる可能性がある。

**修正案**:

single-file での実行自体は許容してよい。ただし、legacy single-file 自動探索や `sys.path` を調整して旧形式を拾う互換対応は破棄する。single-file macro を残す場合は、manifest / registry に明示された entrypoint として扱い、通常の `MacroDefinition` 生成経路に乗せる。`legacy_single_file` fixture は「旧形式互換」ではなく「明示 entrypoint の single-file macro」fixture へ改名する。

### R-013: マクロ移行ガイド仕様書を別途作成する必要がある

**重大度**: 中  
**対象**:

- `RESOURCE_FILE_IO.md`
- `CONFIGURATION_AND_RESOURCES.md`
- `MACRO_COMPATIBILITY_AND_REGISTRY.md`
- `DEPRECATION_AND_MIGRATION.md`

**問題**:

Resource I/O、settings lookup、`DefaultCommand` 旧コンストラクタ、legacy loader の互換を削る方針により、既存マクロ側の修正が必要になる。再設計仕様書だけでは、マクロ作者が「どのファイルをどう直すか」を追いにくい。

**修正案**:

移行ガイド仕様書を別途作成する。配置候補は `spec\framework\rearchitecture\MACRO_MIGRATION_GUIDE.md` とする。最低限、次を含める。

| セクション | 内容 |
|------------|------|
| 破壊的変更一覧 | `static` リソース、settings lookup、single-file entrypoint、`DefaultCommand` 直接生成の扱い |
| 移行前後の配置例 | `static\<macro_name>` から `resources\<macro_id>\assets` / manifest settings への移動例 |
| マクロコード修正例 | `cmd.load_img()` / `cmd.save_img()` の path 指定、settings 参照、manifest 追加 |
| 検出エラーと対処 | 旧配置・旧 entrypoint・root 外 path を検出したときのエラーコードと修正方法 |
| 移行チェックリスト | 既存マクロごとの確認項目と関連テスト |

## 3. 優先対応順

| 優先度 | 対応内容 | 対象コメント |
|--------|----------|--------------|
| P0 | `RunResult`、`ExecutionContext`、Resource Port の正本を確定し、重複定義を参照へ置き換える | R-001, R-002, R-003 |
| P0 | Resource I/O の legacy write / read 互換を削る範囲を確定する | R-009 |
| P1 | settings resolver と macro 識別子のフィールド対応表を作る | R-004, R-005 |
| P1 | settings lookup、`DefaultCommand` 旧コンストラクタ、legacy macro loader の互換削除方針を各仕様へ反映する | R-010, R-011, R-012 |
| P1 | マクロ移行ガイド仕様書を作成する | R-013 |
| P1 | 廃止ゲートのテスト名・ファイル名を同期する | R-006 |
| P2 | GUI ログ移行と optional capability の実装手順を補足する | R-007, R-008 |

## 4. 形式面の確認結果

| 確認項目 | 結果 |
|----------|------|
| 必須 6 セクション | 全 12 ファイルで存在 |
| 用語定義の表形式 | 主要文書で表形式を使用 |
| 対象ファイル表 | 主要文書で存在。ただし重複定義の正本は要整理 |
| テスト方針 | unit / integration / GUI / hardware / perf が広く記載され、実機テストは `@pytest.mark.realdevice` を含む |
| 依存方向 | core から GUI/CLI へ依存しない方針は記述済み |
