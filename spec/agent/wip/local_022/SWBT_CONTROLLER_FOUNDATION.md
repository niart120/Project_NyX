# swbt controller foundation 仕様書

## 1. 概要

### 1.1 目的

swbt backend の実装前に、optional dependency、controller model、settings 正規化、IMU command、adapter discovery を定義する。ここでは Bluetooth 接続や入力送信は実装せず、後続の session / port / runtime / GUI が依存する型と contract を確定する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| `SwbtControllerType` | 永続化・CLI 入力で使う controller 種別。`pro-controller`、`joy-con-l`、`joy-con-r` |
| `SwbtControllerModel` | swbt controller class、capabilities、表示名、既定 key store 名を持つ immutable definition |
| `SwbtInputCapabilities` | controller 種別ごとの button、left stick、right stick、IMU 対応可否 |
| `SwbtControllerConfig` | settings / CLI / GUI から正規化済みの swbt backend 設定 |
| `ControllerConfig` | `SerialControllerConfig | SwbtControllerConfig` |
| `IMUFrame` | NyX 側の IMU 入力 model。swbt の `IMUFrame` とは mapper で変換する |
| `SwbtAdapterDiscoveryService` | `swbt.list_adapters()` を NyX の DTO とエラーへ変換する service |

### 1.3 背景・問題

swbt backend は controller type ごとに対応 input が違う。Pro Controller と Joy-Con L/R を文字列のまま扱うと、GUI choices、CLI choices、settings validation、mapper の unsupported 判定が重複する。

IMU は swbt backend で扱えるが、既存 serial backend では扱えない。silent no-op にすると IMU 前提のマクロが失敗に気づけないため、`Command` と `ControllerOutputPort` の共通 surface として追加し、非対応 backend は `NotImplementedError` にする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| dependency | swbt 未導入 | `swbt-python>=0.2.0,<0.3.0` を `swbt` extra に追加 |
| controller type | 未定義 | `SwbtControllerModel` へ正規化し、config に raw 文字列を残さない |
| GUI / CLI choices | 個別定義になり得る | `supported_controller_models()` から導出する |
| adapter refresh | 未定義 | `list_adapters()` の no-open discovery を使う |
| IMU | command surface なし | `IMUFrame`、`Command.imu(...)`、`ControllerOutputPort.imu(...)` を追加 |

### 1.5 着手条件

- 親計画 `local_021` が存在する。
- `docs/architecture/swbt-integration/configuration-cli-gui.md`、`controller-models.md`、`adapter-discovery.md`、`imu-command.md` を参照済みである。
- この仕様では `SwbtControllerSession`、`SwbtControllerOutputPort`、`SwbtControllerOutputPortFactory` を実装しない。
- `swbt` import は `hardware/swbt` package 内に閉じ、serial backend の通常 import を壊さない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | `[project.optional-dependencies].swbt` に `swbt-python>=0.2.0,<0.3.0` を追加し、`swbt` pytest marker を追加する |
| `src/nyxpy/framework/core/constants/imu.py` | 新規 | `IMUFrame` と `Vector3` を定義する |
| `src/nyxpy/framework/core/constants/__init__.py` | 変更 | `IMUFrame` を公開する |
| `src/nyxpy/framework/core/io/ports.py` | 変更 | `supports_imu` と既定 unsupported の `imu(...)` を追加する |
| `src/nyxpy/framework/core/macro/command.py` | 変更 | `Command.imu(...)` と `DefaultCommand.imu(...)` を追加する |
| `src/nyxpy/framework/core/io/controller_config.py` | 新規 | `ControllerBackend`、`SerialControllerConfig`、`ControllerConfig`、settings 正規化 helper を定義する |
| `src/nyxpy/framework/core/hardware/swbt/__init__.py` | 新規 | swbt backend の public re-export を定義する |
| `src/nyxpy/framework/core/hardware/swbt/config.py` | 新規 | `SwbtControllerType`、`SwbtInputCapabilities`、`SwbtControllerModel`、`SwbtControllerConfig`、`supported_controller_models()` を定義する |
| `src/nyxpy/framework/core/hardware/swbt/discovery.py` | 新規 | `SwbtAdapterDiscoveryService`、`SwbtAdapterView`、`resolve_adapter(...)` を定義する |
| `src/nyxpy/framework/core/hardware/swbt/errors.py` | 新規 | swbt 例外から NyX 例外への変換 code を定義する |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | `controller.*` schema を追加し、既存 serial flat key を読み込み元として残す |
| `tests/unit/framework/hardware/swbt/test_config.py` | 新規 | controller model、capabilities、config validation を検証する |
| `tests/unit/framework/hardware/swbt/test_discovery.py` | 新規 | adapter discovery と adapter 名解決を fake `list_adapters()` で検証する |
| `tests/unit/framework/io/test_controller_config.py` | 新規 | settings 正規化と旧 serial key fallback を検証する |
| `tests/unit/framework/io/test_ports.py` | 変更 | `ControllerOutputPort.imu()` 既定 unsupported を検証する |
| `tests/unit/framework/macro/test_command.py` | 変更 | `DefaultCommand.imu(...)` が controller port へ委譲することを検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

M1 は `hardware/swbt` package の土台である。`config.py` と `discovery.py` は `swbt-python` の public API を使ってよいが、GUI、runtime builder、macro command から `swbt-python` を直接 import させない。

### 公開 API 方針

`Command.imu(...)` はマクロ作者向け API として追加する。serial backend は `ControllerOutputPort` の既定実装により `NotImplementedError` になる。`SwbtControllerConfig` は `controller_type: str` を持たず、settings parser で `SwbtControllerModel` へ解決する。

### 後方互換性

`ControllerOutputPortFactory` の改名や runtime 接続は後続仕様で扱う。M1 では既存 serial CLI の動作を変えない。既存 settings の `serial_device`、`serial_baud`、`serial_protocol` は `controller.serial.*` が未指定の場合の fallback とする。

### レイヤー構成

`hardware/swbt/config.py` は controller model と validation を持つ。`discovery.py` は adapter 列挙だけを行い、pairing、reconnect、controller open、report loop を開始しない。`errors.py` は `ConfigurationError` / `DeviceError` への変換を提供する。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| adapter discovery | controller open なし |
| `supported_controller_models()` | 定義済み tuple を返し、I/O しない |
| settings 正規化 | builder / CLI / GUI の構成時に 1 回実行する |
| swbt extra 未導入時 | serial backend と `Command` import が成功する |

### 並行性・スレッド安全性

M1 では thread や async event loop を追加しない。adapter discovery は同期 API として定義し、GUI では呼び出し側が worker thread に逃がす。

## 4. 実装仕様

### dependency

```toml
[project.optional-dependencies]
swbt = [
    "swbt-python>=0.2.0,<0.3.0",
]
```

### controller model

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SwbtControllerType(str, Enum):
    PRO_CONTROLLER = "pro-controller"
    JOY_CON_L = "joy-con-l"
    JOY_CON_R = "joy-con-r"


@dataclass(frozen=True, slots=True)
class SwbtInputCapabilities:
    buttons: frozenset[object]
    left_stick: bool
    right_stick: bool
    imu: bool


@dataclass(frozen=True, slots=True)
class SwbtControllerModel:
    controller_type: SwbtControllerType
    display_name: str
    controller_cls: type[object]
    default_key_store_name: str
    capabilities: SwbtInputCapabilities

    def default_key_store_path(self, base_dir: Path) -> Path: ...
```

`controller_cls` と capabilities の button set は `swbt` import が必要である。`hardware/swbt/config.py` は swbt backend 選択時だけ使う前提なので `swbt` を import してよい。`swbt` 未導入で `supported_controller_models()` を呼んだ場合は `ConfigurationError(code="NYX_SWBT_DEPENDENCY_MISSING")` へ変換する。

### controller config

```python
@dataclass(frozen=True, slots=True)
class SwbtControllerConfig:
    model: SwbtControllerModel
    adapter: str = "usb:0"
    key_store_path: Path | None = Path(".nyxpy/swbt/pro-controller-bond.json")
    connect_timeout_sec: float = 30.0
    operation_timeout_sec: float = 5.0
    report_period_us: int | None = 8000
    diagnostics_path: Path | None = None
    reset_on_port_create: bool = True
```

設定値は次である。

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `controller.backend` | `str` | `"serial"` | `serial` または `swbt` |
| `controller.serial.device` | `str | None` | `None` | serial device |
| `controller.serial.protocol` | `str` | `"CH552"` | serial protocol |
| `controller.serial.baudrate` | `int` | `9600` | serial baudrate |
| `controller.swbt.controller_type` | `str` | `"pro-controller"` | swbt controller type |
| `controller.swbt.adapter` | `str` | `"usb:0"` | adapter 名。未指定時は discovery 結果で解決可能 |
| `controller.swbt.key_store_path` | `str | None` | controller type 別既定 | pairing key JSON |
| `controller.swbt.connect_timeout_sec` | `float` | `30.0` | pair/reconnect timeout |
| `controller.swbt.operation_timeout_sec` | `float` | `5.0` | apply/status/close の同期 timeout |
| `controller.swbt.report_period_us` | `int | None` | `8000` | swbt report loop 周期 |
| `controller.swbt.reset_on_port_create` | `bool` | `True` | port 作成時に neutral を送るか |

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
    is_bluetooth_hci: bool


class SwbtAdapterDiscoveryService:
    def list_adapters(self) -> tuple[SwbtAdapterView, ...]: ...
```

`list_adapters()` は adapter 候補を返すだけで、controller open、pairing、reconnect、report loop を開始しない。adapter 未指定時、候補が 1 件ならその `name` を採用できる。0 件または複数件では明示選択を要求する。

### エラーハンドリング

| 条件 | NyX 例外 |
|------|----------|
| swbt import 不可 | `ConfigurationError(code="NYX_SWBT_DEPENDENCY_MISSING")` |
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
| ユニット | `test_swbt_optional_dependency_declared` | `pyproject.toml` の `swbt-python>=0.2.0,<0.3.0` |
| ユニット | `test_supported_controller_models_returns_three_models` | Pro Controller / Joy-Con L / Joy-Con R が登録される |
| ユニット | `test_parse_controller_type_rejects_unknown_value` | 不正値が `NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED` |
| ユニット | `test_swbt_config_resolves_default_key_store_per_controller_type` | controller type ごとに key store path が分かれる |
| ユニット | `test_controller_config_falls_back_to_legacy_serial_keys` | 旧 serial flat key が読み込み元になる |
| ユニット | `test_controller_config_does_not_keep_controller_type_string` | `SwbtControllerConfig` に raw 文字列が残らない |
| ユニット | `test_controller_output_port_imu_default_unsupported` | 既定 `imu()` が `NotImplementedError` |
| ユニット | `test_default_command_imu_delegates_to_controller` | `DefaultCommand.imu()` が port へ委譲する |
| ユニット | `test_adapter_discovery_returns_view_without_opening_controller` | fake `list_adapters()` のみが呼ばれる |
| ユニット | `test_resolve_adapter_uses_aliases_and_rejects_ambiguous` | alias 解決と曖昧候補の拒否 |

検証コマンド:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/unit/framework/hardware/swbt/test_config.py tests/unit/framework/hardware/swbt/test_discovery.py tests/unit/framework/io/test_controller_config.py tests/unit/framework/io/test_ports.py tests/unit/framework/macro/test_command.py
```

## 6. 実装チェックリスト

- [ ] `pyproject.toml` に `swbt` optional dependency と pytest marker を追加する。
- [ ] `IMUFrame` を追加し、constants package から公開する。
- [ ] `ControllerOutputPort.supports_imu` と `imu(...)` の既定 unsupported を追加する。
- [ ] `Command.imu(...)` と `DefaultCommand.imu(...)` を追加する。
- [ ] `ControllerBackend`、`SerialControllerConfig`、`ControllerConfig`、settings 正規化 helper を追加する。
- [ ] `hardware/swbt/config.py` に controller model と capabilities を追加する。
- [ ] `hardware/swbt/discovery.py` に adapter DTO、discovery service、adapter 解決を追加する。
- [ ] `hardware/swbt/errors.py` に swbt 例外 mapping を追加する。
- [ ] GUI / CLI choices が `supported_controller_models()` から導出できることをテストする。
- [ ] adapter refresh が pairing、reconnect、report loop を開始しないことをテストする。
- [ ] swbt 未導入環境で serial backend の import が壊れないことをテストする。
