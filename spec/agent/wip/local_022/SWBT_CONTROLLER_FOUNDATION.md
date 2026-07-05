# swbt controller backend 基盤仕様書

> **対象モジュール**: `src/nyxpy/framework/core/io/`, `src/nyxpy/framework/core/runtime/`, `src/nyxpy/framework/core/settings/`, `src/nyxpy/cli/`
> **目的**: swbt controller backend 追加前に、controller 出力 factory 名、controller 設定型、settings 正規化の基盤を整える。
> **関連ドキュメント**: `spec/agent/wip/local_021/SWBT_CONTROLLER_BACKEND.md`, `docs/architecture/swbt-integration/runtime-composition.md`, `docs/architecture/swbt-integration/configuration-cli-gui.md`, `docs/architecture/swbt-integration/testing-rollout.md`
> **破壊的変更**: あり。`ControllerOutputPortFactory` を `SerialControllerOutputPortFactory` へ改名し、旧名 alias、互換 import、`DeprecationWarning` は追加しない。

## 1. 概要

### 1.1 目的

M1 では、既存 serial controller 出力の責務を明示するために factory 名を `SerialControllerOutputPortFactory` へ改める。あわせて `SerialControllerConfig`、`SwbtControllerConfig`、`ControllerConfig` を導入し、既存 `serial_device` / `serial_baud` / `serial_protocol` と新しい `controller.*` 設定を同じ設定型へ正規化する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| `ControllerOutputPort` | Runtime が controller 入力送信に使う抽象 port |
| `SerialControllerOutputPort` | `SerialCommInterface` と `SerialProtocolInterface` を `ControllerOutputPort` へ接続する既存実装 |
| `SerialControllerOutputPortFactory` | serial device discovery、serial device cache、protocol を所有し、`SerialControllerOutputPort` を生成する factory |
| `ControllerConfig` | controller backend ごとの設定型。M1 では serial 実行に使い、swbt 設定型は後続実装へ渡す基盤として定義する |
| settings 正規化 | 旧 flat key と新 `controller.*` key を読み、runtime builder が扱う設定型へ変換する処理 |
| `MacroRuntimeBuilder` | Registry と各種 port factory から `ExecutionContext` を組み立てる composition root |

### 1.3 背景・問題

現行 `ControllerOutputPortFactory` は汎用名だが、実装は serial device と `SerialProtocolInterface` に依存している。swbt backend を同名 factory の分岐として足すと、serial protocol 生成、Bluetooth HID 接続、GUI manual input の lifetime が一つの責務に混ざる。

settings も現状は `serial_device`、`serial_baud`、`serial_protocol` が正であり、controller backend を表す型がない。後続の M2 以降で swbt を追加する前に、serial 専用 factory と controller 設定の境界を固定する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| factory 名 | `ControllerOutputPortFactory` が serial 専用責務を隠している | `SerialControllerOutputPortFactory` が serial 専用責務を明示する |
| 旧名 API | 旧名 import が有効 | 旧名 import は失効し、呼び出し元とテストは正名へ更新済み |
| 設定入力 | `serial_device` / `serial_baud` / `serial_protocol` を個別参照 | `SerialControllerConfig` へ正規化して参照する |
| swbt 依存 | 未導入 | M1 では `swbt-python` import と optional dependency を追加しない |
| serial 挙動 | CLI で `--serial` と `--capture` が必須 | M1 完了後も同じ挙動を維持する |

### 1.5 着手条件

- `spec/agent/wip/local_021/SWBT_CONTROLLER_BACKEND.md` が親計画として存在する。
- `docs/architecture/swbt-integration/` の設計レビュー反映済みである。
- 現行 serial backend の単体テストと CLI parser テストを更新できる状態である。
- M1 では `swbt-python` import、`pyproject.toml` の `swbt` optional dependency、`SwbtControllerOutputPort`、`SwbtGamepadService` を追加しない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/io/controller_config.py` | 新規 | `SerialControllerConfig`、`SwbtControllerConfig`、`ControllerConfig`、settings 正規化 helper を定義する |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | `ControllerOutputPortFactory` を `SerialControllerOutputPortFactory` へ改名し、エラーメッセージも正名へ更新する |
| `src/nyxpy/framework/core/io/__init__.py` | 変更 | 旧名 export を削除し、`SerialControllerOutputPortFactory` と controller config 型を export する |
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | serial controller config を使って serial port factory を構成する。swbt config は明示エラーにする |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | `controller.backend`、`controller.serial.*`、`controller.swbt.*` の schema field を追加し、既存 flat key は残す |
| `src/nyxpy/cli/run_cli.py` | 変更 | factory import と型注釈を正名へ更新し、M1 では現行 serial CLI 動作を維持する |
| `tests/unit/framework/io/test_device_factories.py` | 変更 | factory 改名、旧名未公開、serial factory 挙動維持を検証する |
| `tests/unit/framework/runtime/test_runtime_builder.py` | 変更 | settings 正規化後も serial controller factory が使われることを検証する |
| `tests/unit/framework/settings/test_settings_schema.py` | 変更 | `controller.*` schema、旧 serial key からの正規化、invalid backend を検証する |
| `tests/unit/cli/test_run_cli_parser.py` | 変更 | M1 時点で `--serial` / `--capture` 必須が変わらないことを検証する |
| `tests/integration/test_cli_runtime_adapter.py` | 変更 | CLI から builder へ渡る serial 構成が現行挙動を保つことを検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

M1 は controller 出力 backend 追加の前段である。`SerialControllerOutputPortFactory` は `core/io/device_factories.py` に残し、serial device discovery と serial device cache の所有者であり続ける。`MacroRuntimeBuilder` は引き続き `PortFactory[ControllerOutputPort]` を受け取り、実行中の `Command`、`ExecutionContext`、`MacroRuntime` は backend 種別を知らない。

### 公開 API 方針

`ControllerOutputPortFactory` という公開名は廃止し、`SerialControllerOutputPortFactory` だけを公開する。旧名 alias、旧 import path、警告付き互換層は追加しない。`ControllerConfig` は `src/nyxpy/framework/core/io/controller_config.py` に置き、runtime builder、CLI、GUI の composition root から参照できる型にする。

### 後方互換性

factory 名の変更は破壊的変更として扱う。Project NyX のフレームワーク本体はアルファ版であるため、旧名を延命せず、呼び出し元とテストを同じ変更で更新する。

既存 workspace 設定の読み込みは壊さない。`serial_device`、`serial_baud`、`serial_protocol` は `controller.serial.*` が未指定のときの fallback として読み、内部では `SerialControllerConfig` へ正規化する。

### レイヤー構成

`controller_config.py` は dataclass と settings mapping からの正規化だけを持つ。`swbt-python` の import、Bluetooth adapter 操作、service lifetime は M2 以降の担当に残す。`global_settings.py` は schema field を定義するだけで、runtime builder の生成責務を持たない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| serial device discovery 回数 | 現行 `create_device_runtime_builder()` と同じく builder 作成時 1 回 |
| serial device cache | 現行 factory と同じく device identifier ごとに再利用 |
| settings 正規化 | builder 作成時に 1 回実行し、macro 実行中に再計算しない |
| swbt 追加 import | M1 差分では `swbt` package import 数 0 |

### 並行性・スレッド安全性

M1 では新しい thread や async event loop を追加しない。serial device cache は現行 `SerialControllerOutputPortFactory` の辞書管理を維持し、既存の runtime builder lifetime で閉じる。`SettingsStore` の `RLock` と `MacroRuntimeBuilder.shutdown()` の責務は変更しない。

## 4. 実装仕様

### 公開インターフェース

```python
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from nyxpy.framework.core.settings.schema import SettingValue


@dataclass(frozen=True, slots=True)
class SerialControllerConfig:
    device: str | None = None
    protocol: str = "CH552"
    baudrate: int = 9600


@dataclass(frozen=True, slots=True)
class SwbtControllerConfig:
    adapter: str = "usb:0"
    key_store_path: Path | None = Path(".nyxpy/swbt/switch-bond.json")
    connect_timeout_sec: float = 30.0
    allow_pairing: bool = False
    report_period_us: int = 8000
    device_name: str = "Pro Controller"
    diagnostics_path: Path | None = None
    connect_on_open: bool = True
    invert_stick_y: bool = False


type ControllerConfig = SerialControllerConfig | SwbtControllerConfig


def controller_config_from_settings(
    settings: Mapping[str, SettingValue],
    *,
    serial_device_override: str | None = None,
    serial_protocol_override: str | None = None,
    serial_baudrate_override: int | None = None,
) -> ControllerConfig:
    """settings snapshot と CLI override から controller config を作る。"""
    ...


class SerialControllerOutputPortFactory:
    def create(
        self,
        *,
        name: str | None,
        baudrate: int | None,
        allow_dummy: bool,
        timeout_sec: float,
    ) -> ControllerOutputPort:
        ...

    def close(self) -> None:
        ...
```

`controller_config_from_settings()` は `controller.backend` が未指定なら `"serial"` とみなす。serial の各値は新 schema を優先し、未指定なら既存 flat key を読む。protocol fallback は `settings.get("serial_protocol", "CH552")` であり、`settings.get("protocol")` は使わない。

M1 の `create_device_runtime_builder()` は `SwbtControllerConfig` を受け取った場合、`ConfigurationError` を送出する。swbt backend を選択可能にする実装は M4 に残す。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `controller.backend` | `str` | `"serial"` | controller backend 名。M1 では `serial` のみ実行可能 |
| `controller.serial.device` | `str | None` | `None` | serial device identifier。未指定なら `serial_device` を読む |
| `controller.serial.protocol` | `str` | `"CH552"` | serial protocol 名。未指定なら `serial_protocol` を読む |
| `controller.serial.baudrate` | `int` | `9600` | serial baudrate。未指定なら `serial_baud` を読む |
| `controller.swbt.adapter` | `str` | `"usb:0"` | M2 以降で使う Bluetooth adapter 名 |
| `controller.swbt.key_store_path` | `str | None` | `".nyxpy/swbt/switch-bond.json"` | M3 以降で使う bond 情報保存先 |
| `controller.swbt.connect_timeout_sec` | `float` | `30.0` | M3 以降で使う接続 timeout 秒 |
| `controller.swbt.allow_pairing` | `bool` | `False` | M4 以降で使う pairing 許可 |
| `controller.swbt.report_period_us` | `int` | `8000` | M3 以降で使う HID report 周期 |
| `controller.swbt.device_name` | `str` | `"Pro Controller"` | M3 以降で Switch 側に見せる device 名 |
| `controller.swbt.diagnostics_path` | `str | None` | `None` | M3 以降で diagnostics trace の保存先に使う |
| `controller.swbt.connect_on_open` | `bool` | `True` | M3 以降で port 作成時接続の制御に使う |
| `controller.swbt.invert_stick_y` | `bool` | `False` | M2 以降で stick Y 軸変換に使う |

既存 `serial_device`、`serial_baud`、`serial_protocol` は schema に残す。保存時に旧 key を削除する migration は M1 では行わない。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | `controller.backend` が `serial` / `swbt` 以外である |
| `ConfigurationError` | M1 の runtime builder に `SwbtControllerConfig` が渡された |
| `ConfigurationError` | `controller.swbt.report_period_us <= 0` または `controller.swbt.connect_timeout_sec <= 0` |
| `ConfigurationError` | serial device selection、serial open に失敗し、dummy fallback も許可されていない |
| `ExceptionGroup` | `SerialControllerOutputPortFactory.close()` で cached serial device の close が失敗した |

### シングルトン管理

新規グローバル singleton は追加しない。`SerialControllerOutputPortFactory` は `create_device_runtime_builder()` の lifetime に属し、`MacroRuntimeBuilder.shutdown()` から `close()` される。settings 正規化 helper は状態を持たない純粋関数として実装する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_serial_controller_output_port_factory_reuses_serial_device` | 改名後も serial device cache と port 生成が現行どおり動く |
| ユニット | `test_controller_output_port_factory_old_name_is_not_exported` | `nyxpy.framework.core.io` と `device_factories` から旧名を import できない |
| ユニット | `test_controller_config_defaults_to_serial` | `controller.backend` 未指定で `SerialControllerConfig` が返る |
| ユニット | `test_controller_config_prefers_controller_serial_fields` | `controller.serial.*` が旧 flat key より優先される |
| ユニット | `test_controller_config_falls_back_to_legacy_serial_protocol` | `serial_protocol` を fallback として読み、`protocol` という誤った key を読まない |
| ユニット | `test_controller_config_rejects_invalid_backend` | 不正 backend が `ConfigurationError` になる |
| ユニット | `test_controller_config_rejects_invalid_swbt_numbers` | `report_period_us` と `connect_timeout_sec` の不正値を拒否する |
| ユニット | `test_create_device_runtime_builder_uses_serial_controller_config` | settings 正規化後も serial factory が `name` と `baudrate` を受け取る |
| ユニット | `test_create_device_runtime_builder_rejects_swbt_until_backend_exists` | M1 では `SwbtControllerConfig` を runtime に接続しない |
| ユニット | `test_cli_parser_still_requires_serial_and_capture` | M1 では CLI の `--serial` / `--capture` 必須が変わらない |
| 静的 | `test_foundation_does_not_import_swbt_package` | M1 対象 module の import 文に `swbt` package が増えていない |
| 結合 | `test_cli_create_runtime_builder_preserves_serial_arguments` | CLI から builder へ渡る serial device、protocol、baudrate が現行どおりである |

通常検証は次を実行する。

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/unit/framework/io/test_device_factories.py tests/unit/framework/runtime/test_runtime_builder.py tests/unit/framework/settings/test_settings_schema.py tests/unit/cli/test_run_cli_parser.py tests/integration/test_cli_runtime_adapter.py
```

## 6. 実装チェックリスト

- [ ] `src/nyxpy/framework/core/io/controller_config.py` を追加し、controller config 型と正規化 helper を実装する
- [ ] `ControllerOutputPortFactory` を `SerialControllerOutputPortFactory` へ改名する
- [ ] 旧名 alias、互換 import、`DeprecationWarning` が追加されていないことを確認する
- [ ] `src/nyxpy/framework/core/io/__init__.py` の export を正名へ更新する
- [ ] `MacroRuntimeBuilder` と `create_device_runtime_builder()` の型注釈と factory 生成を正名へ更新する
- [ ] `GLOBAL_SETTINGS_SCHEMA` に `controller.*` field を追加し、既存 serial field を残す
- [ ] `run_cli.py` の import と型注釈を正名へ更新し、M1 では `--serial` / `--capture` 必須を維持する
- [ ] factory 改名と settings 正規化のユニットテストを追加または更新する
- [ ] CLI と runtime builder の既存 serial 挙動を検証する
- [ ] M1 対象 module に `swbt-python` import が増えていないことを検証する
- [ ] `uv run ruff format .` を実行する
- [ ] `uv run ruff check .` を実行する
- [ ] `uv run ty check src/nyxpy --output-format concise --no-progress` を実行する
- [ ] 対象テストを `uv run pytest` で実行する

## 7. 親計画との依存関係と引き渡し

### 7.1 親計画との依存関係

この仕様は `local_021` の M1 に対応する。M1 は M2 以降の swbt mapper、port、service、runtime/CLI 接続の前提であり、serial factory が正名へ整理されていない状態では後続の `SwbtControllerOutputPortFactory` を同列に置けない。

M1 は `local_021` の次の決定を固定する。

- `ControllerOutputPortFactory` の旧名は残さない。
- `serial_device`、`serial_baud`、`serial_protocol` は読み込み元として残し、新 schema へ正規化する。
- `SerialProtocolInterface` と `ProtocolFactory` に swbt を入れない。
- M1 では swbt 実行経路をまだ有効化しない。

### 7.2 完了後に次へ渡す成果

M1 完了後、M2 へ次を渡す。

- `SerialControllerOutputPortFactory` へ改名済みの serial factory。
- `SerialControllerConfig`、`SwbtControllerConfig`、`ControllerConfig` の確定した import path。
- 旧 serial key と `controller.*` key を解決する settings 正規化 helper。
- swbt import がない状態で通る serial backend の単体テストと CLI parser テスト。
- `SwbtControllerConfig` を受け取ったときの明示エラー。M4 でこのエラー箇所を swbt factory 接続へ置き換える。
