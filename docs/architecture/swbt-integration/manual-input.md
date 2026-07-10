# GUI 仮想コントローラー manual input

GUI の仮想コントローラー manual input は、既存の `VirtualControllerPane` / `VirtualControllerModel` を使う。swbt 対応のために GUI 専用の `SwbtManualInputSession` は追加しない。

## 現行経路を維持する

```text
ControllerButton / AnalogStick / DPad
  -> Qt signal
  -> VirtualControllerPane
  -> VirtualControllerModel
  -> ControllerOutputPort
```

backend は `ControllerOutputPort` の下で差し替える。

```text
VirtualControllerModel
  -> ControllerOutputPort
       ├─ SerialControllerOutputPort
       └─ SwbtControllerOutputPort
```

この構造により、GUI model は serial / swbt / dummy を知らない。

## 入力対象

manual input で扱うもの:

- button down / up
- D-pad direction
- left stick
- right stick
- release all

manual input で扱わないもの:

- IMU preset gesture
- IMU pose editor
- IMU raw frame editor
- IMU recorder / replay
- CLI command 生成
- clipboard copy
- diagnostics editor
- controller color editor

## port 注入

settings apply または reconnect 成功後、GUI app service は runtime builder から GUI lifetime controller を取得し、model に差し込む。

```text
GuiAppServices.apply_settings(...)
  -> builder.controller_output_for_manual_input()
  -> MainWindow._apply_runtime_ports(...)
  -> VirtualControllerModel.set_controller(port)
```

swbt backend の場合、その port は `SwbtControllerOutputPort` である。GUI は具象型を見ない。

失敗時は `None` を入れる。

```python
virtual_controller.model.set_controller(None)
```

controller が `None` の間、GUI 操作は送信されない。

## 操作 mapping

| GUI 操作 | `VirtualControllerModel` | `ControllerOutputPort` |
|---|---|---|
| button press | `button_press(button)` | `press((button,))` |
| button release | `button_release(button)` | `release((button,))` |
| D-pad direction | `set_hat_direction(hat)` | previous release + new press |
| left stick | `set_left_stick(angle, strength)` | `press((LStick(...),))` or release previous |
| right stick | `set_right_stick(angle, strength)` | `press((RStick(...),))` or release previous |
| release all | GUI action | `release()` |

swbt backend は `ControllerOutputPort` の下で `InputState` を再構築する。

## connection state

GUI manual input は connected controller port がある時だけ有効にする。

| 状態 | GUI manual input |
|---|---|
| no adapter selected | disabled |
| adapter listed only | disabled |
| pairing in progress | disabled |
| reconnect in progress | disabled |
| connected / port available | enabled |
| macro running | disabled |
| disconnected / error | disabled |

## macro runtime との排他

macro start 前に GUI lifetime port を閉じる。

```text
macro start requested
  -> virtual_controller.model.set_controller(None)
  -> virtual_controller.model.reset_state()
  -> builder.discard_manual_controller(previous port)
  -> previous manual port.release()
  -> previous manual port.close()
  -> macro runtime start
```

runtime 終了後、自動で再接続しない。利用者が reconnect を押した場合だけ GUI lifetime port を再作成する。

backend factory も同じ排他を守る。swbt backend では、同じ session key に対して新しい `SwbtControllerOutputPort` を作る前に旧 active port を close する。GUI 上位層の macro start sequence だけに依存せず、backend 内にも「有効な入力 port は 1 つだけ」という制約を置く。

## IMU の扱い

GUI manual input には IMU 操作 UI を置かない。

IMU は programmatic command として扱う。

```text
Command.imu(...)
  -> ControllerOutputPort.imu(...)
  -> SwbtControllerOutputPort.imu(...)
```

GUI manual input から IMU を変更しないため、`VirtualControllerModel` に IMU state を持たせない。

## error handling

| case | 動作 |
|---|---|
| controller is `None` | no-op |
| port operation fails | error log、controller を `None` に戻すか reconnect を促す |
| unsupported input | user-visible error + technical log |
| macro running | input widgets disabled |
| reconnect lost | input widgets disabled |

silent no-op は controller 未設定時だけ許容する。接続済み port が error を返した場合は明示的に表示する。
