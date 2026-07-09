# SwbtControllerSession 設計

`SwbtControllerSession` は、`swbt-python` の非同期 controller API を NyXPy の同期 `ControllerOutputPort` から使うための backend 内部部品である。

実装 module は `nyxpy.framework.core.hardware.swbt.session` とする。

`SwbtControllerOutputPort` は `apply()` と `neutral()` を session に依頼する。Bluetooth HID の接続、pairing、reconnect、event loop、diagnostics writer は session が所有する。

## なぜ session が必要か

serial backend は `SerialControllerOutputPort` から `SerialComm.send(...)` を同期的に呼べる。一方、swbt controller は async resource と report loop を持つ。

`SwbtControllerSession` はこの差を吸収する。

```text
SwbtControllerOutputPort  # sync ControllerOutputPort implementation
  -> SwbtControllerSession  # async swbt resource adapter
  -> swbt-python controller
```

これは GUI manual input の上位 layer ではない。

## 責務

`SwbtControllerSession` が担当するもの:

- `SwbtControllerModel.controller_cls` から controller を生成する
- `open()`、`pair()`、`reconnect()`、`try_reconnect()` の実行
- macro 実行前の reconnect
- `asyncio` event loop thread の所有
- `InputState` の `apply()`
- `neutral()`
- `status()` の取得
- `DiagnosticsConfig` と trace writer の lifetime
- swbt 例外の NyXPy 例外への変換

`SwbtControllerOutputPort` が担当するもの:

- NyXPy の `KeyType` と `IMUFrame` の状態管理
- mapper による `InputState` 生成
- session の同期 method 呼び出し
- port close 時の neutral

## public interface

```python
class SwbtControllerSession:
    def open(self) -> None:
        """event loop と gamepad resource を準備する。接続は開始しない。"""

    def start(self, *, timeout_sec: float) -> None:
        """macro / GUI lifetime port 用。open 後、保存済み pairing key で reconnect する。"""

    def pair(self, *, timeout_sec: float) -> ConnectionResult:
        """pairing を明示実行する。成功時は key store に pairing 情報が保存される。"""

    def reconnect(self, *, timeout_sec: float) -> ConnectionResult:
        """保存済み pairing key に基づく reconnect を明示実行する。"""

    def apply(self, state: InputState) -> None:
        """現在入力全体を置き換える。"""

    def neutral(self) -> None:
        """全入力を neutral へ戻す。"""

    def status(self) -> GamepadStatus:
        """接続状態と診断 snapshot を返す。"""

    def close(self) -> None:
        """neutral=True で gamepad を閉じ、event loop を停止する。"""
```

CLI / GUI の `pair`、`reconnect` は明示操作である。macro 実行時は `start()` により reconnect だけを行う。

## Gamepad 作成

```python
from swbt import SwitchGamepad


def create_gamepad(config: SwbtControllerConfig, diagnostics_writer=None) -> SwitchGamepad:
    return config.model.controller_cls(
        adapter=config.adapter,
        key_store_path=config.key_store_path,
        report_period_us=config.report_period_us,
        diagnostics=DiagnosticsConfig(trace_writer=diagnostics_writer) if diagnostics_writer else None,
    )
```

## event loop bridge

`ControllerOutputPort` は同期 interface なので、session は内部で event loop thread を持つ。

```python
class SwbtControllerSession:
    def _run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=self.operation_timeout_sec)

    def apply(self, state: InputState) -> None:
        self._run(self._pad.apply(state))
```

GUI thread で async loop を回さない。

## lifecycle state

```text
new
  -> open
  -> pair / reconnect
  -> connected
  -> apply / neutral / status
  -> close
```

`open()` は複数回呼んでも安全にする。`close()` も idempotent にする。

## close semantics

`close()` は接続中なら `pad.close(neutral=True)` を呼ぶ。port close で neutral 済みでも、session close 時の trailing neutral は残す。

transport が壊れて neutral に失敗した場合でも、close 処理は可能な限り最後まで進める。error は technical log に残し、必要に応じて `ExceptionGroup` として集約する。

## 排他

session 内部には `RLock` を置き、connection operation と input apply を直列化する。

GUI lifetime port と macro runtime port が同一 session を同時に使わないよう、GUI 側は macro start 前に manual port を close する。factory 側でも同一 session の重複使用を検知できるなら早く失敗させる。

## DummySwbtControllerSession

```python
class DummySwbtControllerSession:
    connected: bool
    states: list[InputState]

    def start(self, *, timeout_sec: float) -> None: ...
    def apply(self, state: InputState) -> None: ...
    def neutral(self) -> None: ...
    def close(self) -> None: ...
```

実機なし test では dummy session を使う。これは GUI manual input 専用ではなく、`SwbtControllerOutputPort` の test double である。
