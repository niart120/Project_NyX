# テストと段階導入

swbt backend は Bluetooth HID と実機条件に依存するため、テストを単体、fake service 結合、実機の三層に分けます。

## テスト対象

| 層 | 対象 | 実機 |
|---|---|---|
| mapper unit test | `NyxSwbtInputMapper` の button / hat / stick 変換 | 不要 |
| port unit test | `SwbtControllerOutputPort` の状態遷移 | 不要 |
| service unit test | event loop wrapper と例外変換 | 不要。fake `SwitchGamepad` を使う |
| runtime integration test | `MacroRuntimeBuilder` が swbt port を注入すること | 不要。dummy service を使う |
| realdevice test | pairing / reconnect / input reflection | 必要 |

## mapper tests

確認する入力:

```text
Button.A -> SwbtButton.A
Button.ZL + Hat.UP -> buttons {ZL, DPAD_UP}
Hat.UP -> Hat.RIGHT -> D-pad が RIGHT のみになる
release(Hat.UP) -> D-pad 全解除
LStick(0, 128) -> left stick raw x=0, y=約2056
RStick(255, 128) -> right stick raw x=4095, y=約2056
release(LStick(...)) -> left stick center
```

`invert_stick_y=true` の場合、Y 値が反転することを別テストにします。

## port state tests

```python
def test_press_then_release_button(dummy_service):
    port = SwbtControllerOutputPort(service=dummy_service, mapper=NyxSwbtInputMapper())

    port.press((Button.A,))
    port.release((Button.A,))

    assert dummy_service.states[0].buttons == frozenset({SwbtButton.A})
    assert dummy_service.states[1].buttons == frozenset()
```

確認する状態遷移:

```text
press(A) -> A が追加される
press(B) -> A と B が残る
hold(X) -> A/B は消え X のみ残る
release(X) -> button なし
release() -> stick も含め neutral
close() -> neutral が呼ばれる
close() 二回目 -> 例外なし
```

## unsupported feature tests

```text
keyboard("abc") -> NotImplementedError
type_key(KeyCode("a")) -> NotImplementedError
touch_down(100, 100) -> NotImplementedError
disable_sleep(True) -> NotImplementedError
ThreeDSButton を含む press -> UnsupportedSwbtInputError
TouchState を含む press -> UnsupportedSwbtInputError
```

## service tests

`SwitchGamepad` の fake を注入できるよう、service 内部で作成関数を受け取ります。

```python
class FakeSwitchGamepad:
    def __init__(self) -> None:
        self.opened = False
        self.connected = False
        self.closed = False
        self.states: list[InputState] = []

    async def open(self) -> None:
        self.opened = True

    async def connect(self, *, timeout: float | None, allow_pairing: bool) -> None:
        self.connected = True

    async def apply(self, state: InputState) -> None:
        self.states.append(state)

    async def neutral(self) -> None:
        self.states.append(InputState.neutral())

    async def close(self, *, neutral: bool = True) -> None:
        self.closed = True
```

service test の観点:

```text
start() が open -> connect の順で呼ぶ
allow_pairing が設定どおり渡る
apply() が event loop thread 上で実行される
close() が close(neutral=True) を呼ぶ
TransportOpenError が ConfigurationError へ変換される
ConnectionTimeoutError が ConfigurationError へ変換される
close 後の apply が DeviceError になる
```

## runtime builder tests

設定ごとに `MacroRuntimeBuilder` へ渡される controller factory を確認します。

```text
controller.backend 未指定 -> serial factory
controller.backend="serial" -> SerialControllerOutputPortFactory
controller.backend="swbt" -> SwbtControllerOutputPortFactory
CLI override --controller swbt -> serial protocol を生成せず swbt factory
CLI override --controller serial -> --serial が必須
CLI override --controller swbt -> --serial は不要
allow_dummy=True + swbt open 失敗 -> DummySwbtGamepadService
allow_dummy=False + swbt open 失敗 -> ConfigurationError
```

`MacroRuntime` の実行テストでは、簡単なマクロを使います。

```python
class PressAMacro(MacroBase):
    def run(self, cmd: Command) -> None:
        cmd.press(Button.A, dur=0.01, wait=0.01)
```

期待:

```text
DummySwbtGamepadService に A 押下 state と neutral state が入る
Command / MacroRuntime / ExecutionContext が swbt を import しない
```

## realdevice tests

実機テストは既存の `realdevice` marker を使うか、swbt 用 marker を追加します。

```toml
[tool.pytest.ini_options]
markers = [
    "realdevice: tests requiring real hardware devices",
    "swbt: tests requiring swbt-compatible Bluetooth HID setup",
]
```

実行例:

```console
uv run pytest tests -m "not realdevice and not swbt"
uv run pytest tests -m swbt --bt-adapter usb:0 --bt-key-store .nyxpy/swbt/test-switch.json
```

実機テストの内容:

```text
swbt-probe adapters --json で adapter が見える
allow_pairing=true で初回 pairing が成功する
allow_pairing=false で保存済み bond reconnect が成功する
Button.A が対象機器側に反映される
D-pad が反映される
left / right stick が反映される
close 後に入力が残らない
```

入力反映の自動判定は難しいため、初期段階では人手確認を含めます。trace の `report_tx`、`connected`、`disconnected` を補助証跡として保存します。

## 段階導入

### Phase 1: 内部構造

- `ControllerOutputPortFactory` を `SerialControllerOutputPortFactory` へ改名する。
- 互換 alias は残さない。呼び出し元とテストを同じ変更で正 API へ更新する。
- `make_controller_port_factory()` を追加する。
- 既存 serial backend のテストを通す。

### Phase 2: swbt backend 最小実装

- optional dependency `swbt` を追加する。
- `SwbtGamepadConfig`、`SwbtGamepadService`、`SwbtControllerOutputPort` を追加する。
- button / hat / stick の mapper を追加する。
- CLI から `--controller swbt` を選べるようにする。
- swbt backend では `--serial` を不要にし、serial backend では `--serial` を必須にする。
- swbt backend では `ProtocolFactory.resolve_baudrate()` と `create_protocol()` が呼ばれないことをテストする。
- dummy service を使った runtime integration test を追加する。

### Phase 3: pairing / reconnect UX

- `--bt-pair`、`--bt-adapter`、`--bt-key-store` を追加する。
- GUI に backend 選択と adapter refresh を追加する。
- reconnect 失敗時に no bond / timeout / invalid key store を分けて表示する。
- diagnostics trace を保存できるようにする。

### Phase 4: 実機検証

- Windows + 専用 USB Bluetooth dongle で pairing / reconnect を確認する。
- macOS は experimental として adapter open / reconnect を確認する。
- Linux は未確認なら docs に未確認と明記する。
- stick Y 軸向きを確認し、`invert_stick_y` の既定値を確定する。

## 完了条件

```text
既存 serial backend の挙動が変わらない
既存マクロが swbt backend でも同じ Command API で動く
Command / MacroRuntime が swbt を import していない
SerialProtocolInterface / ProtocolFactory に swbt が入っていない
swbt なし install で serial backend が動く
swbt extra install で swbt backend が選べる
close / cancellation / failure で neutral が試みられる
unsupported feature が silent failure にならない
```

## リスク

| リスク | 対策 |
|---|---|
| swbt state update API が即時送信を保証しない | NyXPy port 契約では周期 report 反映とし、厳密な即時送信が必要なら swbt-python に public flush を追加する |
| adapter 名が環境で変わる | GUI / CLI で `swbt-probe adapters --json` を案内する |
| key store に複数 current peers が入る | 対象機器ごとに key store を分け、`InvalidKeyStoreError` を明示表示する |
| GUI lifetime と runtime close が競合する | factory が service を所有し、port close は neutral、factory close は完全終了に分ける |
| serial 既存設定との互換性 | `serial_device` / `serial_baud` を読み続け、新 schema へ正規化する |
| swbt 依存が通常 install を重くする | optional dependency にする |
| manual input と runtime が同じ service を更新する | GUI は実行中の manual input を無効化し、runtime port 作成時に neutral へ揃える |
| diagnostics path 変更が cached service に反映されない | `diagnostics_path` を service key に含め、変更時に builder を再生成する |

## 未確定事項

| 項目 | 決める方法 |
|---|---|
| stick Y 軸の既定 | 実機で上方向、下方向を確認する |
| `close()` で完全 disconnect するか | 決定済み。port close は neutral のみ、完全 disconnect は factory close |
| diagnostics の既定保存先 | CLI は未指定なら無効。GUI は固定 path または無効を既定にし、run artifact 連携は別 PR で決める |
| swbt public flush の要否 | `press` duration が短いマクロで実機確認し、必要なら swbt-python 側へ追加する |
