# SwbtControllerSession 設計

`SwbtControllerSession` は、`swbt-python` controller の lifecycle を NyXPy の同期 `ControllerOutputPort` から使うための backend 内部部品である。

実装 module は `nyxpy.framework.core.hardware.swbt.session` とする。

`SwbtControllerOutputPort` は `apply()` と `neutral()` を session に依頼する。Bluetooth HID の open、pairing、reconnect、diagnostics writer、close は session が所有する。

## なぜ session が必要か

serial backend は `SerialControllerOutputPort` から `SerialComm.send(...)` を呼ぶ。swbt backend は controller class の選択、adapter 未指定の拒否、key store、diagnostics writer、swbt 例外の変換を同じ入力 port から扱う必要がある。

`SwbtControllerSession` はこの lifecycle 差分を吸収する。swbt-python 0.2 系の公開 API は同期呼び出しを前提とする。controller method が awaitable を返した場合だけ、session 内部で完了待ちして上位には同期 method として見せる。

```text
SwbtControllerOutputPort  # sync ControllerOutputPort implementation
  -> SwbtControllerSession  # swbt controller lifecycle adapter
  -> swbt-python controller
```

これは GUI manual input の上位 layer ではない。

## 責務

`SwbtControllerSession` が担当するもの:

- `SwbtControllerModel.controller_type` から swbt controller class を解決し、controller を生成する
- `open()`、`pair()`、`reconnect()` の実行
- macro 実行前の reconnect
- awaitable を返す controller method の完了待ち
- `InputState` の `apply()`
- `neutral()`
- `status()` の取得
- diagnostics writer の lifetime
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
        """controller resource を開く。接続は開始しない。"""

    def pair(self, *, timeout_sec: float) -> object:
        """pairing を明示実行する。成功時は key store に pairing 情報が保存される。"""

    def reconnect(self, *, timeout_sec: float) -> object:
        """保存済み pairing key に基づく reconnect を明示実行する。"""

    def apply(self, state: InputState) -> None:
        """現在入力全体を置き換える。"""

    def neutral(self) -> None:
        """全入力を neutral へ戻す。"""

    def status(self) -> GamepadStatus:
        """接続状態と診断 snapshot を返す。"""

    def close(self) -> None:
        """neutral=True で controller を閉じる。"""
```

`SwbtControllerSession.start()` は作らない。CLI / GUI の `pair`、`reconnect` は明示操作である。macro 実行時は factory が `open()` 後に `reconnect()` を呼ぶ。

## Controller 作成

`SwbtControllerModel` は swbt runtime class を保持しない。session は `controller_type` から swbt controller class を解決する。

```python
from swbt import DiagnosticsConfig


def create_swbt_controller(
    config: SwbtControllerConfig,
    diagnostics_writer=None,
) -> object:
    controller_cls = resolve_swbt_controller_class(config.model.controller_type)
    diagnostics = None
    if diagnostics_writer is not None:
        diagnostics = DiagnosticsConfig(trace_writer=diagnostics_writer)
    return controller_cls(
        adapter=config.adapter,
        key_store_path=str(config.key_store_path),
        report_period_us=config.report_period_us,
        diagnostics=diagnostics,
    )
```

diagnostics writer は NyX 内部 adapter で `LoggerPort.technical(...)` に流す。settings、GUI、CLI に diagnostics path は出さない。

## awaitable bridge

`ControllerOutputPort` は同期 interface である。controller method の戻り値が awaitable なら、session は内部 event loop thread へ渡して完了を待つ。同期 API の戻り値はそのまま使う。

```python
def _run_awaitable(self, awaitable):
    future = asyncio.run_coroutine_threadsafe(awaitable, self._loop)
    return future.result(timeout=self._operation_timeout_sec)
```

GUI thread で event loop を回さない。`_operation_timeout_sec` は session 内部の既定値であり、通常 settings には出さない。

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

`close()` は接続中なら `controller.close(neutral=True)` を呼ぶ。port close で neutral 済みでも、session close 時の trailing neutral は残す。

transport が壊れて neutral に失敗した場合でも、close 処理は可能な限り最後まで進める。error は technical log に残し、必要に応じて `ExceptionGroup` として集約する。

## 排他

session 内部には `RLock` を置き、connection operation と input apply を直列化する。

GUI lifetime port と macro runtime port が同一 session を同時に使わないよう、GUI 側は macro start 前に `VirtualControllerModel.set_controller(None)` を呼び、旧 manual port を release/close する。

初期実装では session の active lease 管理や adapter busy error は入れない。

## DummySwbtControllerSession

```python
class DummySwbtControllerSession:
    connected: bool
    states: list[InputState]

    def open(self) -> None: ...
    def pair(self, *, timeout_sec: float) -> object: ...
    def reconnect(self, *, timeout_sec: float) -> object: ...
    def apply(self, state: InputState) -> None: ...
    def neutral(self) -> None: ...
    def status(self) -> GamepadStatus: ...
    def close(self) -> None: ...
```

実機なし test では dummy session を使う。これは GUI manual input 専用ではなく、`SwbtControllerOutputPort` の test double である。
