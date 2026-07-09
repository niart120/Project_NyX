# Runtime composition と factory 設計

controller backend の選択は、runtime builder を作る構成起点で完了させる。`MacroRuntimeBuilder` は `PortFactory[ControllerOutputPort]` を受け取り、実行時には controller backend を判定しない。

`SwbtControllerOutputPortFactory` の実装 module は `nyxpy.framework.core.hardware.swbt.factory` である。

## 構成の流れ

```text
settings / CLI / GUI
  ↓
controller_config_from_settings(...)
  ↓
make_controller_port_factory(...)
  ├─ serial: existing serial ControllerOutputPort factory
  └─ swbt: SwbtControllerOutputPortFactory
  ↓
MacroRuntimeBuilder(controller_factory=..., manual_controller_factory=...)
  ↓
ExecutionContext(controller=ControllerOutputPort)
```

GUI manual input は runtime port を迂回しない。現行と同じく `MacroRuntimeBuilder.controller_output_for_manual_input()` から GUI lifetime の `ControllerOutputPort` を受け取り、`VirtualControllerModel.set_controller(...)` へ渡す。

## Controller config

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ControllerBackend(str, Enum):
    SERIAL = "serial"
    SWBT = "swbt"


@dataclass(frozen=True)
class SerialControllerConfig:
    device: str | None = None
    protocol: str = "CH552"
    baudrate: int = 9600


@dataclass(frozen=True)
class SwbtControllerConfig:
    model: SwbtControllerModel
    adapter: str = "usb:0"
    key_store_path: Path | None = Path(".nyxpy/swbt/pro-controller-bond.json")
    connect_timeout_sec: float = 30.0
    operation_timeout_sec: float = 5.0
    report_period_us: int | None = 8000
    diagnostics_path: Path | None = None
    reset_on_port_create: bool = True


ControllerConfig = SerialControllerConfig | SwbtControllerConfig
```

`SwbtControllerConfig` は `controller_type` 文字列を持たない。設定正規化の時点で `SwbtControllerModel` へ解決する。

## make_controller_port_factory

```python
from collections.abc import Callable

from nyxpy.framework.core.io.ports import ControllerOutputPort
from nyxpy.framework.core.runtime.builder import PortFactory
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest


def make_controller_port_factory(
    *,
    config: ControllerConfig,
    serial_factory,
    swbt_factory: SwbtControllerOutputPortFactory,
    allow_dummy: Callable[[RuntimeBuildRequest], bool],
    detection_timeout_sec: float,
) -> PortFactory[ControllerOutputPort]:
    match config:
        case SerialControllerConfig():
            def create_serial(request: RuntimeBuildRequest, _definition) -> ControllerOutputPort:
                return serial_factory.create(
                    name=config.device,
                    baudrate=config.baudrate,
                    allow_dummy=allow_dummy(request),
                    timeout_sec=detection_timeout_sec,
                )
            return create_serial

        case SwbtControllerConfig():
            def create_swbt(request: RuntimeBuildRequest, _definition) -> ControllerOutputPort:
                return swbt_factory.create(
                    config=config,
                    allow_dummy=allow_dummy(request),
                    timeout_sec=config.connect_timeout_sec,
                )
            return create_swbt
```

ここでの `match` は構成処理である。`ControllerOutputPort` 実装内で backend dispatch を行うものではない。

## GUI lifetime controller

既存の runtime builder は GUI lifetime 用 controller を別 factory で受け取れる。swbt backend でもこの仕組みを使う。

```text
GuiAppServices.apply_settings(...)
  -> builder.controller_output_for_manual_input()
  -> SettingsApplyOutcome.manual_controller
  -> MainWindow._apply_runtime_ports(...)
  -> VirtualControllerModel.set_controller(port)
```

swbt の manual input 用に別 session を作らない。

```text
VirtualControllerModel
  -> ControllerOutputPort
  -> SwbtControllerOutputPort
```

## SwbtControllerOutputPortFactory

swbt factory は session を cache できる。`create()` ごとに新しい `SwbtControllerOutputPort` を返すが、同じ adapter / controller model / key store の transport resource は `SwbtControllerSession` に集約する。

```text
SwbtControllerOutputPortFactory
  ├─ config から session key を作る
  ├─ session key ごとに SwbtControllerSession を cache する
  ├─ create() で reconnect 済み session を得る
  ├─ create() で SwbtControllerOutputPort を返す
  ├─ pair(config) で明示 pairing を行う
  ├─ reconnect(config) で明示 reconnect を行う
  └─ close() で cached session をすべて close する
```

session key に含める値:

```text
model.controller_type
adapter
key_store_path
report_period_us
diagnostics_path
operation_timeout_sec
```

接続試行ごとの値:

```text
connect_timeout_sec
allow_dummy
```

macro 実行時の接続は reconnect のみである。pairing は runtime の副作用として行わない。

## port 作成

```python
class SwbtControllerOutputPortFactory:
    def create(
        self,
        *,
        config: SwbtControllerConfig,
        allow_dummy: bool,
        timeout_sec: float,
    ) -> ControllerOutputPort:
        session = self._session_for_config(config, allow_dummy=allow_dummy)
        session.start(timeout_sec=timeout_sec)  # open + reconnect
        return SwbtControllerOutputPort(
            session=session,
            mapper=NyxSwbtInputMapper(model=config.model),
            reset_on_create=config.reset_on_port_create,
        )
```

`session.start()` は保存済み pairing key に基づく reconnect を行う。key store がない場合や key store が不正な場合は `ConfigurationError` に変換する。

## GUI pair / reconnect

GUI の pair / reconnect は入力反映経路ではない。app service から `SwbtControllerOutputPortFactory` の lifecycle method を呼ぶ。

```text
Pair button
  -> swbt_factory.pair(config)
  -> session.open()
  -> session.pair(timeout_sec=...)
  -> success: settings / status update
  -> builder.controller_output_for_manual_input()
  -> VirtualControllerModel.set_controller(port)
```

```text
Reconnect button
  -> swbt_factory.reconnect(config)
  -> session.open()
  -> session.reconnect(timeout_sec=...)
  -> success: settings / status update
  -> builder.controller_output_for_manual_input()
  -> VirtualControllerModel.set_controller(port)
```

`Pair` / `Reconnect` が成功したあとに GUI manual input を有効化する。失敗した場合は `VirtualControllerModel.set_controller(None)` に戻す。

## macro runtime との排他

GUI lifetime controller と macro runtime controller が同じ adapter を同時に使うと、USB transport の所有権と入力状態が競合する。GUI は次のルールを守る。

| 状態 | 許可する操作 |
|---|---|
| disconnected | adapter refresh、pair、reconnect |
| connected for manual input | 仮想コントローラー操作、release all、disconnect |
| macro running | manual input、pair、reconnect を無効化 |
| macro start requested while manual connected | GUI lifetime port を `release()` / `close()` してから runtime を開始 |

runtime 終了後、GUI は自動で reconnect しない。利用者が `Reconnect from pairing key` を押した時だけ GUI lifetime port を再作成する。

## shutdown

```text
MacroRuntimeBuilder.shutdown()
  ├─ manual ControllerOutputPort.close()
  ├─ preview FrameSourcePort.close()
  └─ factory close callbacks
       └─ SwbtControllerOutputPortFactory.close()
            └─ SwbtControllerSession.close()
```

`SwbtControllerOutputPort.close()` は neutral を試みる。transport の完全 close は factory / session close で行う。

## dummy

`allow_dummy=True` の swbt backend では、Bluetooth 接続を開始しない `DummySwbtControllerSession` を使える。

用途:

- mapper test
- port contract test
- GUI model test
- runtime builder test

`DummySwbtControllerSession` は受け取った `InputState` を記録する。GUI manual input 専用 session ではない。
