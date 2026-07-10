# swbt controller foundation 仕様書

## 1. 概要

### 1.1 目的

swbt backend の実装前に、通常依存、controller model、settings schema、IMU command、adapter discovery、`nyxpy swbt adapters` を定義する。ここでは Bluetooth 接続や入力送信は実装せず、後続の session / port / runtime / GUI が依存する型と contract を確定する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| `SwbtControllerType` | 永続化・CLI 入力で使う controller 種別。`pro-controller`、`joy-con-l`、`joy-con-r` |
| `SwbtControllerModel` | controller type、表示名、既定 key store 名、NyX 入力 capabilities を持つ immutable definition |
| `SwbtInputCapabilities` | controller 種別ごとの対応 `Button`、left stick、right stick、IMU 対応可否 |
| `SwbtControllerConfig` | settings / CLI / GUI から正規化済みの swbt backend 設定 |
| `ControllerConfig` | `SerialControllerConfig | SwbtControllerConfig` |
| `IMUFrame` | NyX 側の IMU 入力 model。swbt の `IMUFrame` とは mapper で変換する |
| `SwbtAdapterDiscoveryService` | `swbt.list_adapters()` を NyX の DTO とエラーへ変換する service |
| `SwbtAdapterView` | CLI / GUI / troubleshooting へ出す adapter 表示 DTO |

### 1.3 背景・問題

swbt backend は controller type ごとに対応 input が違う。Pro Controller と Joy-Con L/R を文字列のまま扱うと、GUI choices、CLI choices、settings validation、mapper の unsupported 判定が重複する。

IMU は swbt backend で扱えるが、既存 serial backend では扱えない。silent no-op にすると IMU 前提のマクロが失敗に気づけないため、`Command` と `ControllerOutputPort` の共通 surface として追加し、非対応 backend は `NotImplementedError` にする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| dependency | swbt 未導入 | `swbt-python>=0.2.0,<0.3.0` を通常依存に追加 |
| controller type | 未定義 | `SwbtControllerModel` へ正規化し、config に raw 文字列を残さない |
| GUI / CLI choices | 個別定義になり得る | `supported_controller_models()` から導出する |
| adapter refresh | 未定義 | `list_adapters()` の no-open discovery を使う |
| IMU | command surface なし | `IMUFrame`、`Command.imu(...)`、`ControllerOutputPort.imu(...)` を追加 |
| adapter CLI | 未導入 | `nyxpy swbt adapters [--json]` で候補を表示する |

### 1.5 着手条件

- 親計画 `local_021` が存在する。
- `docs/architecture/swbt-integration/configuration-cli-gui.md`、`controller-models.md`、`adapter-discovery.md`、`imu-command.md` を参照済みである。
- この仕様では `SwbtControllerSession`、`SwbtControllerOutputPort`、`SwbtControllerOutputPortFactory` を実装しない。
- `hardware/swbt/config.py` は GUI / CLI choices のために import されるため、controller class など swbt runtime 型の解決は session 作成時へ遅延する。

### 1.6 完了結果

2026-07-10 に、swbt controller foundation として次を実装した。

- `swbt-python>=0.2.0,<0.3.0` を通常依存に追加し、`swbt` pytest marker を追加した。
- `IMUFrame`、`ControllerOutputPort.supports_imu`、`ControllerOutputPort.imu(...)`、`Command.imu(...)`、`DefaultCommand.imu(...)` を追加した。
- `controller.*` schema と `controller_config_from_settings(...)` を追加し、旧 `serial_device` / `serial_baud` / `serial_protocol` に依存しない正規化経路を用意した。
- `hardware/swbt/config.py` に controller model、capabilities、`SwbtControllerConfig` を追加した。
- `hardware/swbt/discovery.py` に adapter DTO、discovery service、adapter 解決を追加した。
- `nyxpy swbt adapters [--json]` を追加した。

`SwbtControllerSession`、mapper、port、factory、runtime builder の backend 切替、GUI 接続操作は本仕様の範囲外であり、`local_023` 以降で扱う。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | `[project].dependencies` に `swbt-python>=0.2.0,<0.3.0` を追加し、`swbt` pytest marker を追加する |
| `src/nyxpy/framework/core/constants/imu.py` | 新規 | `IMUFrame` と `Vector3` を定義する |
| `src/nyxpy/framework/core/constants/__init__.py` | 変更 | `IMUFrame` を公開する |
| `src/nyxpy/framework/core/io/ports.py` | 変更 | `supports_imu` と既定 unsupported の `imu(...)` を追加する |
| `src/nyxpy/framework/core/macro/command.py` | 変更 | `Command.imu(...)` と `DefaultCommand.imu(...)` を追加する |
| `src/nyxpy/framework/core/io/controller_config.py` | 新規 | `ControllerBackend`、`SerialControllerConfig`、`ControllerConfig`、settings 正規化 helper を定義する |
| `src/nyxpy/framework/core/hardware/swbt/__init__.py` | 新規 | swbt backend の public re-export を定義する |
| `src/nyxpy/framework/core/hardware/swbt/config.py` | 新規 | `SwbtControllerType`、`SwbtInputCapabilities`、`SwbtControllerModel`、`SwbtControllerConfig`、`supported_controller_models()` を定義する |
| `src/nyxpy/framework/core/hardware/swbt/discovery.py` | 新規 | `SwbtAdapterDiscoveryService`、`SwbtAdapterView`、`resolve_adapter(...)` を定義する |
| `src/nyxpy/framework/core/hardware/swbt/errors.py` | 新規 | swbt 例外から NyX 例外への変換 code を定義する |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | `controller.*` schema を追加し、旧 serial flat key を削除する |
| `src/nyxpy/cli/swbt_cli.py` | 新規 | `adapters` subcommand の処理を実装する |
| `src/nyxpy/__main__.py` | 変更 | `swbt adapters` subparser を追加し、`swbt_cli.py` へ委譲する |
| `tests/unit/framework/hardware/swbt/test_config.py` | 新規 | controller model、capabilities、config validation を検証する |
| `tests/unit/framework/hardware/swbt/test_discovery.py` | 新規 | adapter discovery と adapter 名解決を fake `list_adapters()` で検証する |
| `tests/unit/framework/io/test_controller_config.py` | 新規 | settings 正規化と旧 serial key 廃止を検証する |
| `tests/unit/framework/io/test_ports.py` | 変更 | `ControllerOutputPort.imu()` 既定 unsupported を検証する |
| `tests/unit/framework/runtime/test_default_command_ports.py` | 変更 | `DefaultCommand.imu(...)` が controller port へ委譲することを検証する |
| `tests/unit/cli/test_swbt_cli.py` | 新規 | `adapters` CLI を fake discovery で検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

M1 は `hardware/swbt` package の土台である。`config.py` と `discovery.py` は GUI、runtime builder、macro command から直接 swbt runtime 型を漏らさない。adapter discovery は `swbt.list_adapters()` を使うが、controller open、pairing、reconnect、report loop は開始しない。

### 公開 API 方針

`Command.imu(...)` はマクロ作者向け API として追加する。serial backend は `ControllerOutputPort` の既定実装により `NotImplementedError` になる。`SwbtControllerConfig` は `controller_type: str` を持たず、settings parser で `SwbtControllerModel` へ解決する。

### 後方互換性

旧 settings の `serial_device`、`serial_baud`、`serial_protocol` は廃止する。保存・読み込み・docs は `controller.*` schema だけを正とする。旧 key の alias や移行警告は追加しない。

### レイヤー構成

`hardware/swbt/config.py` は controller model と validation を持つ。`discovery.py` は adapter 列挙だけを行い、pairing、reconnect、controller open、report loop を開始しない。`errors.py` は `ConfigurationError` / `DeviceError` への変換を提供する。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| adapter discovery | controller open なし |
| `supported_controller_models()` | 定義済み tuple を返し、I/O しない |
| settings 正規化 | builder / CLI / GUI の構成時に 1 回実行する |
| adapter CLI | discovery だけを実行し、settings を変更しない |

### 並行性・スレッド安全性

M1 では thread や async event loop を追加しない。adapter discovery は同期 API として定義し、GUI では呼び出し側が worker thread に逃がす。

## 4. 実装仕様

### dependency

```toml
dependencies = [
    "swbt-python>=0.2.0,<0.3.0",
]
```

`swbt-python` は通常依存であり、`[project.optional-dependencies].swbt` は作らない。

### controller model

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from nyxpy.framework.core.constants import Button


class SwbtControllerType(str, Enum):
    PRO_CONTROLLER = "pro-controller"
    JOY_CON_L = "joy-con-l"
    JOY_CON_R = "joy-con-r"


@dataclass(frozen=True, slots=True)
class SwbtInputCapabilities:
    buttons: frozenset[Button]
    left_stick: bool
    right_stick: bool
    imu: bool


@dataclass(frozen=True, slots=True)
class SwbtControllerModel:
    controller_type: SwbtControllerType
    display_name: str
    default_key_store_name: str
    capabilities: SwbtInputCapabilities

    def default_key_store_path(self, base_dir: Path) -> Path: ...
```

`SwbtControllerModel` は swbt controller class を持たない。controller class は session 作成時に controller type から解決する。

### controller config

```python
@dataclass(frozen=True, slots=True)
class SwbtControllerConfig:
    model: SwbtControllerModel
    adapter: str
    key_store_path: Path
    connect_timeout_sec: float = 30.0
    report_period_us: int | None = 8000
```

設定値は次である。

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `controller.backend` | `str` | `"serial"` | `serial` または `swbt` |
| `controller.serial.device` | `str | None` | `None` | serial device |
| `controller.serial.protocol` | `str` | `"CH552"` | serial protocol |
| `controller.serial.baudrate` | `int` | `9600` | serial baudrate |
| `controller.swbt.controller_type` | `str` | `"pro-controller"` | swbt controller type |
| `controller.swbt.adapter` | `str | None` | `None` | adapter 名。空または未指定のまま接続する場合は `NYX_SWBT_ADAPTER_NOT_SELECTED` |
| `controller.swbt.key_store_path` | `str | None` | controller type 別既定 | pairing key JSON。未指定時は `.nyxpy/swbt/<controller>-bond.json` |
| `controller.swbt.connect_timeout_sec` | `float` | `30.0` | pair/reconnect timeout |
| `controller.swbt.report_period_us` | `int | None` | `8000` | swbt report loop 周期 |

`operation_timeout_sec` と `reset_on_port_create` は settings に出さない。`operation_timeout_sec` は session / factory の内部 default とし、port 作成時の neutral は常に試みる。

`key_store_path` は workspace root 相対 path を標準にする。絶対 path 入力は許可し、workspace 内なら保存時に相対化する。workspace 外 path も許可するが docs では推奨しない。

### IMU API

```python
Vector3 = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class IMUFrame:
    accelerometer: Vector3 = (0, 0, 0)
    gyroscope: Vector3 = (0, 0, 0)

    @classmethod
    def neutral(cls) -> "IMUFrame": ...
    @classmethod
    def raw(cls, *, accel: Vector3 | None = None, gyro: Vector3 | None = None) -> "IMUFrame": ...
    @classmethod
    def accel(cls, *, x: int = 0, y: int = 0, z: int = 0) -> "IMUFrame": ...
    @classmethod
    def gyro(cls, *, x: int = 0, y: int = 0, z: int = 0) -> "IMUFrame": ...
```

`Command.imu(frame)` は 1 frame を 3 frame 分に複製する。`Command.imu(frame1, frame2, frame3)` は 3 frame を順に使う。0、2、4 個以上は swbt mapper で `NYX_IMU_FRAME_COUNT_INVALID` にする。

### adapter discovery

```python
@dataclass(frozen=True, slots=True)
class SwbtAdapterView:
    name: str
    aliases: tuple[str, ...]
    display_name: str
    vendor_id: int | None
    product_id: int | None
    manufacturer: str | None
    product: str | None
    serial_number: str | None
    bus_number: int | None
    device_address: int | None
    port_numbers: tuple[int, ...]
    is_bluetooth_hci: bool


class SwbtAdapterDiscoveryService:
    def list_adapters(self) -> tuple[SwbtAdapterView, ...]: ...
```

`list_adapters()` は adapter 候補を返すだけで、controller open、pairing、reconnect、report loop を開始しない。adapter 未指定時の自動採用はしない。接続操作で adapter が空なら常に `NYX_SWBT_ADAPTER_NOT_SELECTED` とする。

adapter 解決規則:

| 状況 | 扱い |
|------|------|
| selected adapter が `name` に一致 | その adapter を採用 |
| selected adapter が `aliases` に一致 | 対応する `name` へ正規化して採用 |
| selected adapter が空 | `NYX_SWBT_ADAPTER_NOT_SELECTED` |
| 候補不一致 | `NYX_SWBT_ADAPTER_NOT_FOUND` |
| 複数候補が同じ alias に一致 | `NYX_SWBT_ADAPTER_AMBIGUOUS` |

settings 保存値は正規化後の `name` とする。CLI の `--adapter` は当該実行だけの override であり、settings は書き換えない。

### `nyxpy swbt adapters`

```console
nyxpy swbt adapters
nyxpy swbt adapters --json
```

標準出力には adapter `name`、display name、aliases、VID/PID を出す。`--json` は `SwbtAdapterView` の全フィールドを出す。settings は変更しない。

### エラーハンドリング

| 条件 | NyX 例外 |
|------|----------|
| 不正 controller type | `ConfigurationError(code="NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED")` |
| adapter discovery 失敗 | `ConfigurationError(code="NYX_SWBT_ADAPTER_DISCOVERY_FAILED")` |
| adapter 未選択 | `ConfigurationError(code="NYX_SWBT_ADAPTER_NOT_SELECTED")` |
| adapter 候補不一致 | `ConfigurationError(code="NYX_SWBT_ADAPTER_NOT_FOUND")` |
| adapter 候補曖昧 | `ConfigurationError(code="NYX_SWBT_ADAPTER_AMBIGUOUS")` |
| IMU frame 数不正 | `DeviceError(code="NYX_IMU_FRAME_COUNT_INVALID")` |

### シングルトン管理

新規グローバル singleton は追加しない。controller model registry は immutable な module 定義として扱い、session や adapter resource を保持しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_swbt_dependency_declared_as_runtime_dependency` | `pyproject.toml` の通常依存に `swbt-python>=0.2.0,<0.3.0` |
| ユニット | `test_supported_controller_models_returns_three_models_without_swbt_runtime_import` | Pro Controller / Joy-Con L / Joy-Con R が登録される |
| ユニット | `test_parse_controller_type_rejects_unknown_value` | 不正値が `NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED` |
| ユニット | `test_swbt_config_resolves_default_key_store_per_controller_type` | controller type ごとに key store path が分かれる |
| ユニット | `test_controller_config_rejects_legacy_serial_flat_keys` | 旧 serial flat key が fallback されない |
| ユニット | `test_controller_config_does_not_keep_controller_type_string` | `SwbtControllerConfig` に raw 文字列が残らない |
| ユニット | `test_controller_output_port_imu_default_unsupported` | 既定 `imu()` が `NotImplementedError` |
| ユニット | `test_default_command_imu_delegates_to_controller` | `DefaultCommand.imu()` が port へ委譲する |
| ユニット | `test_adapter_discovery_returns_view_without_opening_controller` | fake `list_adapters()` のみが呼ばれる |
| ユニット | `test_resolve_adapter_uses_aliases_and_rejects_ambiguous` | alias 解決と曖昧候補の拒否 |
| CLI | `test_swbt_adapters_cli_prints_json_without_changing_settings` | adapter JSON 出力と settings 非変更 |

検証コマンド:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/unit/framework/hardware/swbt/test_config.py tests/unit/framework/hardware/swbt/test_discovery.py tests/unit/framework/io/test_controller_config.py tests/unit/framework/io/test_ports.py tests/unit/framework/runtime/test_default_command_ports.py tests/unit/cli/test_swbt_cli.py tests/unit/cli/test_run_cli_parser.py tests/unit/framework/settings/test_settings_schema.py
```

実行済み検証:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src\nyxpy --output-format concise --no-progress
uv run pytest tests/unit/framework/hardware/swbt/test_config.py tests/unit/framework/hardware/swbt/test_discovery.py tests/unit/framework/io/test_controller_config.py tests/unit/framework/io/test_ports.py tests/unit/framework/runtime/test_default_command_ports.py tests/unit/cli/test_swbt_cli.py tests/unit/cli/test_run_cli_parser.py tests/unit/framework/settings/test_settings_schema.py
uv run pytest tests/unit -m "not realdevice and not swbt"
```

## 6. 実装チェックリスト

- [x] `pyproject.toml` の通常依存に `swbt-python>=0.2.0,<0.3.0` を追加する。
- [x] `pyproject.toml` に `swbt` pytest marker を追加する。
- [x] `IMUFrame` を追加し、constants package から公開する。
- [x] `ControllerOutputPort.supports_imu` と `imu(...)` の既定 unsupported を追加する。
- [x] `Command.imu(...)` と `DefaultCommand.imu(...)` を追加する。
- [x] `ControllerBackend`、`SerialControllerConfig`、`ControllerConfig`、settings 正規化 helper を追加する。
- [x] 旧 `serial_device`、`serial_baud`、`serial_protocol` fallback を追加しないことをテストする。
- [x] `hardware/swbt/config.py` に controller model と NyX capabilities を追加する。
- [x] `hardware/swbt/discovery.py` に adapter DTO、discovery service、adapter 解決を追加する。
- [x] `hardware/swbt/errors.py` に swbt 例外 mapping を追加する。
- [x] `nyxpy swbt adapters` を追加し、adapter refresh が接続を開始しないことをテストする。
- [x] GUI / CLI choices が `supported_controller_models()` から導出できることをテストする。

## 7. 2026-07-10 監査追補

統合監査で、相対 `key_store_path` の基準と adapter alias の利用箇所を明文化した。相対 path は workspace root を基準に解決する。CLI / GUI の pair、reconnect、run は discovery 結果の `name` / `aliases` を解決し、一意な alias を代表 `name` へ正規化する。候補が 1 件でも未指定 adapter を自動採用しない。

この追補は foundation の非実機契約を補うものであり、adapter の実機列挙や接続成功を確認済みとはしない。
