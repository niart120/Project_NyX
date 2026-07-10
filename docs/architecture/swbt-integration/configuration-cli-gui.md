# 設定、依存関係、CLI、GUI

この文書は、swbt backend を利用者が選べるようにするための設定形式、依存関係、CLI command、GUI 項目を定義する。

設定 model、controller 種別 model、adapter refresh は `nyxpy.framework.core.hardware.swbt` package に置く。

## 依存関係

`swbt-python>=0.2.0,<0.3.0` は通常依存として追加する。`[project.optional-dependencies].swbt` は作らない。

NyX はすでに serial backend のために PySerial を通常依存として持つ。swbt backend も controller backend の正式な選択肢として扱い、利用者に swbt 用の extra 指定や追加同期手順を要求しない。

## settings

serial backend:

```toml
[controller]
backend = "serial"

[controller.serial]
device = "COM3"
protocol = "CH552"
baudrate = 9600
```

swbt backend:

```toml
[controller]
backend = "swbt"

[controller.swbt]
controller_type = "pro-controller"
adapter = "usb:0"
key_store_path = ".nyxpy/swbt/pro-controller-bond.json"
connect_timeout_sec = 30.0
report_period_us = 8000
```

`controller.backend` は `serial` または `swbt` を指定する。capture backend / capture source とは独立して扱う。

`controller_type` は `pro-controller`、`joy-con-l`、`joy-con-r` のいずれか。settings parser で `SwbtControllerType` に parse し、`SwbtControllerModel` に変換する。

`adapter` は swbt が開く USB Bluetooth adapter 名である。空文字または未指定のまま pair / reconnect / run を試みた場合は、候補数に関係なく `NYX_SWBT_ADAPTER_NOT_SELECTED` とする。adapter 候補が 1 件だけでも自動採用しない。

`key_store_path` は pairing key file である。明示されない場合は controller type ごとに `.nyxpy/swbt/<controller>-bond.json` を使う。

```text
.nyxpy/swbt/pro-controller-bond.json
.nyxpy/swbt/joy-con-l-bond.json
.nyxpy/swbt/joy-con-r-bond.json
```

`connect_timeout_sec` は接続操作ごとの timeout である。`report_period_us` は swbt report loop の周期で、既定値は `8000`、値は `None` または正の整数に限る。

`operation_timeout_sec` と `reset_on_port_create` は settings に出さない。operation timeout は session / factory の内部既定値とし、port 作成時の neutral は常に試みる。

## CLI

追加する CLI:

```console
nyxpy swbt adapters [--json]
nyxpy swbt pair [--adapter usb:0] [--controller-type pro-controller] [--key-store .nyxpy/swbt/pro-controller-bond.json]
nyxpy swbt reconnect [--adapter usb:0] [--controller-type pro-controller] [--key-store .nyxpy/swbt/pro-controller-bond.json]
nyxpy swbt disconnect [--adapter usb:0] [--controller-type pro-controller] [--key-store .nyxpy/swbt/pro-controller-bond.json]
```

`pair`、`reconnect`、`disconnect` は workspace settings を読み、CLI option が指定された場合だけ上書きする。解決後に adapter が空なら `NYX_SWBT_ADAPTER_NOT_SELECTED` とする。`key_store_path` が未指定なら controller type から既定値を補う。

run option:

```console
nyxpy run sample_macro --controller swbt --swbt-adapter usb:0 --swbt-controller-type pro-controller
```

`--controller serial|swbt` は controller backend の選択だけを扱う。capture backend / capture source の選択とは独立している。

`--serial` と `--capture` は parser 上の必須 option にしない。未指定時は settings に fallback し、解決後の設定を検証する。

`nyxpy swbt status` は初期範囲外である。`disconnect` は同一 process の factory-managed cached session を閉じる操作であり、別 process や OS、Switch 側の接続状態までは保証しない。

CLI は GUI 連携用の command copy や clipboard 出力を持たない。

## GUI 項目

GUI swbt panel に置く項目:

| 項目 | 必須 | 内容 |
|---|---:|---|
| controller backend selector | yes | serial / swbt |
| controller type | yes | Pro Controller / Joy-Con L / Joy-Con R |
| adapter combo | yes | `list_adapters()` の結果 |
| refresh adapters | yes | adapter 列挙だけ行う |
| key store path | yes | pairing key JSON path |
| pair button | yes | 明示 pairing |
| reconnect button | yes | 保存済み key で reconnect |
| disconnect button | yes | GUI lifetime port を release/close し、factory-managed session を disconnect |
| connection status | yes | factory-managed cached session の状態表示 |

capture backend / capture source の選択 UI は controller backend と独立させる。controller backend を変更しても preview frame source は再作成しない。capture backend を変更しても manual controller port は再作成しない。

GUI に置かない項目:

- CLI command preview
- clipboard copy
- CLI history 連携
- diagnostics editor
- diagnostics folder open button
- controller color editor
- auto pairing suggestion
- IMU preset / pose / raw editor
- IMU recorder / replay

## GUI operation

| operation | enabled when | success | failure |
|---|---|---|---|
| Refresh adapters | macro 未実行中 | combo を更新。settings は変更しない | error 表示 |
| Pair | backend `swbt`、adapter、controller type、key store が有効 | status connected、manual controller を注入 | controller `None`、error 表示 |
| Reconnect | backend `swbt`、key store が存在 | status connected、manual controller を注入 | controller `None`、error 表示 |
| Disconnect | connected | `release()` 後に `close()`、factory session を閉じ、controller `None` | error log、controller `None` |
| Macro run start | not pairing/reconnecting | `VirtualControllerModel.set_controller(None)` 後に旧 manual port を release/close して runtime start | close 失敗時は実行を止める |

## GUI manual input

GUI manual input は既存仮想コントローラー UI で行う。

```text
VirtualControllerModel
  -> ControllerOutputPort
  -> SwbtControllerOutputPort
```

GUI view model は `SwbtControllerSession` や `InputState` を直接扱わない。

## Settings validation

| field | validation |
|---|---|
| `controller.backend` | `serial` or `swbt` |
| `controller.swbt.controller_type` | `resolve_controller_model(...)` で解決できる |
| `controller.swbt.adapter` | 保存時は空を許容する。接続操作時に空なら `NYX_SWBT_ADAPTER_NOT_SELECTED` |
| `controller.swbt.key_store_path` | `Path | None`。`None` なら controller type から既定値を補う。親 directory は pair 前に作成 |
| `connect_timeout_sec` | `> 0` |
| `report_period_us` | `None` or `> 0` |

旧 flat key の `serial_device`、`serial_baud`、`serial_protocol` は廃止する。settings parser は新しい `[controller.serial]` を正とし、旧 key への fallback は持たない。

## error display

| code | 表示 |
|---|---|
| `NYX_SWBT_ADAPTER_DISCOVERY_FAILED` | adapter discovery failed |
| `NYX_SWBT_ADAPTER_NOT_SELECTED` | adapter を選択させる |
| `NYX_SWBT_ADAPTER_NOT_FOUND` | 選択 adapter が見つからない |
| `NYX_SWBT_ADAPTER_AMBIGUOUS` | adapter alias が複数候補に一致している |
| `NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED` | controller type を選択させる |
| `NYX_SWBT_KEY_STORE_INVALID` | key store path を確認させる |
| `NYX_SWBT_CONNECTION_TIMED_OUT` | target device の pairing/reconnect 操作を確認させる |
| `NYX_SWBT_CONNECTION_FAILED` | connection failed |
| `NYX_SWBT_INPUT_UNSUPPORTED` | 選択 controller type ではその入力を扱えない |
| `NYX_SWBT_INPUT_INVALID` | 入力値または型が不正 |
| `NYX_IMU_FRAME_COUNT_INVALID` | IMU frame 数が 1 または 3 ではない |
