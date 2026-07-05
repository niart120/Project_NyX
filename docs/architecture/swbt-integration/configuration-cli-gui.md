# 設定、依存関係、CLI、GUI

この文書は、swbt backend を利用者が選べるようにするための設定形式、依存関係、CLI option、GUI 項目を定義します。

## 依存関係

`swbt-python` は optional dependency として追加します。serial backend だけを使う利用者に Bluetooth / Bumble / libusb 周りの依存を強制しないためです。

```toml
[project.optional-dependencies]
swbt = [
    "swbt-python>=0.1.1,<0.2.0",
]
```

既存の Project_NyX は Python `>=3.12,<3.14`、`swbt-python` は Python `>=3.12` です。Python version 条件は衝突しません。

開発環境で swbt 連携を有効にするコマンド:

```console
uv sync --extra swbt
```

利用者が tool install する場合:

```console
uv tool install "nyxpy-fw[swbt]"
```

## settings schema

既存の `serial_device` / `serial_baud` / `serial_protocol` は、既存 workspace の読み込み元として扱います。新しい設定では controller backend を明示します。

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
adapter = "usb:0"
key_store_path = ".nyxpy/swbt/switch-bond.json"
connect_timeout_sec = 30.0
allow_pairing = false
report_period_us = 8000
device_name = "Pro Controller"
diagnostics_path = "logs/swbt-trace.jsonl"
connect_on_open = true
invert_stick_y = false
```

`adapter = "usb:0"` は例です。実際の adapter 名は `swbt-probe adapters --json` で確認します。

## schema field 案

```python
SettingField("controller.backend", str, "serial", choices=("serial", "swbt"))

SettingField("controller.serial.device", (str, type(None)), None)
SettingField("controller.serial.protocol", str, "CH552")
SettingField("controller.serial.baudrate", int, 9600)

SettingField("controller.swbt.adapter", str, "usb:0")
SettingField("controller.swbt.key_store_path", (str, type(None)), ".nyxpy/swbt/switch-bond.json")
SettingField("controller.swbt.connect_timeout_sec", float, 30.0)
SettingField("controller.swbt.allow_pairing", bool, False)
SettingField("controller.swbt.report_period_us", int, 8000)
SettingField("controller.swbt.device_name", str, "Pro Controller")
SettingField("controller.swbt.diagnostics_path", (str, type(None)), None)
SettingField("controller.swbt.connect_on_open", bool, True)
SettingField("controller.swbt.invert_stick_y", bool, False)
```

`report_period_us` は正の整数として追加検証します。`connect_timeout_sec` は `0` より大きい値にします。

## 既存設定からの正規化

既存 workspace の設定を壊さないため、次の正規化を runtime builder の手前で行います。

```python
def controller_config_from_settings(settings: Mapping[str, object]) -> ControllerConfig:
    backend = dotted_get(settings, "controller.backend", None)
    if backend is None:
        backend = "serial"

    if backend == "serial":
        return SerialControllerConfig(
            device=str(dotted_get(settings, "controller.serial.device", settings.get("serial_device")) or "") or None,
            protocol=str(dotted_get(settings, "controller.serial.protocol", settings.get("serial_protocol", "CH552"))),
            baudrate=int(dotted_get(settings, "controller.serial.baudrate", settings.get("serial_baud", 9600))),
        )

    if backend == "swbt":
        return SwbtControllerConfig(
            adapter=str(dotted_get(settings, "controller.swbt.adapter", "usb:0")),
            key_store_path=_optional_path(dotted_get(settings, "controller.swbt.key_store_path", ".nyxpy/swbt/switch-bond.json")),
            connect_timeout_sec=float(dotted_get(settings, "controller.swbt.connect_timeout_sec", 30.0)),
            allow_pairing=bool(dotted_get(settings, "controller.swbt.allow_pairing", False)),
            report_period_us=int(dotted_get(settings, "controller.swbt.report_period_us", 8000)),
            device_name=str(dotted_get(settings, "controller.swbt.device_name", "Pro Controller")),
            diagnostics_path=_optional_path(dotted_get(settings, "controller.swbt.diagnostics_path", None)),
            connect_on_open=bool(dotted_get(settings, "controller.swbt.connect_on_open", True)),
            invert_stick_y=bool(dotted_get(settings, "controller.swbt.invert_stick_y", False)),
        )

    raise ConfigurationError(
        f"unsupported controller backend: {backend}",
        code="NYX_CONTROLLER_BACKEND_UNSUPPORTED",
        component="ControllerSettings",
        details={"backend": str(backend)},
    )
```

## CLI option

CLI は controller backend を serial protocol 生成より前に決定します。`--controller swbt` の場合、`ProtocolFactory.resolve_baudrate()` と `create_protocol()` は呼びません。

serial backend の通常実行:

```console
nyxpy run sample_macro --controller serial --serial COM3 --capture Camera1
```

swbt backend の通常実行:

```console
nyxpy run sample_macro --controller swbt --bt-adapter usb:0 --capture Camera1
```

初回 pairing:

```console
nyxpy run sample_macro --controller swbt --bt-adapter usb:0 --bt-pair --capture Camera1
```

key store 指定:

```console
nyxpy run sample_macro   --controller swbt   --bt-adapter usb:0   --bt-key-store .nyxpy/swbt/switch-main.json   --capture Camera1
```

追加する CLI option:

| option | 対応設定 | 既定値 |
|---|---|---|
| `--controller serial|swbt` | `controller.backend` | `serial` |
| `--serial TEXT` | `controller.serial.device` | serial backend では必須。swbt backend では不要 |
| `--protocol TEXT` | `controller.serial.protocol` | `CH552`。serial backend 専用 |
| `--baud INT` | `controller.serial.baudrate` | protocol 既定値。serial backend 専用 |
| `--capture TEXT` | capture source 設定 | 実行時に frame source を使うため必須 |
| `--bt-adapter TEXT` | `controller.swbt.adapter` | `usb:0` |
| `--bt-pair` | `controller.swbt.allow_pairing` | `false` |
| `--bt-key-store PATH` | `controller.swbt.key_store_path` | `.nyxpy/swbt/switch-bond.json` |
| `--bt-timeout FLOAT` | `controller.swbt.connect_timeout_sec` | `30.0` |
| `--bt-diagnostics PATH` | `controller.swbt.diagnostics_path` | 未指定 |

CLI option は設定ファイルより優先します。`--serial` は swbt backend では不要です。serial backend のときだけ必須にし、swbt backend で未指定でも parse error にしません。

## GUI 項目

GUI では controller 設定に次を追加します。

```text
Controller backend
  - Serial
  - Bluetooth HID / swbt

Serial settings
  - Protocol
  - Serial device
  - Baudrate

swbt settings
  - Adapter
  - Key store path
  - Connect timeout seconds
  - Pairing mode
      - reconnect only
      - allow pairing once
  - Diagnostics trace path
  - Invert stick Y
```

GUI の操作ボタン:

```text
Refresh adapters
Pair once
Reconnect
Disconnect
Open diagnostics folder
```

`Refresh adapters` は `swbt-probe adapters --json` を subprocess で呼ぶ実装から始めます。このコマンドは adapter 一覧確認用であり、対象機器への pairing、HID advertising、report loop は開始しません。

GUI と runtime は同じ `SwbtGamepadService` 接続を共有します。GUI の manual input とマクロ実行で接続を作り直さず、`SwbtControllerOutputPortFactory` が service lifetime を所有します。backend を serial から swbt、または swbt から serial へ切り替えた場合は runtime builder を再生成し、古い factory を shutdown して transport を閉じます。

## hardware guide へのリンク

swbt backend の設定画面には、次の注意を表示します。

```text
swbt backend は PC の標準 Bluetooth 機能ではなく、Bumble から直接開く専用 USB Bluetooth dongle を使います。
Windows では WinUSB / libwdi driver、Linux / macOS では libusb と USB access の準備が必要です。
```

詳細は swbt-python の Hardware Guide へリンクします。

```text
https://niart120.github.io/swbt-python/hardware/
```

## diagnostics path の保存先

CLI で `--bt-diagnostics` が未指定の場合、既定では trace を出しません。トラブルシューティング時だけ有効にします。

GUI では run artifact 配下へ保存する option を用意できます。

```text
resources/<macro_id>/artifacts/<run_artifact_dir>/logs/swbt-trace.jsonl
```

ただし `SwbtGamepadService` は runtime artifact store へ直接依存しません。diagnostics path は構成起点で解決してから service config に渡します。

GUI と runtime で接続を共有する場合、`diagnostics_path` は service lifetime に紐づきます。実行ごとの artifact directory へ trace を必ず分けたい場合は、run 開始前に builder を再生成するか、diagnostics writer を service から切り離す設計を別途入れます。初期実装では、CLI は明示された `--bt-diagnostics` の path だけへ出力し、GUI は固定 path または diagnostics 無効を既定にします。
