# 利用する swbt-python public API

Project_NyX は `swbt-python` の公開 API を `swbt` root module から import する。private module path には依存しない。

```python
from swbt import (
    AdapterInfo,
    AdapterDiscoveryError,
    Button,
    DiagnosticsConfig,
    GamepadStatus,
    IMUFrame,
    InputState,
    JoyConL,
    JoyConR,
    ProController,
    Stick,
    SwitchGamepad,
    list_adapters,
)
```

## Adapter discovery

```python
from swbt import AdapterDiscoveryError, list_adapters

try:
    adapters = list_adapters()
except AdapterDiscoveryError as error:
    ...
```

`list_adapters()` は adapter 候補を返す no-open discovery API として扱う。候補がない場合は空 tuple を返す。列挙失敗は `AdapterDiscoveryError` として扱い、Project_NyX 側では `NYX_SWBT_ADAPTER_DISCOVERY_FAILED` に変換する。

adapter refresh は pairing、reconnect、report loop を開始しない。

## Controller class

controller 実体は次の具象 class から生成する。

| controller type | swbt class |
|---|---|
| `pro-controller` | `ProController` |
| `joy-con-l` | `JoyConL` |
| `joy-con-r` | `JoyConR` |

`SwitchGamepad` は直接生成せず、共通 interface / type annotation として扱う。

```python
pad: SwitchGamepad = ProController(
    adapter="usb:0",
    key_store_path=".nyxpy/swbt/pro-controller-bond.json",
    report_period_us=8000,
    diagnostics=None,
)
```

## Resource lifecycle

`SwbtControllerSession` は `open()` と `close(neutral=True)` の scope を所有する。`open()` は transport と report loop の準備であり、pairing や reconnect を開始しない。

```python
pad = ProController(adapter="usb:0", key_store_path="switch-bond.json")
await pad.open()
try:
    await pad.reconnect(timeout=30.0)
    await pad.apply(InputState.neutral().with_buttons([Button.A]))
finally:
    await pad.close(neutral=True)
```

## Connection APIs

Project_NyX は connection operation を明示的に分ける。

| operation | swbt API | 用途 |
|---|---|---|
| pair | `pair(timeout=...)` | 初回 pairing。key store に保存する |
| reconnect | `reconnect(timeout=...)` | 保存済み pairing key に基づく再接続 |
| connect | `connect(timeout=..., allow_pairing=False)` | 原則使わない。pairing の暗黙実行を避ける |
| connect result | `try_connect(timeout=..., allow_pairing=False)` | 原則使わない |

macro 実行時は reconnect のみを行う。key store がないからといって暗黙に pairing しない。

現行の Project_NyX 実装は `pair()` と `reconnect()` を使い、接続結果を返す別 API には依存しない。失敗理由は swbt 例外を NyX の framework error に変換して扱う。

`open()`、`pair()`、`reconnect()`、`apply()`、`neutral()`、`close()` は async API であり、`status()` だけは同期 API である。`pair()` / `reconnect()` の戻り値は `None` なので、Project_NyX は操作後に `status()` を取得し、`GamepadStatus.connection_state == "connected"` を接続成功条件とする。

## Input APIs

Project_NyX の `SwbtControllerOutputPort` は、button / stick / IMU を部分更新として `swbt-python` へ順番に投げるのではなく、内部に `NyxSwbtState` を持ち、完全な `InputState` を作って `apply(state)` する。

| NyX 操作 | swbt API の扱い |
|---|---|
| `press(keys)` | state に key を追加し、`InputState` を再構築して `apply(state)` |
| `hold(keys)` | state を破棄し、keys だけを保持する `InputState` を `apply(state)` |
| `release(keys)` | state から key を除去し、`apply(state)` |
| `release()` | neutral state に戻し、`neutral()` または neutral `InputState` を送る |
| `imu(frames)` | state の IMU frames を置き換え、`apply(state)` |

`tap()` は Project_NyX の `press(dur=...)` と意味が重なる action API なので、`ControllerOutputPort.press()` の実装には使わない。

## Input model

Project_NyX は swbt input model を外へ漏らさない。

```text
nyxpy.framework.core.constants.Button
nyxpy.framework.core.constants.Hat
nyxpy.framework.core.constants.LStick / RStick
nyxpy.framework.core.constants.IMUFrame
        ↓ mapper
swbt.Button
swbt.Stick
swbt.IMUFrame
swbt.InputState
```

`InputState.with_imu(...)` は 1 frame または 3 frame の扱いを持つ。Project_NyX 側も同じ規則に合わせる。

## Error mapping

swbt 例外は Project_NyX の framework error へ変換し、macro / GUI へ `SwbtError` をそのまま漏らさない。

| swbt 例外 | NyX error |
|---|---|
| `AdapterDiscoveryError` | `ConfigurationError(code="NYX_SWBT_ADAPTER_DISCOVERY_FAILED")` |
| `TransportOpenError` | `ConfigurationError(code="NYX_SWBT_TRANSPORT_OPEN_FAILED")` |
| `ConnectionTimeoutError` | `ConfigurationError(code="NYX_SWBT_CONNECTION_TIMED_OUT")` |
| `ConnectionFailedError` | `ConfigurationError(code="NYX_SWBT_CONNECTION_FAILED")` |
| `InvalidKeyStoreError` | `ConfigurationError(code="NYX_SWBT_KEY_STORE_INVALID")` |
| `UnsupportedInputError` | `DeviceError(code="NYX_SWBT_INPUT_UNSUPPORTED")` |
| `InvalidInputError` | `DeviceError(code="NYX_SWBT_INPUT_INVALID")` |
| `ClosedError` | `DeviceError(code="NYX_SWBT_NOT_CONNECTED")` |

## Diagnostics

`DiagnosticsConfig` は swbt の diagnostics writer interface を使うためだけに扱う。NyX は writer を `LoggerPort.technical(...)` へ接続する内部 adapter を持つ。

GUI / CLI / settings には diagnostics path や diagnostics editor を出さない。実機 test でファイル証跡が必要な場合だけ、writer を `tmp/hardware/swbt/<timestamp>/swbt-trace.jsonl` へ tee する。
