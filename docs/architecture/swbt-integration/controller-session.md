# SwbtControllerSession 設計

`SwbtControllerSession` は、`swbt-python` controller の lifecycle を NyXPy の同期 `ControllerOutputPort` から使うための backend 内部部品である。

実装 module は `nyxpy.framework.core.hardware.swbt.session` とする。

`SwbtControllerOutputPort` は `apply()` と `neutral()` を session に依頼する。Bluetooth HID の open、pairing、reconnect、diagnostics writer、close は session が所有する。

## なぜ session が必要か

serial backend は `SerialControllerOutputPort` から `SerialComm.send(...)` を呼ぶ。swbt backend は controller class の選択、adapter 未指定の拒否、key store、diagnostics writer、swbt 例外の変換を同じ入力 port から扱う必要がある。

`SwbtControllerSession` はこの lifecycle 差分を吸収する。swbt-python 0.2 系では `open()`、`pair()`、`reconnect()`、`apply()`、`neutral()`、`close()` が async API、`status()` が同期 API である。session は専用 event loop thread で async API の完了を待ち、上位には同期 method として見せる。

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
- async controller method の完了待ち
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

    def pair(self, *, timeout_sec: float) -> None:
        """pairing を実行し、status が connected であることを確認する。"""

    def reconnect(self, *, timeout_sec: float) -> None:
        """保存済み pairing key で reconnect し、status が connected であることを確認する。"""

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

swbt の `pair()` / `reconnect()` 自体の戻り値は `None` である。session は操作完了後に同期 `status()` を取得し、`status.connection_state == "connected"` を接続成功条件として内部で確認する。上位へ返す値も `None` であり、戻り値の truthiness や存在しない `status.connected` / `status.message` は使わない。

## async bridge

`ControllerOutputPort` は同期 interface である。session は controller の async lifecycle / input method を内部 event loop thread へ渡して完了を待つ。`status()` だけは同期呼び出しする。

```python
def _run_awaitable(self, awaitable):
    future = asyncio.run_coroutine_threadsafe(awaitable, self._loop)
    return future.result(timeout=self._operation_timeout_sec)
```

GUI thread で event loop を回さない。GUI の adapter refresh、pair / reconnect / disconnect、macro start、port cleanup は worker thread から session の同期 facade を呼ぶ。仮想コントローラーの manual press / release は現時点では Qt main thread から同期呼び出しする。`_operation_timeout_sec` は session 内部の既定値であり、通常 settings には出さない。

## lifecycle state

```text
new
  -> open
  -> pair / reconnect
  -> connected
  -> apply / neutral / status
  -> close
```

`open()` は複数回呼んでも安全にする。`close()` も idempotent にする。controller close が失敗した場合は closed 扱いにしない。controller close が成功して event loop stop だけが失敗した場合は controller を終端済みとして扱い、次回 `close()` では loop 所有権の回収だけを再試行する。

## close semantics

`close()` は接続中なら `controller.close(neutral=True)` を呼ぶ。port close で neutral 済みでも、session close 時の trailing neutral は残す。

factory は active port の neutral が失敗しても処理を止めず、`session.close()` による `controller.close(neutral=True)` を必ず試す。session close が成功した場合は終端 neutral と transport close が完了したものとし、先行する port neutral error は回復済みとして扱う。factory は cache を削除し、外部が保持する旧 port を追加送信なしで無効化する。

session close または event loop stop が失敗した場合だけ、factory は session / active port の参照を保持して再試行可能にする。controller close と loop stop が両方失敗した場合は、この順序の leaf error を `ExceptionGroup` に格納する。create / pair / reconnect の primary 接続例外後に cleanup も失敗した場合は、primary error を先頭、その後に port neutral、controller close、loop stop の実行順で cleanup error を格納する。各 leaf は元の framework error object を維持するため、`code` を失わない。

## 排他

session 内部には `RLock` を置き、connection operation と input apply を直列化する。

GUI lifetime port と macro runtime port が同一 session を同時に使わないよう、GUI 側は macro start 前に `VirtualControllerModel.set_controller(None)` を呼び、旧 manual port を release/close する。

`SwbtControllerOutputPortFactory` は session key ごとに active port を 1 つだけ持つ。同一物理 adapter を別の controller model / key store で指定した場合も既存 port / session を先に閉じる。`create()` / `pair()` / `reconnect()` で旧 active port の neutral が失敗した場合は session close へ進み、終端 close に成功した場合だけ新しい session / port へ置き換える。`disconnect()` / `close()` / 接続失敗時の session 破棄も同じ cleanup 規則を使う。

session 自体は connection lifecycle と transport lock を持つ。manual / runtime の所有権は factory の active port 管理で扱い、`NYX_SWBT_ADAPTER_BUSY` のような busy error は追加しない。

## DummySwbtControllerSession

```python
class DummySwbtControllerSession:
    states: list[InputState]

    def open(self) -> None: ...
    def pair(self, *, timeout_sec: float) -> None: ...
    def reconnect(self, *, timeout_sec: float) -> None: ...
    def apply(self, state: InputState) -> None: ...
    def neutral(self) -> None: ...
    def status(self) -> GamepadStatus: ...
    def close(self) -> None: ...
```

実機なし test では dummy session を使う。dummy status も `connection_state` を持つ `GamepadStatus` 相当の形にそろえ、production と別の `connected` field を作らない。これは GUI manual input 専用ではなく、`SwbtControllerOutputPort` の test double である。
