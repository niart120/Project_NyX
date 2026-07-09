# 設定、依存関係、CLI、GUI

この文書は、swbt backend を利用者が選べるようにするための設定形式、optional dependency、CLI command、GUI 項目を定義する。

設定 model、controller 種別 model、adapter refresh は `nyxpy.framework.core.hardware.swbt` package に置く。

## optional dependency

`swbt-python` は optional dependency として追加する。serial backend だけを使う利用者に Bluetooth / Bumble / libusb 周りの依存を強制しないためである。

```toml
[project.optional-dependencies]
swbt = [
    "swbt-python>=0.2.0,<0.3.0",
]
```

開発環境で swbt backend を有効にするコマンド:

```console
uv sync --extra swbt
```

利用者が tool install する場合:

```console
uv tool install "nyxpy-fw[swbt]"
```

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
operation_timeout_sec = 5.0
report_period_us = 8000
reset_on_port_create = true
```

`controller_type` は `pro-controller`、`joy-con-l`、`joy-con-r` のいずれか。settings parser で `SwbtControllerType` に parse し、`SwbtControllerModel` に変換する。

`key_store_path` は pairing key file である。controller type ごとに分ける。

```text
.nyxpy/swbt/pro-controller-bond.json
.nyxpy/swbt/joy-con-l-bond.json
.nyxpy/swbt/joy-con-r-bond.json
```

## CLI

追加する CLI:

```console
nyxpy swbt adapters [--json]
nyxpy swbt pair --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
nyxpy swbt reconnect --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
```

run option:

```console
nyxpy run sample_macro --controller swbt --swbt-adapter usb:0 --swbt-controller-type pro-controller
```

CLI は GUI 連携用の command copy や clipboard 出力を持たない。

## GUI 項目

GUI swbt panel に置く項目:

| 項目 | 必須 | 内容 |
|---|---:|---|
| backend selector | yes | serial / swbt |
| controller type | yes | Pro Controller / Joy-Con L / Joy-Con R |
| adapter combo | yes | `list_adapters()` の結果 |
| refresh adapters | yes | adapter 列挙だけ行う |
| key store path | yes | pairing key JSON path |
| pair button | yes | 明示 pairing |
| reconnect button | yes | 保存済み key で reconnect |
| disconnect button | yes | GUI lifetime port を release/close |
| connection status | yes | disconnected / pairing / connected / error |

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
| Refresh adapters | not macro running | combo を更新 | error 表示 |
| Pair | adapter + controller type + key store selected | status connected、manual controller を注入 | error 表示、controller `None` |
| Reconnect | adapter + controller type + key store selected | status connected、manual controller を注入 | error 表示、controller `None` |
| Disconnect | connected | `release()` 後に `close()`、controller `None` | error log、controller `None` |
| Macro run start | not pairing/reconnecting | GUI lifetime port を close して runtime start | close 失敗時は実行を止める |

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
| `controller.swbt.adapter` | non-empty。未指定時は adapter 候補数に基づき解決 |
| `controller.swbt.key_store_path` | `Path`。親 directory は pair 前に作成 |
| `connect_timeout_sec` | `> 0` |
| `operation_timeout_sec` | `> 0` |
| `report_period_us` | `None` or `> 0` |

## error display

| code | 表示 |
|---|---|
| `NYX_SWBT_DEPENDENCY_MISSING` | swbt extra の導入を促す |
| `NYX_SWBT_ADAPTER_DISCOVERY_FAILED` | adapter discovery failed |
| `NYX_SWBT_ADAPTER_NOT_SELECTED` | adapter を選択させる |
| `NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED` | controller type を選択させる |
| `NYX_SWBT_KEY_STORE_INVALID` | key store path を確認させる |
| `NYX_SWBT_CONNECTION_TIMED_OUT` | target device の pairing/reconnect 操作を確認させる |
| `NYX_SWBT_CONNECTION_FAILED` | connection failed |
| `NYX_SWBT_INPUT_UNSUPPORTED` | 選択 controller type ではその入力を扱えない |
