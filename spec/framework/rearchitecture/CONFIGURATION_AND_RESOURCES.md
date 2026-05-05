# 設定とリソース境界再設計 仕様書

> **対象モジュール**: `src\nyxpy\framework\core\settings\`, `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\hardware\`
> **目的**: 通常設定、秘密設定、マクロ設定、画像リソース入出力の境界を分離し、既存マクロを変更せずに設定検証と安全なリソースアクセスを実現する。
> **関連ドキュメント**: `spec\framework\rearchitecture\FW_REARCHITECTURE_OVERVIEW.md`, `spec\framework\rearchitecture\MACRO_COMPATIBILITY_AND_REGISTRY.md`, `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md`, `spec\framework\rearchitecture\ERROR_CANCELLATION_LOGGING.md`
> **破壊的変更**: なし。`static\<macro_name>\settings.toml` と既存 `Command.save_img()` / `Command.load_img()` 呼び出しを維持する。

## 1. 概要

### 1.1 目的

設定永続化とリソース入出力を、`GlobalSettings`、`SecretsSettings`、`MacroSettingsResolver`、`ResourceStorePort` の責務へ分割する。既存マクロの設定ファイル配置と `Command` API を保ちながら、型検証、秘密値マスク、パス脱出防止、画像書き込み失敗検出をフレームワーク側で保証する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| GlobalSettings | デバイス選択、ログレベル、Runtime 既定値など、秘密値を含まない通常設定を永続化する設定コンポーネント |
| SecretsSettings | Discord webhook、Bluesky password など、ログ表示や通常設定への複製を禁止する秘密設定を永続化する設定コンポーネント |
| SettingsSchema | 設定キー、型、既定値、検証規則、秘密値フラグを表す schema 定義 |
| MacroSettingsResolver | `macro.toml` の settings 指定と `static\<macro_name>\settings.toml` 互換を解決し、マクロ実行引数へ渡す辞書を作るコンポーネント |
| ResourceStorePort | 画像保存・画像読み込みを担当する Port。settings TOML の解決は担当しない |
| StaticResourceStorePort | `ResourceStorePort` の標準実装。static root 配下だけを読み書きし、OpenCV の読み書き結果を検証する |
| ResourcePathGuard | `Path.resolve()` 後の root 配下判定により、絶対パス、`..`、シンボリックリンク経由の root 外参照を拒否する内部部品 |
| Command | マクロが画像保存、画像読み込み、ログ、通知、デバイス操作を行う高レベル API |
| MacroRuntimeBuilder | GUI/CLI/Legacy 入口から設定を読み、Runtime と Ports を組み立てる adapter |
| ConfigurationError | 設定ファイル破損、schema 不一致、秘密設定の誤用など、実行前に検出できる不備を表す例外 |
| ResourceError | リソースパス不正、画像読み込み失敗、画像書き込み失敗など、静的リソース操作の失敗を表す例外 |

### 1.3 背景・問題

既存仕様では Runtime と Port の分離、異常系の正規化、マクロ互換は定義済みである。一方で、通常設定と秘密設定の schema、`MacroSettingsResolver` と `ResourceStorePort` の境界、`static\<macro_name>\settings.toml` 互換の扱い、リソースパス検証、`cv2.imwrite()` 失敗検出は補足的に扱われていた。

現行互換を優先するため、既存マクロが `static\<macro_name>\settings.toml` を前提にしている事実は変更しない。抜本改修の対象はフレームワーク内部の設定読み込み、検証、Port adapter、Runtime builder に限定する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 設定 schema 検証 | TOML パース後の型不一致が実行時まで残り得る | Runtime 起動前に `ConfigurationError` として検出 |
| 秘密値の保存境界 | CLI/GUI/通知 adapter で参照経路が分散し得る | secret 値は `SecretsSettings` にだけ保持し、通常設定へ複製しない |
| マクロ設定解決 | 画像リソース I/O と settings 解決が混同されやすい | `MacroSettingsResolver` が設定、`ResourceStorePort` が画像を担当 |
| `static\<macro_name>\settings.toml` 互換 | 暗黙維持 | 互換契約として固定し、manifest 指定がない場合の第一候補にする |
| resource path escape | root 外参照の検証が弱い | `resolve()` 後に static root 配下だけ許可 |
| `cv2.imwrite()` 失敗 | 戻り値未検証で成功扱いになり得る | `False` と保存後未存在を `ResourceWriteError` にする |
| 既存マクロ変更数 | 変更不可 | 0 件 |

### 1.5 着手条件

- 既存 `MacroBase` / `Command` / `MacroExecutor` の import 互換を維持する。
- `static\<macro_name>\settings.toml` は削除せず、legacy settings の標準探索先として扱う。
- `SecretsSettings` に保存される値は INFO 以上のログ、GUI 表示イベント、例外メッセージへ平文で出さない。
- 実装着手前に `uv run pytest tests\unit\` のベースラインを確認する。
- 既存マクロ本体の編集を要求しない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\framework\rearchitecture\CONFIGURATION_AND_RESOURCES.md` | 新規 | 本仕様書 |
| `src\nyxpy\framework\core\settings\schema.py` | 新規 | `SettingsSchema`, `SettingField`, schema 検証結果を定義 |
| `src\nyxpy\framework\core\settings\global_settings.py` | 変更 | `GlobalSettings` schema、既定値、型検証、破損 TOML 保護を実装 |
| `src\nyxpy\framework\core\settings\secrets_settings.py` | 変更 | `SecretsSettings` schema、秘密値マスク、通知設定の正配置を実装 |
| `src\nyxpy\framework\core\macro\settings_resolver.py` | 新規 | `MacroSettingsResolver` と manifest / legacy settings 解決を実装 |
| `src\nyxpy\framework\core\io\resources.py` | 新規 | `ResourceStorePort`, `StaticResourceStorePort`, `ResourcePathGuard` を実装 |
| `src\nyxpy\framework\core\hardware\resource.py` | 変更 | 既存 `StaticResourceIO` を互換 adapter とし、新 resource store へ委譲 |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | `save_img()` / `load_img()` を `ResourceStorePort` へ委譲し、既存シグネチャを維持 |
| `src\nyxpy\framework\core\runtime\builder.py` | 新規 | `GlobalSettings` と `SecretsSettings` から Runtime / Ports を組み立てる |
| `tests\unit\settings\test_settings_schema.py` | 新規 | 通常設定と秘密設定の schema 検証を確認 |
| `tests\unit\macro\test_settings_resolver.py` | 新規 | manifest settings と legacy settings の解決を確認 |
| `tests\unit\io\test_resource_store.py` | 新規 | パス脱出防止、画像読み書き失敗、OpenCV 戻り値検証を確認 |
| `tests\integration\test_configuration_resource_runtime.py` | 新規 | Runtime builder と既存マクロ設定の結合を確認 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

設定とリソースは Runtime 実行前の構成処理と、実行中に `Command` が使う I/O 境界に分かれる。`GlobalSettings` と `SecretsSettings` は永続化、`MacroSettingsResolver` はマクロ引数の初期値解決、`ResourceStorePort` は画像リソース I/O を担当する。

```text
nyxpy.gui / nyxpy.cli
  -> MacroRuntimeBuilder
  -> GlobalSettings / SecretsSettings
  -> MacroRuntime
  -> CommandFacade
  -> ResourceStorePort

MacroRegistry
  -> MacroSettingsResolver
  -> static\<macro_name>\settings.toml
```

フレームワーク層から GUI/CLI へ依存しない。個別マクロを import 対象として動的に読むことは許可するが、個別マクロの名前へ静的依存しない。

### 公開 API 方針

既存マクロ向けの `Command.save_img(filename, image)` と `Command.load_img(filename, grayscale=False)` は変更しない。新規 API は Runtime builder、settings schema、resource store に追加し、既存呼び出しは adapter 経由で新実装へ委譲する。

`GlobalSettings` と `SecretsSettings` は schema 検証 API を公開する。既存の load/save API がある場合は戻り値と呼び出し名を維持し、内部で schema を適用する。秘密値は `SecretValue` 相当の wrapper または mask 関数を通してログへ渡す。

### 後方互換性

`static\<macro_name>\settings.toml` は互換契約である。`macro.toml` が settings path を明示した場合は manifest を優先し、明示がない場合は `project_root\static\<macro_name>\settings.toml` を第一候補にする。`Path.cwd()` 由来の fallback は段階互換として残せるが、構造化ログに非推奨警告を出す。

既存 settings TOML に schema 外キーがある場合は保持する。型不一致は自動補正しない。ただし安全な範囲の文字列から数値への変換は設定ごとに明示した場合だけ許可する。

### レイヤー構成

| レイヤー | 所有する責務 | 依存してよい先 |
|----------|--------------|----------------|
| settings | 通常設定、秘密設定、schema 検証、永続化 | 標準ライブラリ、TOML reader、`ConfigurationError` |
| macro settings | manifest / legacy settings の解決と辞書化 | settings schema、`MacroDescriptor` |
| resource port | 画像リソースのパス検証、読み書き、OpenCV 結果検証 | OpenCV、`ResourceError` |
| runtime builder | GUI/CLI/Legacy 入口の設定を Runtime Ports へ変換 | settings、macro、io、hardware |
| command facade | 既存 `Command` API を Port へ委譲 | Runtime context、Ports |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `GlobalSettings` / `SecretsSettings` schema 検証 | 100 キーで 50 ms 未満 |
| `MacroSettingsResolver.resolve()` | manifest なし legacy path で 10 ms 未満 |
| `ResourcePathGuard.resolve()` | 1 パスあたり 2 ms 未満 |
| `ResourceStorePort.save_image()` の追加検証コスト | `cv2.imwrite()` 実行時間を除き 5 ms 未満 |

### 並行性・スレッド安全性

設定ファイルの load/save はプロセス内 `RLock` で保護する。読み込み済み設定は immutable な snapshot として Runtime builder に渡し、実行中に GUI 設定変更があっても進行中の `ExecutionContext` へ反映しない。

`ResourceStorePort` は root path と OpenCV 呼び出しだけを保持するため、原則として stateless に近い。複数スレッドが同じファイル名へ同時保存する場合の内容競合は呼び出し側の責務とし、Port は path escape と書き込み失敗検出を保証する。

## 4. 実装仕様

### 公開インターフェース

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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


class ResourceStorePort(ABC):
    @abstractmethod
    def resolve_resource_path(self, filename: str | Path) -> Path: ...

    @abstractmethod
    def save_image(self, filename: str | Path, image: Any) -> None: ...

    @abstractmethod
    def load_image(self, filename: str | Path, grayscale: bool = False) -> Any: ...

    def close(self) -> None: ...


class StaticResourceStorePort(ResourceStorePort):
    def __init__(self, root: Path) -> None: ...
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
| `resource.static_root` | `Path | None` | `project_root\static` | `ResourceStorePort` が許可する root |

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

絶対パス、空 path、`..` による root 外参照、解決後に許可 root 外へ出るシンボリックリンクは `ConfigurationError` とする。settings ファイルが存在しない場合は既存互換のため空辞書を返す。ただし manifest で将来 `required=true` を導入した場合は `ConfigurationError` とする。

#### ResourceStorePort

`StaticResourceStorePort.resolve_resource_path()` は以下を満たす。

1. `filename` は `str | Path` であり、空文字列ではない。
2. `filename` は絶対パスではない。
3. `(root / filename).resolve()` は `root.resolve()` と同一、またはその配下である。
4. 保存時は親ディレクトリ作成後に親ディレクトリの `resolve()` を再確認する。

`save_image()` は `cv2.imwrite(str(path), image)` の戻り値を検証する。戻り値が `False` の場合、または呼び出し後に `path.exists()` が `False` の場合は `ResourceWriteError` を送出する。`load_image()` は `cv2.imread()` が `None` を返した場合に `ResourceReadError` を送出する。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | schema 型不一致、TOML 破損、manifest settings path 不正、secret 値の通常設定混入 |
| `SecretBoundaryError` | `GlobalSettings` へ secret field を定義、または Runtime builder が `SecretsSettings` 以外から secret 値を受け取った |
| `ResourcePathError` | 空 filename、絶対パス、root 外参照、root 外シンボリックリンク |
| `ResourceWriteError` | `cv2.imwrite()` が `False` を返す、保存後にファイルが存在しない、親ディレクトリ作成に失敗 |
| `ResourceReadError` | `cv2.imread()` が `None` を返す、読み込み対象が存在しない |

例外メッセージには secret 値を含めない。パスは `project_root` または `static_root` からの相対表示を優先する。

### シングルトン管理

既存 `singletons.py` の `global_settings` と `secrets_settings` は互換のため維持する。`SettingsSchema`、`MacroSettingsResolver`、`ResourceStorePort` はシングルトンにしない。`reset_for_testing()` は `global_settings`、`secrets_settings` の snapshot と lock 状態を初期化できるようにする。

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
| ユニット | `test_resource_store_rejects_absolute_path` | 絶対 filename を `ResourcePathError` にする |
| ユニット | `test_resource_store_rejects_parent_escape` | `..` と root 外シンボリックリンクを拒否する |
| ユニット | `test_resource_store_checks_imwrite_return` | `cv2.imwrite()` が `False` の場合に `ResourceWriteError` を送出する |
| ユニット | `test_resource_store_checks_saved_file_exists` | 書き込み成功戻り値でも保存後未存在なら失敗にする |
| ユニット | `test_resource_store_raises_on_imread_none` | `cv2.imread()` が `None` の場合に `ResourceReadError` を送出する |
| 結合 | `test_runtime_builder_uses_secrets_settings_for_notifications` | 通知 secret が `SecretsSettings` からのみ adapter へ渡る |
| 結合 | `test_existing_macro_settings_load_without_macro_changes` | 代表既存マクロの settings が変更なしで読み込まれる |
| 結合 | `test_command_save_and_load_image_use_resource_store` | `Command.save_img()` / `load_img()` が新 Port 経由で動く |
| ハードウェア | `test_realdevice_resource_save_during_macro` | `@pytest.mark.realdevice`。実機マクロ実行中の画像保存が成功する |
| パフォーマンス | `test_settings_schema_validation_perf` | 100 キー検証が 50 ms 未満で完了する |

## 6. 実装チェックリスト

- [ ] `GlobalSettings` / `SecretsSettings` schema の公開 API を確定
- [ ] 通常設定と秘密設定の境界を Runtime builder に反映
- [ ] `MacroSettingsResolver` を `ResourceStorePort` から分離
- [ ] `static\<macro_name>\settings.toml` 互換を固定
- [ ] resource path escape 防止を `ResourcePathGuard` として実装
- [ ] `cv2.imwrite()` の戻り値と保存後存在を検証
- [ ] `StaticResourceIO` 互換 adapter を新 Port へ接続
- [ ] secret 値を例外、保存ログ、GUI 表示イベントへ平文出力しない
- [ ] ユニットテスト作成・パス
- [ ] 統合テスト作成・パス
- [ ] 既存マクロ変更不要で互換検証
