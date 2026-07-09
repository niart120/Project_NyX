# デバイス列挙

adapter 列挙は `swbt.list_adapters()` を使う。これは Bluetooth adapter の候補を返す API であり、controller の open、advertising、pairing、reconnect、HID report loop は開始しない。

`SwbtAdapterDiscoveryService` の実装 module は `nyxpy.framework.core.hardware.swbt.discovery` である。

## 基本 API

```python
from swbt import AdapterInfo, list_adapters

adapters: tuple[AdapterInfo, ...] = list_adapters()
for adapter in adapters:
    print(adapter.name, adapter.aliases)
```

戻り値は `AdapterInfo` の tuple。候補がない場合は空 tuple。列挙自体に失敗した場合は `AdapterDiscoveryError` を Project_NyX 側で `NYX_SWBT_ADAPTER_DISCOVERY_FAILED` に変換する。

## `AdapterInfo` の扱い

Project_NyX では次の情報を表示と validation に使う。

| field | 用途 |
|---|---|
| `name` | swbt controller の `adapter=` に渡せる代表名 |
| `aliases` | 同じ adapter を指す候補名 |
| `vendor_id` / `product_id` | デバイス識別と表示 |
| `manufacturer` / `product` | GUI / CLI 表示 |
| `serial_number` | 識別補助 |
| `bus_number` / `device_address` / `port_numbers` | デバッグ表示 |
| `is_bluetooth_hci` | Bluetooth HCI adapter として認識されたかの表示 |

## Project_NyX DTO

CLI と GUI は `swbt.AdapterInfo` をそのまま外へ出さず、Project_NyX の DTO に変換する。

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SwbtAdapterView:
    name: str
    aliases: tuple[str, ...]
    display_name: str
    vendor_id: int | None
    product_id: int | None
    manufacturer: str | None
    product: str | None
    serial_number: str | None
    bus_number: int | None
    device_address: int | None
    port_numbers: tuple[int, ...]
    is_bluetooth_hci: bool
```

`display_name` は短い表示名でよい。

```text
usb:0 — ASUS USB-BT500 (VID:PID 0b05:190e)
```

## 保存値の選択

設定値としては `AdapterInfo.name` を基本にする。`aliases` は validation と表示補助に使う。

| 状況 | 扱い |
|---|---|
| selected adapter が `name` に一致 | その adapter を採用 |
| selected adapter が `aliases` に一致 | 対応する `name` へ解決し、保存値も `name` に正規化する |
| adapter が空文字または未指定 | 候補数に関係なく `NYX_SWBT_ADAPTER_NOT_SELECTED` |
| selected adapter がどの `name` / `aliases` にも一致しない | `NYX_SWBT_ADAPTER_NOT_FOUND` |
| 複数候補が同じ alias に一致 | `NYX_SWBT_ADAPTER_AMBIGUOUS` |

候補が 1 件だけの場合でも adapter 未指定を自動採用しない。pair / reconnect / run は、利用者が settings または CLI / GUI で adapter を選んだ後に実行する。

## CLI

```console
nyxpy swbt adapters
nyxpy swbt adapters --json
```

`--json` は GUI 連携用ではなく、developer / automation 用の machine-readable output として扱う。GUI は Python API を直接呼ぶ。

## GUI

GUI の adapter refresh button は `SwbtAdapterDiscoveryService.list()` を呼ぶだけである。pairing や reconnect は開始しない。

```text
[Refresh adapters]
  -> SwbtAdapterDiscoveryService.list()
  -> combo box を更新
```

refresh 中は button を disable し、結果が空の場合は明確に表示する。

| 結果 | GUI 表示 |
|---|---|
| 1 件以上 | combo box に表示 |
| 0 件 | “No swbt USB Bluetooth adapter found.” |
| discovery error | error dialog + technical log |

## error handling

| case | code |
|---|---|
| `AdapterDiscoveryError` | `NYX_SWBT_ADAPTER_DISCOVERY_FAILED` |
| adapter not selected | `NYX_SWBT_ADAPTER_NOT_SELECTED` |
| selected adapter not found | `NYX_SWBT_ADAPTER_NOT_FOUND` |
| ambiguous adapter | `NYX_SWBT_ADAPTER_AMBIGUOUS` |
