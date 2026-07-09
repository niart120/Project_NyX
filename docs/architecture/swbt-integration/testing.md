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
| alias ambiguity | `NYX_SWBT_ADAPTER_AMBIGUOUS` |
| empty adapter | `NYX_SWBT_ADAPTER_NOT_SELECTED` |
| strict mismatch | `NYX_SWBT_ADAPTER_NOT_FOUND` |

## session test

swbt controller の fake class を使う。

```python
class FakeGamepad:
    def __init__(self, **kwargs): ...
    def open(self): ...
    def pair(self, *, timeout=None): ...
    def reconnect(self, *, timeout=None): ...
    def apply(self, state): ...
    def neutral(self): ...
    def close(self, *, neutral=True): ...
```

検証項目:

- `open()` が controller resource を準備する。
- `pair()` が `pair(timeout=...)` を呼ぶ。
- `reconnect()` が `reconnect(timeout=...)` を呼ぶ。
- `apply()` が完全な `InputState` を同期 method として完了する。
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
| `nyxpy swbt disconnect` | factory-managed cached session を閉じる |
| adapter 未指定で pair/reconnect/run | `NYX_SWBT_ADAPTER_NOT_SELECTED` |

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
@pytest.mark.realdevice
```

実行 gate は pytest option ではなく環境変数で制御する。stdin で operator 確認を待たない。

```powershell
$env:NYX_REALDEVICE = "1"
$env:NYX_SWBT = "1"
$env:NYX_SWBT_ADAPTER = "usb:0"
$env:NYX_SWBT_CONTROLLER_TYPE = "pro-controller"
$env:NYX_SWBT_KEY_STORE = ".nyxpy/swbt/pro-controller-bond.json"
$env:NYX_SWBT_OPERATOR_CONFIRMATION = "1"
uv run pytest tests/hardware/ -m realdevice
```

必要な環境変数が欠ける場合は skip する。

実機 test の証跡は `tmp/hardware/swbt/<timestamp>/` に置く。`NYX_SWBT_EVIDENCE_DIR` が指定された場合はその directory を使う。diagnostics writer は `LoggerPort.technical(...)` と `tmp/hardware/swbt/<timestamp>/swbt-trace.jsonl` の tee にする。

実機確認:

- adapter discovery
- Pro Controller pair / reconnect
- Joy-Con L pair / reconnect
- Joy-Con R pair / reconnect
- disconnect
- button press/release
- D-pad diagonal
- left/right stick
- `Command.imu(...)`
- short press durations: 16ms / 33ms / 50ms
- close neutral
- GUI manual input via `ControllerOutputPort`
