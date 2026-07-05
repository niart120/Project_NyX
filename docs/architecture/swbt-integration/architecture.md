# レイヤードアーキテクチャ上の配置

`swbt-python` 連携は、NyXPy の既存レイヤーに沿って配置します。マクロから見える抽象は `Command` と `ControllerOutputPort` で止め、Bluetooth HID の詳細は `hardware` 層へ閉じ込めます。

## 既存レイヤー

NyXPy の controller 出力に関係する既存の責務は次のように分かれています。

```text
macro
  MacroBase / Command
  マクロ作者が触る API

runtime
  ExecutionContext / MacroRuntime / MacroRuntimeBuilder
  実行単位の依存関係を組み立て、Command へ context を渡す

io
  ControllerOutputPort / FrameSourcePort / NotificationPort
  runtime が依存する port と port adapter

hardware
  SerialProtocolInterface / SerialComm / capture device / discovery
  実デバイス、外部ライブラリ、通信方式に近い処理

cli / gui
  ユーザー入力、設定編集、実行開始、manual input
```

`ControllerOutputPort` は、runtime が controller 入力を送るための port です。`SerialControllerOutputPort` は `SerialProtocolInterface` で bytes を作り、`SerialComm` へ送る adapter です。

## swbt 連携後の配置

追加後は次の構造にします。

```text
macro.Command
  ↓
runtime.ExecutionContext.controller
  ↓
io.ports.ControllerOutputPort
  ├─ io.adapters.SerialControllerOutputPort
  └─ io.swbt_adapter.SwbtControllerOutputPort
        ↓
hardware.swbt_gamepad.SwbtGamepadService
        ↓
swbt.SwitchGamepad
        ↓
Bumble HID transport
```

`SwbtControllerOutputPort` は NyXPy の port 契約を満たす adapter です。Bluetooth adapter の open、pairing、reconnect、async event loop、diagnostics trace は `SwbtGamepadService` が担当します。

## 置くファイル

推奨する追加・変更ファイルは次です。

```text
src/nyxpy/framework/core/io/ports.py
  ControllerOutputPort                    # 変更しない

src/nyxpy/framework/core/io/adapters.py
  SerialControllerOutputPort              # 既存。移動しない場合はそのまま

src/nyxpy/framework/core/io/swbt_adapter.py
  SwbtControllerOutputPort                # 新規

src/nyxpy/framework/core/hardware/swbt_gamepad.py
  SwbtGamepadService                      # 新規
  SwbtGamepadConfig                       # 新規
  SwbtConnectionError                     # 新規

src/nyxpy/framework/core/hardware/swbt_mapper.py
  NyxSwbtInputMapper                      # 新規
  NyX KeyType → swbt InputState 変換

src/nyxpy/framework/core/io/device_factories.py
  SerialControllerOutputPortFactory       # 既存 ControllerOutputPortFactory を改名
  SwbtControllerOutputPortFactory         # 新規

src/nyxpy/framework/core/runtime/builder.py
  make_controller_port_factory            # 新規関数、または create_device_runtime_builder 内の分岐

src/nyxpy/framework/core/settings/schema.py
  controller.backend
  controller.serial.*
  controller.swbt.*
```

`SerialControllerOutputPort` を `io/adapters.py` から分割するかどうかは別判断です。最小変更では既存位置のままにし、`SwbtControllerOutputPort` だけ `io/swbt_adapter.py` に置きます。

`ControllerOutputPortFactory` の改名では互換 alias を残しません。呼び出し元、テスト、公開 export を同じ変更で `SerialControllerOutputPortFactory` へ更新します。

## 依存方向

守る依存方向は次です。

```text
cli / gui
  ↓
runtime builder
  ↓
io factory
  ↓
io adapter
  ↓
hardware service
  ↓
swbt-python
```

マクロ側は次で止めます。

```text
macro
  ↓
Command
  ↓
ControllerOutputPort
```

`macro`、`DefaultCommand`、`ExecutionContext`、`MacroRuntime` から `swbt` を import しません。

## SerialProtocolInterface に入れない理由

`SerialProtocolInterface` は controller 入力をシリアル送信用 bytes に変換するための protocol です。`swbt-python` は Bluetooth HID の resource lifecycle と input report loop を持つため、ここへ入れると抽象の意味が変わります。

避ける実装:

```python
class SwbtSerialProtocol(SerialProtocolInterface):
    ...
```

```python
ProtocolFactory.create_protocol("SWBT")
```

採用する実装:

```python
class SwbtControllerOutputPort(ControllerOutputPort):
    ...
```

```python
def make_controller_port_factory(config: ControllerConfig) -> PortFactory[ControllerOutputPort]:
    ...
```

## import policy

`swbt-python` の公開 API は `swbt` module root から import します。`swbt.gamepad.*` や `swbt.transport.*` の deep import は、NyXPy 側ではテスト用 fake か transport 差し替えが必要な場合だけに限定します。

推奨:

```python
from swbt import Button, DiagnosticsConfig, InputState, Stick, SwitchGamepad
```

避ける:

```python
from swbt.gamepad.core import SwitchGamepad
from swbt.transport._bumble_transport import ...
```

## レイヤー違反になりやすい実装

次の実装は避けます。

```python
# Command が外部ライブラリを知る
from swbt import SwitchGamepad

class DefaultCommand:
    ...
```

```python
# ControllerOutputPort が backend 選択を毎回行う
class DispatchingControllerOutputPort(ControllerOutputPort):
    def press(self, keys):
        if self.backend == "serial":
            self.serial.press(keys)
        else:
            self.swbt.press(keys)
```

```python
# GUI が直接 Bluetooth HID 接続を開始する
pad = SwitchGamepad(adapter="usb:0", key_store_path="switch-bond.json")
await pad.connect(timeout=30.0, allow_pairing=True)
```

GUI / CLI は設定値とユーザー操作を runtime builder へ渡します。接続手順は factory と hardware service に閉じ込めます。
