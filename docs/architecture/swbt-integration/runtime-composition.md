# Runtime composition と factory 設計

この設計では、backend 選択を実行時 port に持たせません。構成起点で `serial` または `swbt` の具象 factory を一度だけ選び、`MacroRuntimeBuilder` には `PortFactory[ControllerOutputPort]` を渡します。

## 結論

実行時の依存は次で十分です。

```text
MacroRuntimeBuilder
  controller_factory: PortFactory[ControllerOutputPort]
```

backend 選択は `MacroRuntimeBuilder` の手前で終えます。

```text
settings / CLI / GUI
  ↓
make_controller_port_factory(...)
  ├─ serial なら SerialControllerOutputPortFactory を束縛
  └─ swbt なら SwbtControllerOutputPortFactory を束縛
  ↓
MacroRuntimeBuilder(controller_factory=...)
```

`ControllerOutputPort` の具象実装を隠蔽境界にします。`press()` や `release()` のたびに backend を見て分岐する port は作りません。

## factory 名の整理

現在の `ControllerOutputPortFactory` は名前だけ見ると汎用 factory ですが、実体は serial 専用です。`SerialProtocolInterface` と serial discovery に依存し、`create()` も `name` と `baudrate` を受けます。

推奨する整理:

```text
ControllerOutputPortFactory
  ↓
SerialControllerOutputPortFactory
```

新規追加:

```text
SwbtControllerOutputPortFactory
```

この改名では互換 alias を残しません。Project NyX のフレームワーク本体はアルファ版として扱うため、`ControllerOutputPortFactory` の import 利用箇所とテストを同じ変更で `SerialControllerOutputPortFactory` へ更新します。

この 2 つは同じ interface class を実装する必要はありません。どちらも最終的に `ControllerOutputPort` を返せばよいです。

## controller config

設定は controller backend ごとに型を分けます。

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SerialControllerConfig:
    device: str | None = None
    protocol: str = "CH552"
    baudrate: int = 9600


@dataclass(frozen=True)
class SwbtControllerConfig:
    adapter: str = "usb:0"
    key_store_path: Path | None = Path(".nyxpy/swbt/switch-bond.json")
    connect_timeout_sec: float = 30.0
    allow_pairing: bool = False
    report_period_us: int = 8000
    device_name: str = "Pro Controller"
    diagnostics_path: Path | None = None
    connect_on_open: bool = True
    invert_stick_y: bool = False


ControllerConfig = SerialControllerConfig | SwbtControllerConfig
```

`allow_pairing` は通常実行で `False` を既定にします。初回 pairing は CLI option または GUI 操作で明示的に許可します。

## make_controller_port_factory

説明用の形です。実装では既存の `create_device_runtime_builder` 内の `allow_dummy()` と lifetime 設定を使います。

```python
from collections.abc import Callable

from nyxpy.framework.core.io.ports import ControllerOutputPort
from nyxpy.framework.core.runtime.builder import PortFactory
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.macro.registry import MacroDefinition


def make_controller_port_factory(
    *,
    config: ControllerConfig,
    serial_factory: SerialControllerOutputPortFactory,
    swbt_factory: SwbtControllerOutputPortFactory,
    allow_dummy: Callable[[RuntimeBuildRequest], bool],
    timeout_sec: float,
) -> PortFactory[ControllerOutputPort]:
    match config:
        case SerialControllerConfig():
            def create_serial(
                request: RuntimeBuildRequest,
                _definition: MacroDefinition,
            ) -> ControllerOutputPort:
                return serial_factory.create(
                    name=config.device,
                    baudrate=config.baudrate,
                    allow_dummy=allow_dummy(request),
                    timeout_sec=timeout_sec,
                )

            return create_serial

        case SwbtControllerConfig():
            def create_swbt(
                request: RuntimeBuildRequest,
                _definition: MacroDefinition,
            ) -> ControllerOutputPort:
                return swbt_factory.create(
                    allow_dummy=allow_dummy(request),
                    timeout_sec=config.connect_timeout_sec,
                )

            return create_swbt
```

ここで `match` は backend 選択のための構成処理です。`ControllerOutputPort` 実装ではありません。

## create_device_runtime_builder の扱い

既存の `create_device_runtime_builder` は serial 名、baudrate、`ControllerOutputPortFactory.create(name=..., baudrate=...)` を前提にしています。swbt を入れるなら、次のどちらかにします。

| 案 | 内容 | 評価 |
|---|---|---|
| A | 既存 helper を serial 用として残し、swbt 用 helper を追加する | 変更範囲は小さいが CLI / GUI 側の分岐が増える |
| B | helper 内で controller config を正規化し、`PortFactory[ControllerOutputPort]` を作る | controller 以外の組み立てを共通化できる |

推奨は案 B です。capture、notification、resource、logger の組み立ては既存 helper にまとまっているため、controller だけ helper を分けるより、controller factory 生成だけを差し替える方が保守しやすいです。

## lifetime port

GUI の preview と manual input を考えると、factory は device / service を cache できる必要があります。既存 serial factory は serial device を cache して `SerialControllerOutputPort` を返します。swbt でも同じ考え方にします。

```text
SwbtControllerOutputPortFactory
  ├─ service key ごとに SwbtGamepadService を cache
  ├─ create() で SwbtControllerOutputPort を返す
  └─ close() で service.close() を呼ぶ
```

service key は少なくとも次を含めます。

```text
adapter
key_store_path
report_period_us
device_name
diagnostics_path
connect_on_open
```

`allow_pairing` と `connect_timeout_sec` は接続試行ごとの値です。既存 service が未接続なら次の `start()` / `connect()` に使えますが、接続済み service の key には含めません。設定変更で service key が変わる場合は runtime builder を再生成し、古い factory を `close()` します。

GUI と runtime は同じ接続を共有します。CLI 実行だけなら port が service を所有して `close()` で完全終了しても動きますが、実装方針としては CLI でも GUI でも factory が service を所有します。これにより manual input とマクロ実行で reconnect を繰り返さずに済みます。

## close の責務分担

`SwbtControllerOutputPort.close()` は安全停止として `neutral()` を呼びます。完全な transport close は service の所有者が呼びます。

推奨:

```text
MacroRuntime finally
  └─ context.controller.close()
       └─ neutral を送る

MacroRuntimeBuilder.shutdown()
  └─ SwbtControllerOutputPortFactory.close()
       └─ SwbtGamepadService.close()
            └─ close(neutral=True)
```

CLI でも GUI でも port close は neutral だけを担当します。完全 close は factory close に寄せます。CLI では `runtime_builder.shutdown()` がすぐ呼ばれるため、その時点で transport も閉じます。GUI では runtime 終了後も builder が生きている限り transport を維持できます。

## shared service と port state

`SwbtControllerOutputPort` は NyXPy 側の入力状態を持ちます。GUI manual input とマクロ runtime は別 port でも同じ service を共有するため、runtime 開始時は必ず neutral から始めます。

```text
SwbtControllerOutputPortFactory.create()
  └─ 新しい SwbtControllerOutputPort を返す
       ├─ port 内部状態は NyxSwbtState() で初期化
       └─ 必要に応じて service.neutral() を呼び、共有 service 側も neutral に揃える
```

port の `close()` は内部状態を破棄し、service に neutral を送るだけです。別 port が直前に持っていた状態は維持しません。manual input と runtime 実行を同時に動かさない前提にし、GUI は macro 実行中に manual input 操作を無効化します。

## dummy fallback

serial backend は dummy serial を持ちます。swbt backend の dummy は、実機なしで macro を走らせる用途に限定します。

```text
allow_dummy=True
  serial: DummySerialComm を使う
  swbt: DummySwbtGamepadService を使う

allow_dummy=False
  serial: device 未選択または open 失敗で ConfigurationError
  swbt: adapter 未選択、open 失敗、connect 失敗で ConfigurationError
```

swbt dummy は実際の Bluetooth 接続を開始しません。`press` / `hold` / `release` を記録し、テストや dry run で検証できるようにします。
