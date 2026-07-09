# レイヤードアーキテクチャ上の配置

swbt backend は、NyXPy の controller 出力を Bluetooth HID 経由で実現する backend である。マクロから見える抽象は `Command` と `ControllerOutputPort` に止め、`swbt-python` の公開 API と Bluetooth lifecycle は `hardware.swbt` package に閉じ込める。

## 全体構造

```text
macro
  MacroBase / Command
        ↓
runtime
  ExecutionContext / MacroRuntime / MacroRuntimeBuilder
        ↓
io
  ControllerOutputPort
        ├─ SerialControllerOutputPort
        └─ SwbtControllerOutputPort
                ↓
hardware.swbt
  config.py       SwbtControllerType / SwbtControllerModel / SwbtControllerConfig
  factory.py      SwbtControllerOutputPortFactory
  controller.py   SwbtControllerOutputPort
  session.py      SwbtControllerSession
  discovery.py    SwbtAdapterDiscoveryService
  mapper.py       NyxSwbtInputMapper / NyxSwbtState
  errors.py       exception mapping
        ↓
swbt-python
  ProController / JoyConL / JoyConR
  list_adapters()
  InputState / Button / Stick / IMUFrame
        ↓
Bumble USB Bluetooth HID transport
```

`manual.py` や `SwbtManualInputSession` は追加しない。GUI manual input の入力経路は既存の `VirtualControllerModel -> ControllerOutputPort` で足りている。

## 責務分担

| 層 | 責務 |
|---|---|
| `macro` | `Command` API を使う。swbt を import しない |
| `runtime` | 実行 context を作り、controller port を注入する。swbt の詳細を知らない |
| `io` | `ControllerOutputPort` の契約を定義する |
| `hardware.swbt` | controller 種別解決、adapter discovery、pairing、reconnect、awaitable bridge、input mapping を扱う |
| `gui` | adapter 更新、pair、reconnect、controller 種別指定、既存仮想コントローラーからの manual input を扱う |
| `cli` | adapter 一覧、pair、reconnect、disconnect、run option を公開する |

## 推奨ファイル配置

swbt 専用実装は 1 つの package にまとめる。`swbt_config.py`、`swbt_gamepad.py` のような接頭辞付き file は作らない。

```text
src/nyxpy/framework/core/io/ports.py
  ControllerOutputPort

src/nyxpy/framework/core/macro/command.py
  Command / DefaultCommand

src/nyxpy/framework/core/constants/
  controller.py  Button / Hat / ThreeDSButton / TouchState
  stick.py       LStick / RStick
  imu.py         IMUFrame

src/nyxpy/framework/core/hardware/swbt/__init__.py
  public re-export

src/nyxpy/framework/core/hardware/swbt/config.py
  SwbtControllerType
  SwbtControllerModel
  SwbtInputCapabilities
  SwbtControllerConfig
  SwbtRuntimeOptions
  supported_controller_models()
  parse_controller_type(...)
  resolve_controller_model(...)

src/nyxpy/framework/core/hardware/swbt/discovery.py
  SwbtAdapterDiscoveryService
  SwbtAdapterView
  resolve_adapter(...)

src/nyxpy/framework/core/hardware/swbt/factory.py
  SwbtControllerOutputPortFactory

src/nyxpy/framework/core/hardware/swbt/controller.py
  SwbtControllerOutputPort

src/nyxpy/framework/core/hardware/swbt/session.py
  SwbtControllerSession
  DummySwbtControllerSession

src/nyxpy/framework/core/hardware/swbt/mapper.py
  NyxSwbtState
  NyxSwbtInputMapper

src/nyxpy/framework/core/hardware/swbt/errors.py
  SwbtIntegrationError
  map_exception(...)
```

`SwbtControllerSession` は、serial backend における `SerialComm` と `SerialProtocolInterface` の組み合わせに近い backend 内部部品である。GUI の専用 layer ではない。

## import policy

`swbt-python` は通常依存である。ただし依存方向を明確にするため、`swbt` の import は `hardware.swbt` package と swbt public API を説明する文書内に閉じる。

| 場所 | import 方針 |
|---|---|
| `hardware.swbt.*` | `swbt` を import してよい |
| `io.ports` | `swbt` を import しない |
| `macro.command` | `swbt` を import しない |
| `runtime.builder` | `swbt` を直接 import しない。factory 注入に止める |
| `gui` | `swbt` を直接 import しない。app service / factory 経由で扱う |

`swbt` 未導入を通常の runtime 分岐として扱わない。依存解決に失敗する環境は packaging / installation の問題であり、backend ごとの追加導入案内は出さない。

## GUI manual input の配置

GUI 仮想コントローラーは既存の `VirtualControllerModel` を使う。

```text
VirtualControllerPane
  -> VirtualControllerModel
  -> ControllerOutputPort
```

backend 切り替えは `ControllerOutputPort` の下で行う。

```text
VirtualControllerModel
  -> ControllerOutputPort
       ├─ SerialControllerOutputPort
       └─ SwbtControllerOutputPort
```

このため、GUI 層に `SwbtManualInputSession`、`SwbtManualInputModel`、`SwbtVirtualControllerAdapter` のような中間 layer は作らない。

## lifecycle の分離

pairing / reconnect は入力反映ではなく、controller port を使用可能にするための lifecycle 操作である。

```text
adapter refresh / pair / reconnect
  -> hardware.swbt factory/session lifecycle
  -> GUI lifetime ControllerOutputPort が使用可能になる
  -> VirtualControllerModel.set_controller(port)
```

button / D-pad / stick 入力は lifecycle 操作を経由しない。

```text
button / D-pad / stick
  -> VirtualControllerModel
  -> ControllerOutputPort.press/release
  -> SwbtControllerOutputPort
```

## IMU の配置

IMU は GUI manual input ではなく、`Command` / `ControllerOutputPort` の command surface に追加する。swbt backend は実装し、非対応 backend は `NotImplementedError` を返す。

```text
Command.imu(...)
  -> ControllerOutputPort.imu(...)
       ├─ SwbtControllerOutputPort.imu(...)
       └─ default unsupported
```

GUI には IMU preset、pose editor、raw editor を置かない。

## 命名方針

| 対象 | 方針 | 例 |
|---|---|---|
| package | `swbt` namespace を切る | `hardware/swbt/session.py` |
| file | `swbt_` 接頭辞を付けない | `config.py`, `factory.py` |
| public class | backend 判別のため `Swbt...` を残す | `SwbtControllerConfig`, `SwbtControllerSession` |
| package-local helper | `swbt_` を重ねない | `map_exception`, `to_button` |

## 依存方向

```text
macro -> io.ports
runtime -> io.ports
runtime -> injected factories
gui -> app service -> runtime builder / hardware.swbt factory
hardware.swbt -> io.ports
hardware.swbt -> swbt-python
```

禁止する依存:

```text
gui -> swbt-python
gui -> SwbtControllerOutputPort internals
macro -> hardware.swbt
io.ports -> swbt-python
runtime.builder -> concrete swbt controller class
```
