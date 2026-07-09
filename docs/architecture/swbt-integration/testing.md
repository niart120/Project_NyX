# テスト

swbt 連携は unit test、session test、CLI test、GUI model test、port contract test、実機 test に分ける。通常の CI は実機なしで完結させ、実機 test は明示 marker 付きで実行する。

## unit test

### controller config / model

| test | expected |
|---|---|
| `parse_controller_type("pro-controller")` | `SwbtControllerType.PRO_CONTROLLER` |
| unsupported value | `NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED` |
| resolve model | `controller_cls`、表示名、default key store が得られる |
| capabilities | Pro Controller と Joy-Con L/R が IMU を supported として持つ |
| config normalization | `controller_type` 文字列が `SwbtControllerModel` に変換される |

### mapper

`NyxSwbtInputMapper` は純粋関数として検証する。

| test | expected |
|---|---|
| button enum mapping | Project_NyX `Button` が swbt `Button` へ変換される |
| hat diagonal mapping | `Hat.UPRIGHT` が D-pad 2 button へ変換される |
| left stick y axis | `LStick.UP` が swbt stick へ変換される |
| right stick center | `RStick.CENTER` が `SwbtStick.center()` になる |
| IMU one frame | 1 frame が 3 frame に複製される |
| IMU three frames | 3 frame が順に保存される |
| IMU invalid frame count | `NYX_IMU_FRAME_COUNT_INVALID` |
| unsupported touch | `NYX_SWBT_INPUT_UNSUPPORTED` or `NotImplementedError` |
| controller type constraint | Joy-Con type で扱えない input が失敗する |

### adapter discovery

`list_adapters()` を monkeypatch し、`AdapterInfo` から `SwbtAdapterView` への変換を検証する。

| case | expected |
|---|---|
| empty tuple | adapters `[]`、exit code 0 |
| one adapter | `name` と `aliases` が保持される |
| discovery exception | `NYX_SWBT_ADAPTER_DISCOVERY_FAILED` |
| strict match by alias | alias 指定で adapter が解決される |
| strict mismatch | `NYX_SWBT_ADAPTER_NOT_FOUND` |

## session test

swbt controller の fake class を使う。

```python
class FakeGamepad:
    def __init__(self, **kwargs): ...
    async def open(self): ...
    async def pair(self, *, timeout=None): ...
    async def reconnect(self, *, timeout=None): ...
    async def try_reconnect(self, *, timeout=None): ...
    async def apply(self, state): ...
    async def neutral(self): ...
    async def close(self, *, neutral=True): ...
```

検証項目:

- `open()` が event loop と gamepad resource を準備する。
- `start()` が `open()` 後に `reconnect()` を呼ぶ。
- `pair()` が `pair(timeout=...)` を呼ぶ。
- `reconnect()` が `try_reconnect(timeout=...)` または `reconnect(timeout=...)` を呼ぶ。
- `apply()` が event loop thread へ coroutine を渡し、完了を待つ。
- `close()` が `close(neutral=True)` を呼び、複数回呼んでも安全。
- transport error が `NYX_SWBT_TRANSPORT_OPEN_FAILED` になる。
- connection timeout が `NYX_SWBT_CONNECTION_TIMED_OUT` になる。
- invalid key store が `NYX_SWBT_KEY_STORE_INVALID` になる。
- close 後の apply が `DeviceError` になる。

## port contract test

`SwbtControllerOutputPort` は fake session で検証する。

| test | expected |
|---|---|
| `press(Button.A)` | state に A が追加され、`apply()` が呼ばれる |
| `release(Button.A)` | state から A が消える |
| `release()` | neutral が呼ばれる |
| `hold(Button.A)` | state が A のみになる |
| button + stick | 完全 state が `apply()` される |
| `imu(frame)` | IMU だけが変わり、button/stick は維持される |
| keyboard | `NotImplementedError` |
| touch | `NotImplementedError` |
| close twice | safe |

## GUI model test

既存の `VirtualControllerModel` に fake `ControllerOutputPort` を差し込む。swbt 固有 model は作らない。

| test | expected |
|---|---|
| button press | fake port の `press((button,))` が呼ばれる |
| button release | fake port の `release((button,))` が呼ばれる |
| D-pad center | previous direction release |
| left stick threshold | threshold 以下で release previous |
| controller `None` | no-op |
| swbt backend selected | model に見える型は `ControllerOutputPort` のまま |
| macro start | manual port が close され、model controller が `None` になる |
| IMU UI | 存在しない |

## CLI test

| command | expected |
|---|---|
| `nyxpy swbt adapters` | adapter list を表示 |
| `nyxpy swbt adapters --json` | JSON を出力 |
| `nyxpy swbt pair` | session `pair()` を呼ぶ |
| `nyxpy swbt reconnect` | session `reconnect()` を呼ぶ |
| dependency missing | `NYX_SWBT_DEPENDENCY_MISSING` |

## abstraction regression test

不要な layer が増えないように grep / import test を入れる。

```text
[ ] `hardware/swbt/manual.py` が存在しない
[ ] `SwbtManualInputSession` が存在しない
[ ] `gui` package から `swbt` module を import していない
[ ] GUI manual input test が fake `ControllerOutputPort` だけで通る
```

## 実機 test

marker:

```python
@pytest.mark.swbt_real_device
```

実機確認:

- adapter discovery
- Pro Controller pair / reconnect
- Joy-Con L pair / reconnect
- Joy-Con R pair / reconnect
- button press/release
- D-pad diagonal
- left/right stick
- `Command.imu(...)`
- close neutral
- GUI manual input via `ControllerOutputPort`
