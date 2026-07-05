# swbt core adapter/service 仕様書

## 1. 概要

### 1.1 目的

`swbt-python` を NyX の `ControllerOutputPort` 実装として扱うための core 部品を追加する。対象は入力変換、port 状態管理、`SwitchGamepad` の同期 service、service を共有する factory であり、CLI、GUI、runtime builder への接続は後続仕様へ渡す。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| `swbt-python` | Switch 向け Bluetooth HID controller を扱う外部ライブラリ。Python package 名は `swbt-python`、import 名は `swbt` |
| `NyxSwbtInputMapper` | NyX の `Button`、`Hat`、`LStick`、`RStick` を swbt の `Button`、`Stick`、`InputState` へ変換する mapper |
| `SwbtControllerOutputPort` | `ControllerOutputPort` を実装し、NyX の controller 入力状態を `SwbtGamepadService` へ渡す port |
| `SwbtGamepadService` | `SwitchGamepad`、event loop thread、diagnostics writer、接続 lifecycle を所有する同期 service |
| `SwbtControllerOutputPortFactory` | 同じ service key の `SwbtGamepadService` を共有し、`create()` ごとに新しい port を返す factory |
| service key | GUI manual input と macro runtime が同じ接続を共有してよいかを判定する不変設定の組 |
| dummy service | 実機なしテストと dummy 実行で使う記録用 service。Bluetooth transport は開かない |
| fake `SwitchGamepad` | `SwbtGamepadService` の単体テストで注入する非同期 fake。`open`、`connect`、`apply`、`close` の呼び出し順を検証する |

### 1.3 背景・問題

既存の serial controller 出力は `SerialProtocolInterface` が入力状態を bytes へ変換し、`SerialCommInterface` が送信する構造である。`swbt-python` は bytes 生成器ではなく、Bluetooth adapter、pairing 情報、接続状態、周期 report loop を持つ長寿命の controller 実装であるため、serial protocol として扱うと責務が混ざる。

この仕様では `swbt-python` への依存を `swbt` extra 選択時だけ有効にし、通常 install の serial backend に import error を持ち込まない。実機に依存する pairing と入力反映確認は扱わず、dummy service と fake `SwitchGamepad` で core 部品の状態遷移と例外変換を検証する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| swbt 依存範囲 | 未導入 | `io/swbt_adapter.py`、`hardware/swbt_service.py`、lazy import 箇所へ限定 |
| 通常 install | serial backend のみ | `swbt` extra 未導入でも既存 import と serial backend が動作する |
| mapper 検証 | 未導入 | button、D-pad、stick、非対応入力を実機なしで単体検証できる |
| port close | 未導入 | `port.close()` は neutral だけを送る |
| transport close | 未導入 | factory または service owner の `close()` だけが完全 close を行う |
| service 共有 | 未導入 | 同じ service key では runtime 用 port と GUI manual input 用 port が同じ接続を使える |

### 1.5 着手条件

- 親計画 `spec/agent/wip/local_021/SWBT_CONTROLLER_BACKEND.md` の M2+M3 に対応する作業として着手する。
- M1 で `SerialControllerOutputPortFactory` 改名と controller config の配置方針が確定している。
- `SwbtControllerConfig` の設定項目は親計画の値に従い、この仕様では CLI option や settings schema を追加しない。
- `swbt-python>=0.1.1,<0.2.0` の public API を対象にする。
- 旧名 alias、互換 import、`DeprecationWarning` は追加しない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | `[project.optional-dependencies].swbt` に `swbt-python>=0.1.1,<0.2.0` を追加する |
| `src/nyxpy/framework/core/io/swbt_adapter.py` | 新規 | `NyxSwbtState`、`NyxSwbtInputMapper`、`SwbtControllerOutputPort`、swbt input API loader、非対応入力例外を実装する |
| `src/nyxpy/framework/core/hardware/swbt_service.py` | 新規 | `SwbtGamepadService`、`SwbtServiceKey`、dummy service、fake 注入用 protocol、例外変換を実装する |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | `SwbtControllerOutputPortFactory` を追加し、service key、service 共有、factory close を管理する。swbt 実装 module は必要時に lazy import する |
| `tests/unit/framework/io/test_swbt_adapter.py` | 新規 | mapper と port の状態遷移、非対応入力、optional dependency 境界を検証する |
| `tests/unit/framework/hardware/test_swbt_service.py` | 新規 | fake `SwitchGamepad` で service の start、connect、apply、neutral、close、例外変換を検証する |
| `tests/unit/framework/io/test_swbt_factory.py` | 新規 | service key、service 再利用、`port.close()` と factory close の分離、dummy fallback、GUI 向け接続操作を検証する |

## 3. 設計方針

swbt backend は `ControllerOutputPort` の具象実装である。`SerialProtocolInterface`、`ProtocolFactory`、serial device discovery には入れない。`Command`、`MacroRuntime`、`ExecutionContext` は swbt を import しない。

`swbt-python` は optional dependency とする。`nyxpy.framework.core.io.device_factories`、`nyxpy.framework.core.io.adapters`、`nyxpy.framework.core.io.ports` の通常 import では `swbt` を読み込まない。`SwbtControllerOutputPortFactory.create()` が swbt backend を作る時点で `io/swbt_adapter.py` と `hardware/swbt_service.py` を lazy import する。

`SwbtControllerOutputPort` は port ごとに NyX 側の入力状態を持つ。`create()` ごとに新しい port を返し、状態は neutral から始める。GUI と runtime は同じ `SwbtGamepadService` を共有できるが、同じ port object は共有しない。

`port.close()` は idempotent とし、内部状態を neutral に戻して `service.neutral()` を呼ぶだけにする。Bluetooth transport、diagnostics writer、event loop thread の完全終了は `SwbtControllerOutputPortFactory.close()` が `SwbtGamepadService.close()` を呼ぶことで行う。

service key は service lifetime に影響する設定だけで作る。少なくとも `adapter`、`key_store_path`、`report_period_us`、`device_name`、`diagnostics_path`、`connect_on_open` を含める。`allow_pairing` と `connect_timeout_sec` は接続試行ごとの値なので service key に含めない。

非対応入力は silent failure にしない。`ThreeDSButton`、`TouchState`、`keyboard()`、`type_key()`、`touch_down()`、`touch_up()`、`disable_sleep()` は swbt backend で扱えない入力として明示的に失敗させる。

新規グローバル singleton は追加しない。CLI と GUI の composition root が factory lifetime を所有し、factory が service lifetime を所有する。

## 4. 実装仕様

### 4.1 optional dependency 境界

`pyproject.toml` の既存 `[project.optional-dependencies]` には次の extra key を追加する。

```toml
[project.optional-dependencies]
swbt = [
    "swbt-python>=0.1.1,<0.2.0",
]
```

`swbt` import は loader 関数へ閉じ込める。extra 未導入で swbt backend を作ろうとした場合は `ConfigurationError` を送出する。

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SwbtInputApi:
    button: Any
    stick: Any
    input_state: Any


def load_swbt_input_api() -> SwbtInputApi:
    try:
        from swbt import Button, InputState, Stick
    except ModuleNotFoundError as exc:
        raise ConfigurationError(
            "swbt extra is not installed",
            code="NYX_SWBT_EXTRA_MISSING",
            component="SwbtControllerOutputPortFactory",
            cause=exc,
        ) from exc
    return SwbtInputApi(button=Button, stick=Stick, input_state=InputState)
```

unit test は fake `SwbtInputApi` を注入し、`swbt-python` 未導入環境でも mapper と port の検証を実行できるようにする。

### 4.2 入力状態と mapper

`NyxSwbtState` は swbt の完全入力状態を作るための中間状態である。型は production では `swbt.Button`、`swbt.Stick`、`swbt.InputState` を使うが、test では fake API を注入するため `Any` を許容する。

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NyxSwbtState:
    buttons: set[Any] = field(default_factory=set)
    left_stick: Any | None = None
    right_stick: Any | None = None
```

`NyxSwbtInputMapper` は次の public method を持つ。

```python
class UnsupportedSwbtInputError(ValueError):
    """swbt backend で表現できない NyX 入力を受け取った場合の例外。"""


class NyxSwbtInputMapper:
    def __init__(self, *, input_api: SwbtInputApi | None = None, invert_stick_y: bool = False) -> None: ...
    def new_state(self) -> NyxSwbtState: ...
    def add_to_state(self, state: NyxSwbtState, keys: tuple[KeyType, ...]) -> None: ...
    def remove_from_state(self, state: NyxSwbtState, keys: tuple[KeyType, ...]) -> None: ...
    def to_input_state(self, state: NyxSwbtState) -> object: ...
```

button は明示 dict で変換する。NyX 側の `CAP`、`LS`、`RS` は swbt 側の `CAPTURE`、`LEFT_STICK`、`RIGHT_STICK` へ対応させる。

| NyX | swbt |
|-----|------|
| `Button.A` | `Button.A` |
| `Button.B` | `Button.B` |
| `Button.X` | `Button.X` |
| `Button.Y` | `Button.Y` |
| `Button.L` | `Button.L` |
| `Button.R` | `Button.R` |
| `Button.ZL` | `Button.ZL` |
| `Button.ZR` | `Button.ZR` |
| `Button.PLUS` | `Button.PLUS` |
| `Button.MINUS` | `Button.MINUS` |
| `Button.HOME` | `Button.HOME` |
| `Button.CAP` | `Button.CAPTURE` |
| `Button.LS` | `Button.LEFT_STICK` |
| `Button.RS` | `Button.RIGHT_STICK` |

`Hat` は D-pad button set へ変換する。`press(Hat.CENTER)` と `release(Hat.*)` は D-pad 全解除として扱う。斜め方向は 2 button 同時押しで表す。新しい `Hat` を押した場合は既存 D-pad button を全解除してから新しい方向を入れる。

stick は NyX の `0..255` を swbt の `0..4095` へ変換する。

```python
def stick_8bit_to_12bit(value: int) -> int:
    if not 0 <= value <= 255:
        raise ValueError(f"stick value out of range: {value}")
    return round(value * 4095 / 255)
```

`invert_stick_y=false` を初期値とする。Y 軸既定値の最終確定は実機検証の担当範囲へ渡す。

### 4.3 `SwbtControllerOutputPort`

`SwbtControllerOutputPort` は `ControllerOutputPort` を実装する。`tap()` は使わない。NyX の `Command.press()` は `press()`、待機、`release()` の分離を前提にしており、swbt の即時 action API と意味が一致しないためである。

```python
from threading import RLock


class SwbtControllerOutputPort(ControllerOutputPort):
    def __init__(
        self,
        *,
        service: SwbtGamepadServiceProtocol,
        mapper: NyxSwbtInputMapper,
        reset_on_open: bool = True,
    ) -> None: ...

    @property
    def supports_touch(self) -> bool: ...

    def press(self, keys: tuple[KeyType, ...]) -> None: ...
    def hold(self, keys: tuple[KeyType, ...]) -> None: ...
    def release(self, keys: tuple[KeyType, ...] = ()) -> None: ...
    def keyboard(self, text: str) -> None: ...
    def type_key(self, key: KeyCode | SpecialKeyCode) -> None: ...
    def close(self) -> None: ...
```

操作の意味は次の通りである。

| 操作 | 処理 |
|------|------|
| `__init__(reset_on_open=True)` | port state を neutral で作り、`service.neutral()` を呼ぶ |
| `press(keys)` | 現在状態へ keys を追加し、完全状態を `service.apply()` へ渡す |
| `hold(keys)` | 現在状態を破棄し、keys のみを追加して `service.apply()` へ渡す |
| `release(keys)` | keys を現在状態から除去し、完全状態を `service.apply()` へ渡す |
| `release()` | 現在状態を neutral に戻し、`service.neutral()` を呼ぶ |
| `close()` | idempotent。現在状態を neutral に戻し、`service.neutral()` を呼ぶ。transport は閉じない |

close 後の `press()`、`hold()`、`release()` は `DeviceError(code="NYX_SWBT_PORT_CLOSED")` とする。`close()` の二回目は例外にしない。

### 4.4 `SwbtGamepadService`

service は `SwitchGamepad` と event loop thread を所有する。同期 port から呼ばれる method は `asyncio.run_coroutine_threadsafe()` で event loop thread へ処理を渡し、例外を NyX の `ConfigurationError` または `DeviceError` へ変換する。

```python
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SwbtServiceKey:
    adapter: str
    key_store_path: Path | None
    report_period_us: int
    device_name: str
    diagnostics_path: Path | None
    connect_on_open: bool


class SwbtGamepadProtocol(Protocol):
    async def open(self) -> None: ...
    async def connect(self, *, timeout: float, allow_pairing: bool) -> None: ...
    async def apply(self, state: object) -> None: ...
    async def close(self, *, neutral: bool = True) -> None: ...


class SwbtGamepadServiceProtocol(Protocol):
    def start(self, *, allow_pairing: bool, timeout_sec: float) -> None: ...
    def connect(self, *, allow_pairing: bool, timeout_sec: float) -> None: ...
    def apply(self, state: object) -> None: ...
    def neutral(self) -> None: ...
    def status(self) -> object: ...
    def close(self) -> None: ...


class SwbtGamepadService:
    def __init__(
        self,
        *,
        key: SwbtServiceKey,
        gamepad_factory: Callable[..., SwbtGamepadProtocol] | None = None,
        input_api: SwbtInputApi | None = None,
        operation_timeout_sec: float = 5.0,
    ) -> None: ...
```

`start()` の順序は次にする。

`status()` の production return は `swbt.GamepadStatus` である。上記 signature では `swbt` 未導入環境の import 境界を保つため `object` としている。実装では `TYPE_CHECKING` 配下で `GamepadStatus` を参照し、docstring とテストで返却 object の意味を固定する。GUI は `GamepadStatus` を直接 import せず、GUI service layer で表示用 DTO へ変換する。

| 順序 | 処理 |
|------|------|
| 1 | event loop thread を起動する |
| 2 | `diagnostics_path` があれば JSON Lines writer を開く |
| 3 | `SwitchGamepad` を作る |
| 4 | `open()` を実行する |
| 5 | `connect_on_open=true` なら `connect(timeout=timeout_sec, allow_pairing=allow_pairing)` を実行する |
| 6 | 失敗時は可能な範囲で `close(neutral=True)` と writer close を試み、NyX 例外へ変換する |

`neutral()` は `InputState.neutral()` を作って `apply()` と同じ送信経路へ流す。`close()` は idempotent とし、`SwitchGamepad.close(neutral=True)`、writer close、event loop stop、thread join の順で終了する。

service の lifecycle は `RLock` で保護する。`close` 開始後の `apply()` は `DeviceError(code="NYX_SWBT_SERVICE_CLOSING")`、close 後の `apply()` は `DeviceError(code="NYX_SWBT_SERVICE_CLOSED")` とする。`Future.result()` を待つ間に lifecycle lock を保持し続けない。

### 4.5 dummy service と fake `SwitchGamepad`

dummy service は production code に置き、実機なし runtime と単体テストで使えるようにする。Bluetooth transport は開かず、受け取った state を記録する。

```python
class DummySwbtGamepadService:
    def __init__(self, *, neutral_state_factory: Callable[[], object]) -> None: ...
    def start(self, *, allow_pairing: bool, timeout_sec: float) -> None: ...
    def connect(self, *, allow_pairing: bool, timeout_sec: float) -> None: ...
    def apply(self, state: object) -> None: ...
    def neutral(self) -> None: ...
    def status(self) -> object: ...
    def close(self) -> None: ...
```

fake `SwitchGamepad` は tests 配下に置く。`SwbtGamepadService` へ `gamepad_factory` で注入し、`open`、`connect`、`apply`、`close(neutral=True)` の呼び出し順と引数を検証する。

### 4.6 `SwbtControllerOutputPortFactory`

factory は `device_factories.py` に置き、既存 serial factory と同じ port factory 層で扱う。実装本体の import は `create()` または service 作成時まで遅延する。

```python
from collections.abc import Callable


class SwbtControllerOutputPortFactory:
    def __init__(
        self,
        *,
        config: SwbtControllerConfig,
        service_factory: Callable[[SwbtServiceKey], SwbtGamepadServiceProtocol] | None = None,
        mapper_factory: Callable[..., NyxSwbtInputMapper] | None = None,
    ) -> None: ...

    @property
    def service_key(self) -> SwbtServiceKey: ...

    def create(
        self,
        *,
        allow_dummy: bool,
        timeout_sec: float,
    ) -> ControllerOutputPort: ...

    def pair_once(self, *, timeout_sec: float | None = None) -> object: ...
    def reconnect(self, *, timeout_sec: float | None = None) -> object: ...
    def disconnect(self) -> None: ...
    def status(self) -> object | None: ...
    def close(self) -> None: ...
```

`create()` は同じ `service_key` の service を再利用し、新しい `SwbtControllerOutputPort` を返す。service が未開始なら `service.start(allow_pairing=config.allow_pairing, timeout_sec=timeout_sec)` を呼ぶ。`allow_dummy=True` で service start が失敗した場合は dummy service へ fallback する。`allow_dummy=False` では `ConfigurationError` を送出する。

`pair_once()` は `allow_pairing=True` で接続を試み、`reconnect()` は `allow_pairing=False` で接続を試みる。どちらも service が未作成なら同じ service key で作成し、成功時は `status()` の結果を返す。`disconnect()` は service を close して factory 内の service 参照を破棄する。これにより GUI は backend を切り替えずに、同じ factory から pair once、reconnect、disconnect を呼べる。

factory の `close()` は所有する service を一度だけ close する。すでに作成済みの port に対しては、runtime 側の通常 close が neutral を送る前提であり、factory close は transport の最終解放を担当する。

### 4.7 例外変換

| 条件 | NyX 例外 |
|------|----------|
| `swbt` import 不可 | `ConfigurationError(code="NYX_SWBT_EXTRA_MISSING")` |
| adapter open 失敗 | `ConfigurationError(code="NYX_SWBT_TRANSPORT_OPEN_FAILED")` |
| connect timeout | `ConfigurationError(code="NYX_SWBT_CONNECTION_TIMED_OUT")` |
| connect 失敗 | `ConfigurationError(code="NYX_SWBT_CONNECTION_FAILED")` |
| key store 不正 | `ConfigurationError(code="NYX_SWBT_KEY_STORE_INVALID")` |
| service close 中の apply | `DeviceError(code="NYX_SWBT_SERVICE_CLOSING")` |
| service close 後の apply | `DeviceError(code="NYX_SWBT_SERVICE_CLOSED")` |
| port close 後の入力操作 | `DeviceError(code="NYX_SWBT_PORT_CLOSED")` |
| swbt 非対応入力 | `UnsupportedSwbtInputError` |
| swbt 入力値不正 | `DeviceError(code="NYX_SWBT_INPUT_INVALID")` |

`swbt-python` の例外 object は macro 側へ直接漏らさない。`details` には `adapter`、`key_store_path`、`allow_pairing`、`connect_timeout_sec`、元例外型を入れる。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_swbt_optional_dependency_is_lazy_for_default_imports` | `swbt` 未導入でも `ports`、`adapters`、`device_factories` の import が成功する |
| ユニット | `test_mapper_maps_switch_buttons_with_explicit_names` | `CAP`、`LS`、`RS` を含む button map が fake swbt button へ変換される |
| ユニット | `test_mapper_replaces_dpad_buttons_when_hat_changes` | `Hat.UP` 後に `Hat.RIGHT` を押すと D-pad が RIGHT だけになる |
| ユニット | `test_mapper_clears_dpad_for_hat_center_and_release` | `Hat.CENTER` と `release(Hat.*)` が D-pad 全解除になる |
| ユニット | `test_mapper_converts_sticks_from_8bit_to_12bit` | `0`、`128`、`255` の stick 値が `0..4095` へ変換される |
| ユニット | `test_mapper_inverts_stick_y_when_enabled` | `invert_stick_y=True` で Y 値が反転する |
| ユニット | `test_mapper_rejects_unsupported_nyx_inputs` | `ThreeDSButton` と `TouchState` が `UnsupportedSwbtInputError` になる |
| ユニット | `test_port_press_hold_release_apply_complete_state` | `press`、`hold`、`release` が dummy service へ完全状態を渡す |
| ユニット | `test_port_close_sends_neutral_without_closing_service` | `port.close()` が neutral だけを送信し、service close を呼ばない |
| ユニット | `test_port_rejects_operations_after_close` | close 後の入力操作が `DeviceError(code="NYX_SWBT_PORT_CLOSED")` になる |
| ユニット | `test_service_start_opens_and_connects_fake_gamepad` | fake `SwitchGamepad` で open と connect の順序を検証する |
| ユニット | `test_service_apply_runs_on_event_loop_thread` | `apply()` が service 所有 event loop thread 上で実行される |
| ユニット | `test_service_close_uses_trailing_neutral` | `close()` が `close(neutral=True)` を呼び、thread と writer を閉じる |
| ユニット | `test_service_maps_swbt_exceptions_to_framework_errors` | transport、timeout、key store、closed 系の例外変換を検証する |
| ユニット | `test_factory_reuses_service_for_same_key_and_new_ports` | 同じ service key で service を共有し、port は毎回新規になる |
| ユニット | `test_factory_key_excludes_attempt_options` | `allow_pairing` と `connect_timeout_sec` の違いだけでは service key が変わらない |
| ユニット | `test_factory_key_includes_lifetime_options` | `adapter`、`key_store_path`、`report_period_us`、`device_name`、`diagnostics_path`、`connect_on_open` の違いで key が変わる |
| ユニット | `test_factory_falls_back_to_dummy_when_allowed` | `allow_dummy=True` の service start 失敗で dummy service を返す |
| ユニット | `test_factory_pair_reconnect_disconnect_for_gui_actions` | GUI から呼ぶ pair once、reconnect、disconnect が service へ正しい接続条件を渡す |

この仕様の通常検証は次で行う。

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/unit/framework/io/test_swbt_adapter.py tests/unit/framework/hardware/test_swbt_service.py tests/unit/framework/io/test_swbt_factory.py
```

実機検証はこの仕様の完了条件に含めない。pairing、reconnect、実機上の button、D-pad、stick 反映は M6 の担当範囲で確認する。

## 6. 実装チェックリスト

- [ ] `pyproject.toml` に `swbt` optional dependency を追加する。
- [ ] `SwbtInputApi` と `load_swbt_input_api()` を追加し、`swbt` import を lazy にする。
- [ ] `NyxSwbtState` と `NyxSwbtInputMapper` を実装する。
- [ ] button、D-pad、stick、Y 軸反転、非対応入力の mapper 単体テストを追加する。
- [ ] `SwbtControllerOutputPort` を実装する。
- [ ] `press`、`hold`、`release`、`close`、close 後操作の port 単体テストを追加する。
- [ ] `SwbtServiceKey` と `SwbtGamepadService` を実装する。
- [ ] event loop thread、diagnostics writer、start/connect/apply/neutral/close の service 単体テストを追加する。
- [ ] `swbt-python` 例外から NyX 例外への変換を実装する。
- [ ] `DummySwbtGamepadService` と fake `SwitchGamepad` 注入経路を実装する。
- [ ] `SwbtControllerOutputPortFactory` を実装し、service key と factory close を管理する。
- [ ] GUI 向けの pair once / reconnect / disconnect / status 操作を `SwbtControllerOutputPortFactory` に追加する。
- [ ] `allow_dummy=True` の dummy fallback と `allow_dummy=False` の失敗をテストする。
- [ ] `swbt` extra 未導入でも通常 import が壊れないことをテストする。
- [ ] `uv run ruff format .` を実行する。
- [ ] `uv run ruff check .` を実行する。
- [ ] `uv run ty check src/nyxpy --output-format concise --no-progress` を実行する。
- [ ] M2+M3 対象の unit test を実行する。

## 7. 親計画との依存関係と引き渡し

この仕様は `local_021` の M2+M3 をまとめる。M1 の成果である controller config と serial factory 改名が前提であり、M2+M3 では settings schema、CLI option、GUI 操作を実装しない。

後続の M4 へ渡す成果は次である。

| 成果 | 後続での使い方 |
|------|----------------|
| `SwbtControllerOutputPortFactory` | runtime builder が `controller.backend="swbt"` のときに選択する |
| `SwbtServiceKey` | GUI と runtime が同じ service を共有してよいかを判定する |
| `DummySwbtGamepadService` | runtime integration test で実機なしに `Command.press()` の反映を確認する |
| pair once / reconnect / disconnect / status 操作 | GUI の接続操作から共有 service を制御する |
| optional dependency 境界 | `--controller swbt` 選択時だけ `swbt` extra を要求し、serial backend の import を壊さない |
| 例外 code と details | CLI と GUI が接続失敗、extra 未導入、key store 不正を利用者へ表示する |

M5 へ渡す前提は、port object は共有せず service だけを共有することである。GUI manual input と macro runtime の同時入力制御は M5 で行い、この仕様では service 側が destructive な lifecycle 競合を起こさないところまでを保証する。

M6 へ渡す未確定事項は、stick Y 軸の既定値と短押し時の public flush 要否である。M2+M3 では `invert_stick_y=false` と周期 report loop 前提で実装し、private method には依存しない。
