# 設定とリソース境界再設計 仕様書

> **文書種別**: 仕様書。settings lookup、`MacroSettingsResolver`、通常設定、秘密設定の正本である。Runtime builder の正本は `RUNTIME_AND_IO_PORTS.md`、Resource File I/O の正本は `RESOURCE_FILE_IO.md` に置く。
> **対象モジュール**: `src\nyxpy\framework\core\settings\`, `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\runtime\`  
> **目的**: 通常設定、秘密設定、マクロ設定 lookup の境界を分離し、画像・ファイル I/O の詳細を Resource File I/O 仕様へ独立させる。  
> **関連ドキュメント**: `spec/framework/rearchitecture/FW_REARCHITECTURE_OVERVIEW.md`, `spec/framework/rearchitecture/MACRO_COMPATIBILITY_AND_REGISTRY.md`, `spec/framework/rearchitecture/RUNTIME_AND_IO_PORTS.md`, `spec/framework/rearchitecture/RESOURCE_FILE_IO.md`, `spec/framework/rearchitecture/ERROR_CANCELLATION_LOGGING.md`
> **破壊的変更**: settings lookup の破壊的変更と削除条件は `DEPRECATION_AND_MIGRATION.md` を正とする。本書は `MacroSettingsResolver`、settings schema、secret 境界の詳細だけを定義する。

## 1. 概要

### 1.1 目的

設定永続化と settings lookup を、`SettingsStore`、`SecretsStore`、`MacroSettingsResolver` の責務へ分割する。画像、テンプレート、CSV、デバッグ成果物などのファイル I/O は `RESOURCE_FILE_IO.md` で扱い、本書は設定境界と Resource File I/O への接続点だけを定義する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| SettingsStore | デバイス選択、ログレベル、Runtime 既定値など、秘密値を含まない通常設定を読み書きする起動層の依存 |
| SecretsStore | Discord webhook、Bluesky password など、ログ表示や通常設定への複製を禁止する秘密設定を読み書きする起動層の依存 |
| GlobalSettings / SecretsSettings | 既存互換 shim。新 Runtime 経路では直接参照せず、`SettingsStore` / `SecretsStore` の snapshot を渡す |
| SettingsSchema | 設定キー、型、既定値、検証規則、秘密値フラグを表す schema 定義 |
| MacroSettingsResolver | `macro.toml` または class metadata の settings 指定を解決し、マクロ実行引数へ渡す辞書を作るコンポーネント |
| Resource File I/O | assets 読み込みと outputs 書き込みを扱う別建て仕様。詳細と API は `RESOURCE_FILE_IO.md` に従う |
| MacroRuntimeBuilder | GUI/CLI/Legacy 入口から Runtime、Ports、settings、Resource scope を組み立てる adapter。API と責務の正本は `RUNTIME_AND_IO_PORTS.md` に置く |
| ConfigurationError | 設定ファイル破損、schema 不一致、秘密設定の誤用など、実行前に検出できる不備を表す例外 |
| SecretBoundaryError | secret 値が通常設定、例外、ログ、GUI 表示イベントへ漏れる構成を検出したことを表す例外 |

### 1.3 背景・問題

現行 `load_macro_settings()` は `Path.cwd()\static\<macro_name>\settings.toml` を暗黙に読む。画像入出力も `static` 配下にあるため、settings lookup と resource file I/O の境界が曖昧になっていた。再設計ではこの暗黙探索を残さず、manifest または class metadata の settings source と明示 `project_root` へ移行する。

再設計では、settings TOML の探索、TOML parse、schema 検証、secret 境界を本書で扱う。`cmd.load_img()`、`cmd.save_img()`、assets / outputs 配置、path traversal 防止、atomic write は `RESOURCE_FILE_IO.md` を正とする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 設定 schema 検証 | TOML パース後の型不一致が実行時まで残り得る | Runtime 起動前に `ConfigurationError` として検出 |
| 秘密値の保存境界 | CLI/GUI/通知 adapter で参照経路が分散し得る | secret 値は secrets snapshot にだけ保持し、通常設定へ複製しない |
| マクロ settings lookup | 画像リソース I/O と同じ `static` 文脈で扱われる | `MacroSettingsResolver` が settings だけを担当 |
| `static\<macro_name>\settings.toml` 互換 | 暗黙維持 | 削除し、manifest または class metadata settings source と移行ガイドで置き換える |
| Resource File I/O の詳細 | 本書と Runtime 仕様に重複 | `RESOURCE_FILE_IO.md` へ集約 |
| 既存マクロ変更数 | 変更不可 | 移行ガイドに従って settings 配置を更新 |

### 1.5 着手条件

- 既存 `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` の import 互換を維持する。`MacroExecutor` は既存マクロ互換 API ではなく削除対象として扱う。
- `static\<macro_name>\settings.toml` は標準探索先にしない。必要な settings は manifest または class metadata の settings source へ移行する。
- secrets snapshot に保存される値は INFO 以上のログ、GUI 表示イベント、例外メッセージへ平文で出さない。
- Resource File I/O の実装詳細は `RESOURCE_FILE_IO.md` を参照し、本書へ再定義しない。
- 実装着手前に `uv run pytest tests\unit\` のベースラインを確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/framework/rearchitecture/CONFIGURATION_AND_RESOURCES.md` | 変更 | settings 境界仕様として整理し、ファイル I/O 詳細を `RESOURCE_FILE_IO.md` へ移動 |
| `spec/framework/rearchitecture/RESOURCE_FILE_IO.md` | 新規 | assets / outputs 配置、Resource Store、artifact 保存仕様を定義 |
| `src\nyxpy\framework\core\settings\schema.py` | 新規 | `SettingsSchema`, `SettingField`, schema 検証結果を定義 |
| `src\nyxpy\framework\core\settings\global_settings.py` | 変更 | `SettingsStore` schema、既定値、型検証、破損 TOML 保護を実装。既存クラスは互換 shim に限定 |
| `src\nyxpy\framework\core\settings\secrets_settings.py` | 変更 | `SecretsStore` schema、秘密値マスク、通知設定の正配置を実装。既存クラスは互換 shim に限定 |
| `src\nyxpy\framework\core\macro\settings_resolver.py` | 新規 | `MacroSettingsResolver` と manifest / class metadata settings 解決を実装 |
| `src\nyxpy\framework\core\utils\helper.py` | 変更 | `load_macro_settings()` を `MacroSettingsResolver` へ接続 |
| `src\nyxpy\framework\core\runtime\builder.py` | 新規 | `RUNTIME_AND_IO_PORTS.md` が正本。本書の settings snapshot と `MacroSettingsResolver` を呼び出して Runtime 入力を構築 |
| `tests\unit\framework\settings\test_settings_schema.py` | 新規 | 通常設定と秘密設定の schema 検証を確認 |
| `tests\unit\framework\macro\test_settings_resolver.py` | 新規 | manifest / class metadata settings の解決と旧 fallback 不使用を確認 |
| `tests\integration\test_configuration_runtime.py` | 新規 | Runtime builder と既存マクロ設定の結合を確認 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

設定境界は Runtime 実行前の構成処理に属する。`SettingsStore` と `SecretsStore` は永続化、`MacroSettingsResolver` はマクロ引数の初期値解決、Resource File I/O は実行中の assets / outputs 操作を担当する。`MacroRuntimeBuilder` はこれらを呼び出す側であり、本書は builder の API を再定義しない。

```text
nyxpy.gui / nyxpy.cli
  -> MacroRuntimeBuilder  # RUNTIME_AND_IO_PORTS.md が正本
      -> SettingsStore / SecretsStore
      -> MacroSettingsResolver
      -> Resource File I/O
      -> MacroRuntime
```

フレームワーク層から GUI/CLI へ依存しない。個別マクロを動的に読むことは許可するが、個別マクロの名前へ静的依存しない。

### 公開 API 方針

`MacroSettingsResolver` は settings TOML の探索と読み込みだけを公開 API とする。`Command.save_img()` / `Command.load_img()` は `RESOURCE_FILE_IO.md` の API とし、本書では settings lookup と混同しないことだけを契約にする。

`SettingsStore` と `SecretsStore` は schema 検証 API を公開する。既存 `GlobalSettings` / `SecretsSettings` の load/save API が残る場合は互換 shim とし、内部で store 経路へ委譲する。秘密値は mask 関数を通してログへ渡す。

### 後方互換性

`static\<macro_name>\settings.toml` は互換契約に含めない。manifest または class metadata が settings path を明示した場合だけ macro settings file を読み込む。明示がない場合は `resolve()` が `None`、`load()` が `{}` を返す。`Path.cwd()` 由来の fallback は残さない。

既存 settings TOML に schema 外キーがある場合は保持する。型不一致は自動補正しない。ただし安全な範囲の文字列から数値への変換は設定ごとに明示した場合だけ許可する。

### レイヤー構成

| レイヤー | 所有する責務 | 依存してよい先 |
|----------|--------------|----------------|
| settings | 通常設定、秘密設定、schema 検証、永続化 | 標準ライブラリ、TOML reader、`ConfigurationError` |
| macro settings | manifest / class metadata settings の解決と辞書化 | settings schema、`MacroDefinition` |
| runtime builder | settings snapshot と resolver の結果を Runtime 入力へ変換。API と build 順序は `RUNTIME_AND_IO_PORTS.md` が正本 | settings、macro、runtime、resource scope factory |
| resource file io | assets 読み込み、outputs 保存、path guard、atomic write | `RESOURCE_FILE_IO.md` の範囲 |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `SettingsStore` / `SecretsStore` schema 検証 | 100 キーで 50 ms 未満 |
| `MacroSettingsResolver.resolve()` | manifest / class metadata settings path で 10 ms 未満 |
| `MacroSettingsResolver.load()` | TOML parse を除き 10 ms 未満 |
| secret mask snapshot 生成 | 100 キーで 20 ms 未満 |

### 並行性・スレッド安全性

設定ファイルの load/save はプロセス内 `RLock` で保護する。読み込み済み設定は immutable な snapshot として Runtime builder に渡し、実行中に GUI 設定変更があっても進行中の `ExecutionContext` へ反映しない。

`MacroSettingsResolver` は project root と探索候補を保持するだけの stateless な部品として実装する。ファイル I/O の書き込み競合、atomic write、outputs の per-path lock は `RESOURCE_FILE_IO.md` の責務である。

## 4. 実装仕様

### 公開インターフェース

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


type SettingValue = str | int | float | bool | list[SettingValue] | dict[str, SettingValue] | None


@dataclass(frozen=True)
class SettingField:
    name: str
    type_: type | tuple[type, ...]
    default: SettingValue
    secret: bool = False
    required: bool = False
    choices: tuple[SettingValue, ...] | None = None


@dataclass(frozen=True)
class SettingsSchema:
    fields: Mapping[str, SettingField]
    preserve_unknown: bool = True

    def validate(self, data: Mapping[str, SettingValue]) -> dict[str, SettingValue]: ...
    def defaults(self) -> dict[str, SettingValue]: ...
    def mask(self, data: Mapping[str, SettingValue]) -> dict[str, SettingValue]: ...


class SettingsStore:
    schema: SettingsSchema

    def load(self) -> None: ...
    def save(self) -> None: ...
    def snapshot(self) -> Mapping[str, SettingValue]: ...
    def validate(self) -> None: ...


@dataclass(frozen=True)
class SecretsSnapshot:
    def get_secret(self, key: str) -> str: ...
    def masked(self) -> Mapping[str, SettingValue]: ...


class SecretsStore:
    schema: SettingsSchema

    def load(self) -> None: ...
    def save(self) -> None: ...
    def snapshot(self) -> SecretsSnapshot: ...
    def snapshot_masked(self) -> Mapping[str, SettingValue]: ...
    def get_secret(self, key: str) -> str: ...
    def validate(self) -> None: ...


@dataclass(frozen=True)
class MacroSettingsSource:
    path: Path
    source: str


class MacroSettingsResolver:
    def __init__(self, project_root: Path) -> None: ...
    def resolve(self, definition: MacroDefinition) -> MacroSettingsSource | None: ...
    def load(self, definition: MacroDefinition) -> dict[str, SettingValue]: ...
```

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_device` | `str` | `""` | 通常設定。利用するキャプチャデバイス名 |
| `serial_device` | `str` | `""` | 通常設定。利用するシリアルデバイス名 |
| `serial_baud` | `int` | `9600` | 通常設定。シリアル通信速度 |
| `serial_protocol` | `str` | `"CH552"` | 通常設定。利用するシリアルプロトコル |
| `runtime.allow_dummy` | `bool` | `False` | 通常設定。明示 dummy 実行を許可するか |
| `runtime.frame_ready_timeout_sec` | `float` | `3.0` | 通常設定。初回フレーム待機秒数 |
| `logging.file_level` | `str` | `"DEBUG"` | 通常設定。保存ログの最低レベル |
| `logging.gui_level` | `str` | `"INFO"` | 通常設定。GUI 表示イベントの最低レベル |
| `notification.discord.enabled` | `bool` | `False` | 秘密設定。Discord 通知の有効化 |
| `notification.discord.webhook_url` | `str` | `""` | 秘密設定。ログでは全体をマスクする |
| `notification.bluesky.enabled` | `bool` | `False` | 秘密設定。Bluesky 通知の有効化 |
| `notification.bluesky.identifier` | `str` | `""` | 秘密設定。ログでは一部をマスクする |
| `notification.bluesky.password` | `str` | `""` | 秘密設定。ログでは全体をマスクする |
| `macro.toml [macro].settings` | `str | None` | `None` | manifest で明示する macro settings path。未指定なら class metadata を見る |
| `MacroBase.settings_path` | `str | None` | `None` | manifest がない、または manifest に settings がない場合に class metadata で明示する macro settings path |

### 内部設計

#### SettingsStore / SecretsStore schema

schema は dotted key を受け付け、TOML 読み込み後の辞書に対して既定値適用と型検証を行う。`SettingsStore` は secret flag を持つ field を禁止する。`SecretsStore` は通知 secret を保持し、Runtime builder には immutable な `SecretsSnapshot` を渡す。Runtime builder は通知 adapter へ secret 値を渡す直前だけ `SecretsSnapshot.get_secret()` で平文を取り出す。

```text
load()
  -> TOML parse
  -> schema.defaults() を merge
  -> schema.validate()
  -> unknown keys を preserve_unknown=True なら保持
  -> immutable snapshot を更新
```

TOML 破損時は元ファイルを上書きしない。save は一時ファイルと置換を使う実装を許可するが、作業ファイルは設定ファイルと同じディレクトリに置く。

`SettingsStore` と `SecretsStore` は store ごとに `settings_store_lock` を持ち、`load()`、`save()`、snapshot 交換を直列化する。`snapshot()` は内部辞書への参照ではなく immutable copy を返す。`save()` は lock 内で一時ファイルへ書き込み、同一ディレクトリ内の replace を行ってから snapshot を更新する。複数 Runtime が同じ snapshot を読んでも、実行中に GUI 設定保存が走った場合は既存 context の値を変更せず、次回 build から新 snapshot を使う。

#### secret boundary contract

secret の平文値は `SecretsStore` と Runtime builder の通知 adapter 初期化処理だけが扱う。CLI 引数で webhook URL、password、access token などの secret を受け取る機能は設けない。GUI 設定画面で入力された secret は `SecretsStore` へ保存した後、保存済み secrets snapshot として Runtime builder へ渡す。

| 経路 | 平文 secret | mask 済み値 | 禁止事項 |
|------|-------------|-------------|----------|
| `SecretsStore.snapshot()` | 返さない | `SecretsSnapshot` として保持する | snapshot 自体を log extra、metadata、`exec_args` へ渡さない |
| `SecretsSnapshot.get_secret(key)` | 返してよい。呼び出し元は Runtime builder の通知 adapter 初期化に限定 | なし | 取得値を `exec_args`、通常 settings、metadata、log extra へ複製しない |
| `SecretsSnapshot.masked()` / `SecretsStore.snapshot_masked()` | 返さない | 返してよい | mask 済み snapshot から通知 adapter を初期化しない |
| `MacroRuntimeBuilder` | `NotificationPort` 構築直前だけ参照してよい | logger / diagnostics へ渡してよい | `ExecutionContext` に平文 secret field や `SecretsSnapshot` を持たせない |
| `LoggerPort` / `TechnicalLog` | 受け取らない | `LogSanitizer` を通した値だけ受け取る | 例外 message、traceback 要約、`extra` に secret を平文で入れない |
| `RunResult.error` / `UserEvent` | 受け取らない | 必要最小限の mask 済み要約だけ許可 | GUI/CLI 表示に secret、通知 payload、内部 token を含めない |

通常設定 schema に secret field が定義された場合、または Runtime builder が `SecretsStore` / secrets snapshot 以外の経路から secret 値を受け取った場合は `SecretBoundaryError` とする。secret を含む可能性がある例外 message は `LogSanitizer.mask_text()` 相当を通してから `ErrorInfo.message`、`TechnicalLog.extra`、fallback stderr へ渡す。

`ExecutionContext` は `SecretsSnapshot` と平文 secret field を保持しない。Runtime builder は通知 adapter を構築する瞬間だけ `SecretsSnapshot.get_secret()` を呼び、構築後の `NotificationPort` へ secret を閉じ込める。`SecretsSnapshot` のマルチスレッド読み取りは immutable copy の参照だけで完結し、`get_secret()` は値のコピーを返す。テストでは `test_execution_context_does_not_contain_secrets_snapshot` と `test_secrets_snapshot_is_immutable_during_concurrent_save` でこの不変条件を固定する。

#### MacroSettingsResolver

解決順序は次の通りである。

| 優先度 | 条件 | 解決先 |
|--------|------|--------|
| 1 | manifest に `settings` があり、`project:` prefix で始まる | 明示 `project_root` 相対 |
| 2 | manifest に `settings` があり、相対パスで始まる | manifest を置いた macro root 相対 |
| 3 | class metadata `settings_path` があり、`project:` prefix で始まる | 明示 `project_root` 相対 |
| 4 | class metadata `settings_path` があり、相対パスで始まる | macro root 相対 |
| 5 | manifest / class metadata 指定なし | `None`。macro settings file は読み込まない |

`static\<macro_name>\settings.toml` と `Path.cwd()\static\<macro_name>\settings.toml` は探索しない。絶対パス、空 path、`..` による root 外参照、解決後に許可 root 外へ出るシンボリックリンクは `ConfigurationError` とする。

`MacroSettingsResolver.resolve(definition)` は、有効な明示 settings path が存在する場合に `MacroSettingsSource` を返す。`definition.settings_path` が `Path` の場合は解決済み path として root guard だけを適用し、`str` の場合は `project:` prefix または portable relative path を未解決指定として `project_root` / `definition.macro_root` から解決する。manifest / class metadata 指定が存在しない場合は `None` を返す。不正 path、許可 root 外参照、root 外シンボリックリンク、required flag を導入した場合の未存在は `ConfigurationError` とする。

`MacroSettingsResolver.load(definition)` は `resolve()` が `None` を返した場合に `{}` を返す。settings TOML の parse 失敗、schema 型不一致、secret 境界違反は `ConfigurationError` とし、既定値へ fallback しない。fallback すると実行引数の誤りを成功扱いにするためである。エラー時は `settings.load_failed` の `UserEvent` と `NYX_SETTINGS_PARSE_FAILED` または `NYX_SETTINGS_SCHEMA_INVALID` を含む `TechnicalLog` を出し、Runtime builder は実行を開始しない。

#### Resource File I/O との接続

Runtime builder は `MacroSettingsResolver` で settings を読み込んだ後、同じ `MacroDefinition` から `MacroResourceScope` を生成する。settings lookup の結果は `exec_args` に入り、Resource File I/O の scope には入らない。

`Command.save_img()` / `load_img()` の仕様、`resources\<macro_id>\assets` と `runs\<run_id>\outputs` の標準配置、path traversal 防止、atomic write は `RESOURCE_FILE_IO.md` を参照する。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | schema 型不一致、TOML 破損、明示 settings path 不正、secret 値の通常設定混入 |
| `SecretBoundaryError` | 通常設定へ secret field を定義、Runtime builder が `SecretsStore` / secrets snapshot 以外から secret 値を受け取った、または log / error / metadata へ平文 secret を渡そうとした |
| `ConfigurationError(code="NYX_SETTINGS_PATH_INVALID")` | settings path が空、絶対パス、root 外参照、root 外シンボリックリンクである |

`ConfigurationError.code` は `ERROR_CANCELLATION_LOGGING.md` の Error code catalog を正とする。本書では `NYX_SETTINGS_PARSE_FAILED`、`NYX_SETTINGS_SCHEMA_INVALID`、`NYX_SETTINGS_PATH_INVALID`、`NYX_DEFINE_PARSE_FAILED`、`NYX_DEFINE_INVALID`、`NYX_MACRO_ARGS_INVALID` を参照し、別名を定義しない。

Resource File I/O の `ResourcePathError`、`ResourceReadError`、`ResourceWriteError` は `RESOURCE_FILE_IO.md` で定義する。例外メッセージには secret 値を含めない。パスは `project_root` からの相対表示を優先する。

### シングルトン管理

`SettingsStore`、`SecretsStore`、`SettingsSchema`、`MacroSettingsResolver` はシングルトンにしない。GUI / CLI の composition root が project root を明示して生成し、Runtime には通常設定 snapshot、secrets snapshot、macro settings dict を渡す。既存 `singletons.py` の `global_settings` と `secrets_settings` は互換 shim として段階的に廃止し、新 Runtime 経路では参照しない。device discovery cache、logging、Runtime/Port 実体の扱いは `RUNTIME_AND_IO_PORTS.md` のシングルトン管理表を正とする。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_settings_store_schema_applies_defaults` | 通常設定の既定値が schema から適用される |
| ユニット | `test_settings_store_rejects_secret_fields` | 通常設定に secret field を定義できない |
| ユニット | `test_settings_store_rejects_type_mismatch` | 型不一致を `ConfigurationError` にする |
| ユニット | `test_secrets_store_masks_values` | webhook URL と password がログ用 snapshot でマスクされる |
| ユニット | `test_secrets_store_preserves_unknown_keys` | 既存ファイルの schema 外キーを保持する |
| ユニット | `test_macro_settings_resolver_uses_manifest_project_path` | manifest の `project:` settings を `project_root` 相対で解決する |
| ユニット | `test_macro_settings_resolver_uses_macro_root_relative_path` | manifest の相対 settings を macro root 相対で解決する |
| ユニット | `test_macro_settings_resolver_uses_class_metadata_path` | manifest がない場合に class metadata `settings_path` を解決する |
| ユニット | `test_macro_settings_resolver_rejects_backslash_in_portable_path` | TOML / class metadata の path に `\` が含まれる場合は診断して拒否する |
| ユニット | `test_macro_settings_resolver_does_not_read_legacy_static_settings` | `static\<macro_name>\settings.toml` を暗黙探索しない |
| ユニット | `test_macro_settings_resolver_returns_none_when_absent` | settings 候補が存在しない場合に `resolve()` が `None`、`load()` が `{}` を返す |
| ユニット | `test_macro_settings_resolver_rejects_broken_toml` | TOML parse 失敗時に既定値 fallback せず `ConfigurationError` にする |
| ユニット | `test_macro_settings_resolver_rejects_path_escape` | `..` と絶対パスを `ConfigurationError` にする |
| ユニット | `test_macro_settings_resolver_is_separate_from_resource_store` | settings lookup が Resource Store を参照しない |
| 結合 | `test_cli_notification_settings_source_is_secrets_store` | 通知 secret が secrets snapshot からのみ adapter へ渡る |
| 結合 | `test_file_settings_and_exec_args_are_merged_with_exec_args_precedence` | settings と実行引数が Runtime builder で merge され、実行引数が優先される |
| 性能 | `test_settings_schema_validation_perf` | 100 キー検証が 50 ms 未満で完了する |

Resource File I/O の path guard、画像読み書き、atomic write、`cmd.save_img()` / `load_img()` テストは `RESOURCE_FILE_IO.md` のテスト方針を正とする。

## 6. 実装チェックリスト

- [ ] `SettingsStore` / `SecretsStore` schema の公開 API を確定
- [ ] 通常設定と秘密設定の境界を Runtime builder に反映
- [ ] `MacroSettingsResolver` を Resource File I/O から分離
- [ ] `static\<macro_name>\settings.toml` と `Path.cwd()` fallback を削除
- [ ] manifest / class metadata settings path の root 検証を実装
- [ ] secret 値を例外、保存ログ、GUI 表示イベントへ平文出力しない
- [ ] Resource File I/O 詳細を `RESOURCE_FILE_IO.md` へ集約
- [ ] ユニットテスト作成・パス
- [ ] 統合テスト作成・パス
- [ ] 移行後マクロの明示 settings source を検証
