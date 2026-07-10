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
    adapter: str | None = None
    key_store_path: Path | None = None
    connect_timeout_sec: float = 30.0
    report_period_us: int | None = 8000


ControllerConfig = SerialControllerConfig | SwbtControllerConfig
```

`SwbtControllerConfig` は `controller_type` 文字列を持たない。設定正規化の時点で `SwbtControllerModel` へ解決する。

`key_store_path` が `None` の場合は、session 作成前に `.nyxpy/swbt/<controller>-bond.json` へ補完する。`adapter` が `None` または空文字の場合、接続操作は `NYX_SWBT_ADAPTER_NOT_SELECTED` で失敗させる。

`operation_timeout_sec` は settings / config に出さず、session / factory の内部既定値として扱う。diagnostics は config path ではなく writer を session へ渡す。

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

swbt factory は session と active port を cache する。同じ adapter / controller model / key store / report period の transport resource は `SwbtControllerSession` に集約し、有効な `SwbtControllerOutputPort` は session key ごとに 1 つだけにする。

```text
SwbtControllerOutputPortFactory
  ├─ config から session key を作る
  ├─ session key ごとに SwbtControllerSession を cache する
  ├─ session key ごとに active SwbtControllerOutputPort を 1 つだけ管理する
  ├─ create() で open + reconnect 済み session を得る
  ├─ create() で旧 active port を close してから新しい SwbtControllerOutputPort を返す
  ├─ pair(config) で明示 pairing を行う
  ├─ reconnect(config) で明示 reconnect を行う
  ├─ pair/reconnect/disconnect 前に active port を close する
  ├─ disconnect(config) で factory-managed cached session と active port を閉じる
  ├─ status(config) で factory-managed cached session の状態を返す
  └─ close() で active port と cached session をすべて close する
```

session key に含める値:

```text
model.controller_type
adapter
key_store_path
report_period_us
```

session key に含めない値:

```text
connect_timeout_sec
operation_timeout_sec
allow_dummy
diagnostics writer
reset_on_port_create
```

接続試行ごとの値:

```text
connect_timeout_sec
allow_dummy
```

macro 実行時の接続は reconnect のみである。pairing は runtime の副作用として行わない。

`allow_dummy=True` による dummy fallback は `create()` だけで有効にする。`pair()` と `reconnect()` は実接続操作なので dummy fallback しない。

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
        session.open()
        session.reconnect(timeout_sec=timeout_sec)
        self._close_active_port(session_key(config))
        return SwbtControllerOutputPort(
            session=session,
            mapper=NyxSwbtInputMapper(model=config.model),
            on_close=lambda port: self._discard_active_port(session_key(config), port),
        )
```

`SwbtControllerSession.start()` は作らない。`factory.create()` が `open()` と `reconnect()` を順に呼ぶ。

key store がない場合に pairing へ fallback しない。key store がない場合や不正な場合は `ConfigurationError` に変換する。

port 作成時は `SwbtControllerOutputPort` が neutral を常に試みる。`reset_on_port_create` という設定や引数は持たない。

`create()` が既存 active port を close できない場合、新しい port は返さない。接続失敗で session を cache から捨てる場合は、同じ key の active port も閉じて再利用対象から外す。

## diagnostics writer

swbt diagnostics は path 設定ではなく writer interface として扱う。runtime / GUI / CLI には `diagnostics_path`、`--diagnostics`、diagnostics UI を出さない。

NyX 内部では diagnostics writer を `LoggerPort.technical(...)` へ流す adapter を用意する。実機 test では同じ writer を tee し、`tmp/hardware/swbt/<timestamp>/swbt-trace.jsonl` に証跡を残す。

## GUI pair / reconnect / disconnect

GUI の pair / reconnect / disconnect は入力反映経路ではない。app service から `SwbtControllerOutputPortFactory` の lifecycle method を呼ぶ。

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

```text
Disconnect button
  -> VirtualControllerModel.set_controller(None)
  -> VirtualControllerModel.reset_state()
  -> builder.discard_manual_controller(previous port)
  -> previous manual port.release()
  -> previous manual port.close()
  -> swbt_factory.disconnect(config)
  -> status update
```

`Pair` / `Reconnect` が成功したあとに GUI manual input を有効化する。失敗した場合は `VirtualControllerModel.set_controller(None)` に戻す。

## macro runtime との排他

GUI lifetime controller と macro runtime controller が同じ adapter を同時に使うと、USB transport の所有権と入力状態が競合する。GUI は次のルールを守る。

| 状態 | 許可する操作 |
|---|---|
| disconnected | adapter refresh、pair、reconnect |
| connected for manual input | 仮想コントローラー操作、release all、disconnect |
| macro running | manual input、pair、reconnect、disconnect を無効化 |
| macro start requested while manual connected | `VirtualControllerModel.set_controller(None)` と `reset_state()` 後に GUI lifetime port を `release()` / `close()` し、builder cache からも外してから runtime を開始 |

runtime 終了後、GUI は自動で reconnect しない。利用者が `Reconnect from pairing key` を押した時だけ GUI lifetime port を再作成する。

排他は GUI の macro start sequence と、factory の active port 管理で担保する。manual input と runtime input を混ぜる mixer は作らない。新しい port を払い出す操作は同じ session key の旧 port を閉じる。

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
