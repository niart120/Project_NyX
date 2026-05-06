# 設定とリソース境界再設計 仕様書

> **対象モジュール**: `src\nyxpy\framework\core\settings\`, `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\runtime\`  
> **目的**: 通常設定、秘密設定、マクロ設定 lookup の境界を分離し、画像・ファイル I/O の詳細を Resource File I/O 仕様へ独立させる。  
> **関連ドキュメント**: `spec\framework\rearchitecture\FW_REARCHITECTURE_OVERVIEW.md`, `spec\framework\rearchitecture\MACRO_COMPATIBILITY_AND_REGISTRY.md`, `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md`, `spec\framework\rearchitecture\RESOURCE_FILE_IO.md`, `spec\framework\rearchitecture\ERROR_CANCELLATION_LOGGING.md`  
> **破壊的変更**: なし。`static\<macro_name>\settings.toml` と既存 `Command.save_img()` / `Command.load_img()` 呼び出しを維持する。

## 1. 概要

### 1.1 目的

設定永続化と settings lookup を、`GlobalSettings`、`SecretsSettings`、`MacroSettingsResolver` の責務へ分割する。画像、テンプレート、CSV、デバッグ成果物などのファイル I/O は `RESOURCE_FILE_IO.md` で扱い、本書は設定境界と Resource File I/O への接続点だけを定義する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| GlobalSettings | デバイス選択、ログレベル、Runtime 既定値など、秘密値を含まない通常設定を永続化する設定コンポーネント |
| SecretsSettings | Discord webhook、Bluesky password など、ログ表示や通常設定への複製を禁止する秘密設定を永続化するコンポーネント |
| SettingsSchema | 設定キー、型、既定値、検証規則、秘密値フラグを表す schema 定義 |
| MacroSettingsResolver | `macro.toml` の settings 指定と `static\<macro_name>\settings.toml` 互換を解決し、マクロ実行引数へ渡す辞書を作るコンポーネント |
| Resource File I/O | assets 読み込みと outputs 書き込みを扱う別建て仕様。詳細は `RESOURCE_FILE_IO.md` に従う |
| MacroRuntimeBuilder | GUI/CLI/Legacy 入口から設定を読み、Runtime、Ports、Resource scope を組み立てる adapter |
| ConfigurationError | 設定ファイル破損、schema 不一致、秘密設定の誤用など、実行前に検出できる不備を表す例外 |
| SecretBoundaryError | secret 値が通常設定、例外、ログ、GUI 表示イベントへ漏れる構成を検出したことを表す例外 |

### 1.3 背景・問題

現行 `load_macro_settings()` は `Path.cwd()\static\<macro_name>\settings.toml` を暗黙に読む。これは既存互換として維持する必要があるが、画像入出力も `static` 配下にあるため、settings lookup と resource file I/O の境界が曖昧になっていた。

再設計では、settings TOML の探索、TOML parse、schema 検証、secret 境界を本書で扱う。`cmd.load_img()`、`cmd.save_img()`、assets / outputs 配置、path traversal 防止、atomic write は `RESOURCE_FILE_IO.md` を正とする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 設定 schema 検証 | TOML パース後の型不一致が実行時まで残り得る | Runtime 起動前に `ConfigurationError` として検出 |
| 秘密値の保存境界 | CLI/GUI/通知 adapter で参照経路が分散し得る | secret 値は `SecretsSettings` にだけ保持し、通常設定へ複製しない |
| マクロ settings lookup | 画像リソース I/O と同じ `static` 文脈で扱われる | `MacroSettingsResolver` が settings だけを担当 |
| `static\<macro_name>\settings.toml` 互換 | 暗黙維持 | 互換契約として固定し、manifest 指定がない場合の探索候補にする |
| Resource File I/O の詳細 | 本書と Runtime 仕様に重複 | `RESOURCE_FILE_IO.md` へ集約 |
| 既存マクロ変更数 | 変更不可 | 0 件 |

### 1.5 着手条件

- 既存 `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` の import 互換を維持する。`MacroExecutor` は既存マクロ互換 API ではなく、一時 adapter または廃止候補として扱う。
- `static\<macro_name>\settings.toml` は削除せず、legacy settings の標準探索先として扱う。
- `SecretsSettings` に保存される値は INFO 以上のログ、GUI 表示イベント、例外メッセージへ平文で出さない。
- Resource File I/O の実装詳細は `RESOURCE_FILE_IO.md` を参照し、本書へ再定義しない。
- 実装着手前に `uv run pytest tests\unit\` のベースラインを確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\framework\rearchitecture\CONFIGURATION_AND_RESOURCES.md` | 変更 | settings 境界仕様として整理し、ファイル I/O 詳細を `RESOURCE_FILE_IO.md` へ移動 |
| `spec\framework\rearchitecture\RESOURCE_FILE_IO.md` | 新規 | assets / outputs 配置、Resource Store、artifact 保存仕様を定義 |
| `src\nyxpy\framework\core\settings\schema.py` | 新規 | `SettingsSchema`, `SettingField`, schema 検証結果を定義 |
| `src\nyxpy\framework\core\settings\global_settings.py` | 変更 | `GlobalSettings` schema、既定値、型検証、破損 TOML 保護を実装 |
| `src\nyxpy\framework\core\settings\secrets_settings.py` | 変更 | `SecretsSettings` schema、秘密値マスク、通知設定の正配置を実装 |
| `src\nyxpy\framework\core\macro\settings_resolver.py` | 新規 | `MacroSettingsResolver` と manifest / legacy settings 解決を実装 |
| `src\nyxpy\framework\core\utils\helper.py` | 変更 | `load_macro_settings()` を `MacroSettingsResolver` へ接続 |
| `src\nyxpy\framework\core\runtime\builder.py` | 新規 | `GlobalSettings`、`SecretsSettings`、`MacroSettingsResolver` から Runtime 入力を構築 |
| `tests\unit\settings\test_settings_schema.py` | 新規 | 通常設定と秘密設定の schema 検証を確認 |
| `tests\unit\macro\test_settings_resolver.py` | 新規 | manifest settings と legacy settings の解決を確認 |
| `tests\integration\test_configuration_runtime.py` | 新規 | Runtime builder と既存マクロ設定の結合を確認 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

設定境界は Runtime 実行前の構成処理に属する。`GlobalSettings` と `SecretsSettings` は永続化、`MacroSettingsResolver` はマクロ引数の初期値解決、Resource File I/O は実行中の assets / outputs 操作を担当する。

```text
nyxpy.gui / nyxpy.cli
  -> MacroRuntimeBuilder
  -> GlobalSettings / SecretsSettings
  -> MacroSettingsResolver
  -> MacroRuntime
  -> Resource File I/O
```

フレームワーク層から GUI/CLI へ依存しない。個別マクロを動的に読むことは許可するが、個別マクロの名前へ静的依存しない。

### 公開 API 方針

`MacroSettingsResolver` は settings TOML の探索と読み込みだけを公開 API とする。`Command.save_img()` / `Command.load_img()` は `RESOURCE_FILE_IO.md` の互換 API とし、本書では settings lookup と混同しないことだけを契約にする。

`GlobalSettings` と `SecretsSettings` は schema 検証 API を公開する。既存の load/save API がある場合は戻り値と呼び出し名を維持し、内部で schema を適用する。秘密値は mask 関数を通してログへ渡す。

### 後方互換性

`static\<macro_name>\settings.toml` は互換契約である。`macro.toml` が settings path を明示した場合は manifest を優先し、明示がない場合は `project_root\static\<macro_name>\settings.toml` を探索する。`Path.cwd()` 由来の fallback は段階互換として残せるが、構造化ログに非推奨警告を出す。

既存 settings TOML に schema 外キーがある場合は保持する。型不一致は自動補正しない。ただし安全な範囲の文字列から数値への変換は設定ごとに明示した場合だけ許可する。

### レイヤー構成

| レイヤー | 所有する責務 | 依存してよい先 |
|----------|--------------|----------------|
| settings | 通常設定、秘密設定、schema 検証、永続化 | 標準ライブラリ、TOML reader、`ConfigurationError` |
| macro settings | manifest / legacy settings の解決と辞書化 | settings schema、`MacroDescriptor` |
| runtime builder | GUI/CLI/Legacy 入口の設定を Runtime 入力へ変換 | settings、macro、runtime、resource scope factory |
| resource file io | assets 読み込み、outputs 保存、path guard、atomic write | `RESOURCE_FILE_IO.md` の範囲 |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `GlobalSettings` / `SecretsSettings` schema 検証 | 100 キーで 50 ms 未満 |
| `MacroSettingsResolver.resolve()` | manifest なし legacy path で 10 ms 未満 |
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
from typing import Any, Mapping


@dataclass(frozen=True)
class SettingField:
    name: str
    type_: type | tuple[type, ...]
    default: object
    secret: bool = False
    required: bool = False
    choices: tuple[object, ...] | None = None


@dataclass(frozen=True)
class SettingsSchema:
    fields: Mapping[str, SettingField]
    preserve_unknown: bool = True

    def validate(self, data: Mapping[str, Any]) -> dict[str, Any]: ...
    def defaults(self) -> dict[str, Any]: ...
    def mask(self, data: Mapping[str, Any]) -> dict[str, Any]: ...


class GlobalSettings:
    schema: SettingsSchema

    def load(self) -> None: ...
    def save(self) -> None: ...
    def snapshot(self) -> Mapping[str, Any]: ...
    def validate(self) -> None: ...


class SecretsSettings:
    schema: SettingsSchema

    def load(self) -> None: ...
    def save(self) -> None: ...
    def snapshot_masked(self) -> Mapping[str, Any]: ...
    def get_secret(self, key: str) -> str: ...
    def validate(self) -> None: ...


@dataclass(frozen=True)
class MacroSettingsSource:
    path: Path
    legacy: bool
    source: str


class MacroSettingsResolver:
    def __init__(self, project_root: Path) -> None: ...
    def resolve(self, descriptor: MacroDescriptor) -> MacroSettingsSource | None: ...
    def load(self, descriptor: MacroDescriptor) -> dict[str, Any]: ...
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
| `macro.toml [macro].settings` | `str | None` | `None` | manifest opt-in 時の settings path。未指定なら legacy lookup |

### 内部設計

#### GlobalSettings / SecretsSettings schema

schema は dotted key を受け付け、TOML 読み込み後の辞書に対して既定値適用と型検証を行う。`GlobalSettings` は secret flag を持つ field を禁止する。`SecretsSettings` は通知 secret を保持し、Runtime builder は通知 adapter へ secret 値を渡す直前だけ平文を取り出す。

```text
load()
  -> TOML parse
  -> schema.defaults() を merge
  -> schema.validate()
  -> unknown keys を preserve_unknown=True なら保持
  -> immutable snapshot を更新
```

TOML 破損時は元ファイルを上書きしない。save は一時ファイルと置換を使う実装を許可するが、作業ファイルは設定ファイルと同じディレクトリに置く。

#### MacroSettingsResolver

解決順序は次の通りである。

| 優先度 | 条件 | 解決先 |
|--------|------|--------|
| 1 | manifest に `settings` があり、`static\...` で始まる | `project_root` 相対 |
| 2 | manifest に `settings` があり、相対パスで始まる | manifest を置いた macro root 相対 |
| 3 | manifest 指定なし | `project_root\static\<macro_name>\settings.toml` |
| 4 | 段階互換 fallback が有効 | `Path.cwd()\static\<macro_name>\settings.toml` |

絶対パス、空 path、`..` による root 外参照、解決後に許可 root 外へ出るシンボリックリンクは `ConfigurationError` とする。settings ファイルが存在しない場合は既存互換のため空辞書を返す。ただし manifest で将来 required flag を導入した場合は `ConfigurationError` とする。

#### Resource File I/O との接続

Runtime builder は `MacroSettingsResolver` で settings を読み込んだ後、同じ `MacroDescriptor` から `MacroResourceScope` を生成する。settings lookup の結果は `exec_args` に入り、Resource File I/O の scope には入らない。

`Command.save_img()` / `load_img()` の仕様、`resources\<macro_id>\assets` と `runs\<run_id>\outputs` の標準配置、legacy static write、path traversal 防止、atomic write は `RESOURCE_FILE_IO.md` を参照する。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | schema 型不一致、TOML 破損、manifest settings path 不正、secret 値の通常設定混入 |
| `SecretBoundaryError` | `GlobalSettings` へ secret field を定義、または Runtime builder が `SecretsSettings` 以外から secret 値を受け取った |
| `MacroSettingsPathError` | settings path が空、絶対パス、root 外参照、root 外シンボリックリンクである |

Resource File I/O の `ResourcePathError`、`ResourceReadError`、`ResourceWriteError` は `RESOURCE_FILE_IO.md` で定義する。例外メッセージには secret 値を含めない。パスは `project_root` からの相対表示を優先する。

### シングルトン管理

既存 `singletons.py` の `global_settings` と `secrets_settings` は互換のため維持する。`SettingsSchema` と `MacroSettingsResolver` はシングルトンにしない。`reset_for_testing()` は `global_settings`、`secrets_settings` の snapshot と lock 状態を初期化できるようにする。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_global_settings_schema_applies_defaults` | 通常設定の既定値が schema から適用される |
| ユニット | `test_global_settings_rejects_secret_fields` | `GlobalSettings` に secret field を定義できない |
| ユニット | `test_global_settings_rejects_type_mismatch` | 型不一致を `ConfigurationError` にする |
| ユニット | `test_secrets_settings_masks_values` | webhook URL と password がログ用 snapshot でマスクされる |
| ユニット | `test_secrets_settings_preserves_unknown_keys` | 既存ファイルの schema 外キーを保持する |
| ユニット | `test_macro_settings_resolver_uses_manifest_static_path` | manifest の `static\...` settings を `project_root` 相対で解決する |
| ユニット | `test_macro_settings_resolver_uses_macro_root_relative_path` | manifest の相対 settings を macro root 相対で解決する |
| ユニット | `test_macro_settings_resolver_legacy_static_settings` | `static\<macro_name>\settings.toml` を互換 settings として読み込む |
| ユニット | `test_macro_settings_resolver_rejects_path_escape` | `..` と絶対パスを `ConfigurationError` にする |
| ユニット | `test_macro_settings_resolver_is_separate_from_resource_store` | settings lookup が Resource Store を参照しない |
| 結合 | `test_runtime_builder_uses_secrets_settings_for_notifications` | 通知 secret が `SecretsSettings` からのみ adapter へ渡る |
| 結合 | `test_existing_macro_settings_load_without_macro_changes` | 代表既存マクロの settings が変更なしで読み込まれる |
| パフォーマンス | `test_settings_schema_validation_perf` | 100 キー検証が 50 ms 未満で完了する |

Resource File I/O の path guard、画像読み書き、atomic write、`cmd.save_img()` / `load_img()` 互換テストは `RESOURCE_FILE_IO.md` のテスト方針を正とする。

## 6. 実装チェックリスト

- [ ] `GlobalSettings` / `SecretsSettings` schema の公開 API を確定
- [ ] 通常設定と秘密設定の境界を Runtime builder に反映
- [ ] `MacroSettingsResolver` を Resource File I/O から分離
- [ ] `static\<macro_name>\settings.toml` 互換を固定
- [ ] manifest settings path の root 検証を実装
- [ ] secret 値を例外、保存ログ、GUI 表示イベントへ平文出力しない
- [ ] Resource File I/O 詳細を `RESOURCE_FILE_IO.md` へ集約
- [ ] ユニットテスト作成・パス
- [ ] 統合テスト作成・パス
- [ ] 既存マクロ変更不要で互換検証
