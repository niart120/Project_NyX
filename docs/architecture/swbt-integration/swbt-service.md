# SwbtGamepadService 設計

`SwbtGamepadService` は、非同期 API である `swbt.SwitchGamepad` を NyXPy の同期 `ControllerOutputPort` から使えるようにする境界です。

## 責務

`SwbtGamepadService` は次を担当します。

- `SwitchGamepad` の生成
- `open()`、`connect()`、`try_connect()`、`close(neutral=True)` の実行
- `asyncio` event loop の所有
- `InputState` の反映
- diagnostics trace writer の lifetime 管理
- swbt 例外を NyXPy 例外へ変換するための境界

`SwbtControllerOutputPort` はこの service に `apply()` と `neutral()` を依頼するだけにします。

## public interface

```python
class SwbtGamepadService:
    def start(self) -> None:
        """event loop を起動し、SwitchGamepad を open/connect する。"""

    def apply(self, state: InputState) -> None:
        """現在入力全体を swbt へ反映する。"""

    def neutral(self) -> None:
        """全入力を neutral へ戻す。"""

    def status(self) -> GamepadStatus:
        """GUI や診断用に接続状態を返す。"""

    def close(self) -> None:
        """neutral=True で gamepad を閉じ、event loop を停止する。"""
```

## event loop thread

NyXPy の `Command` と `ControllerOutputPort` は同期 API です。各 controller 操作で `asyncio.run()` を呼ぶ設計は避けます。`SwitchGamepad` は接続状態、callback、report loop を持つ長寿命 object なので、専用 event loop 上で管理します。

```text
NyX runtime thread
  └─ SwbtControllerOutputPort.press()
      └─ SwbtGamepadService.apply(state)
          └─ asyncio.run_coroutine_threadsafe(...)
              └─ SwitchGamepad.apply(state)
```

## start sequence

`start()` は次の順序で実行します。

```text
1. event loop thread を起動する
2. diagnostics trace writer を開く
3. SwitchGamepad を作る
4. await pad.open()
5. connect_on_open=True なら await pad.connect(timeout=..., allow_pairing=...)
6. 接続失敗時は await pad.close(neutral=True) して例外へ変換する
```

`SwitchGamepad.__aenter__()` は resource open だけを行い、pairing や reconnect は開始しません。service 側では `open()` の後に明示的に接続戦略を呼びます。

## 接続戦略

設定値による動作は次にします。

| 設定 | 動作 |
|---|---|
| `connect_on_open=true`, `allow_pairing=false` | 保存済み bond があれば reconnect。bond がなければ失敗 |
| `connect_on_open=true`, `allow_pairing=true` | 保存済み bond があれば reconnect。bond がなければ pairing |
| `connect_on_open=false` | open だけ行う。GUI の明示操作で connect / pair を呼ぶ |

CLI の通常実行では `connect_on_open=true` を使います。GUI では manual input 画面に「pair once」「reconnect」操作を分けてもよいです。

## key store

`key_store_path` は pairing 情報を保存する JSON path です。対象機器ごとに別ファイルを使います。

推奨値:

```text
.nyxpy/swbt/switch-bond.json
```

複数対象機器を扱う場合:

```text
.nyxpy/swbt/switch-main.json
.nyxpy/swbt/switch-sub.json
```

`key_store_path=None` は永続 bond を持たない一時 controller として扱われます。NyXPy の通常利用では reconnect を安定させるため、path 指定を推奨します。

## diagnostics

`diagnostics_path` が指定された場合、service が JSON Lines writer を開き、`DiagnosticsConfig(trace_writer=...)` を `SwitchGamepad` に渡します。

```python
from swbt import DiagnosticsConfig, SwitchGamepad

trace = diagnostics_path.open("a", encoding="utf-8")
pad = SwitchGamepad(
    adapter=config.adapter,
    key_store_path=str(config.key_store_path),
    report_period_us=config.report_period_us,
    device_name=config.device_name,
    diagnostics=DiagnosticsConfig(trace_writer=trace),
)
```

trace writer は service close で閉じます。trace に raw link key などの secret material を出さないのは swbt-python 側の責務ですが、NyXPy 側でも trace path を通常ログと同じ run artifact 配下に置く場合は、ユーザーが共有する前に内容を確認できる導線を用意します。

GUI と runtime で service を共有するため、`diagnostics_path` は service lifetime の設定です。`diagnostics_path` を変更した場合は既存 service を閉じ、新しい service を作ります。実行ごとの artifact directory へ trace を分ける場合は、run ごとに builder を再生成するか、diagnostics writer を service の cache key から外す別設計が必要です。初期実装では service key に `diagnostics_path` を含めます。

## 同期 wrapper

service の同期 method は `run_coroutine_threadsafe()` の結果を待ちます。待機中に swbt 側の例外が出たら NyXPy 例外へ変換します。

```python
import asyncio
from concurrent.futures import Future


def _submit(self, coro):
    if self._loop is None:
        raise SwbtServiceClosedError("swbt service is not started")
    future: Future = asyncio.run_coroutine_threadsafe(coro, self._loop)
    try:
        return future.result(timeout=self._operation_timeout_sec)
    except Exception as exc:
        raise map_swbt_exception(exc) from exc
```

`operation_timeout_sec` は `connect_timeout_sec` とは別に持つと、入力反映の停止を検出できます。既定値は 5 秒で十分です。

## close sequence

`close()` は次の順序で行います。

```text
1. close 中フラグを立てる
2. await pad.close(neutral=True)
3. diagnostics writer を閉じる
4. event loop を停止する
5. thread を join する
```

`SwitchGamepad.close(neutral=True)` は接続中なら trailing neutral を試みてから transport を閉じます。service 側で先に `neutral()` を呼んでいても、close 時の trailing neutral は残します。

## reconnect 失敗時の扱い

保存済み bond がない状態で `allow_pairing=false` の場合は、NyXPy では構成不備として失敗させます。

例外 details に含める情報:

```python
{
    "adapter": "usb:0",
    "key_store_path": ".nyxpy/swbt/switch-bond.json",
    "allow_pairing": False,
    "connect_timeout_sec": 30.0,
    "swbt_status": "no_bond",
}
```

GUI ではこの情報を使い、「初回 pairing を実行する」操作へ誘導できます。

## thread safety

`SwbtControllerOutputPort` から service を呼ぶ経路は同期化します。port 側に `RLock` を置き、service 側でも close と apply の競合を防ぎます。

```text
runtime 用 port 作成時
  → service.neutral()

close 中に apply が来た場合
  → DeviceError(code="NYX_SWBT_SERVICE_CLOSING")

close 後に apply が来た場合
  → DeviceError(code="NYX_SWBT_SERVICE_CLOSED")
```

GUI manual input とマクロ runtime は同じ service を共有しますが、同時操作は対象外です。GUI は runtime 実行中に manual input を無効化します。service 側は競合時に破壊的な状態遷移を起こさないように lock で保護します。

## dummy service

実機なしテスト用に `DummySwbtGamepadService` を作ります。

```python
class DummySwbtGamepadService:
    def __init__(self) -> None:
        self.started = False
        self.closed = False
        self.states: list[InputState] = []

    def start(self) -> None:
        self.started = True

    def apply(self, state: InputState) -> None:
        self.states.append(state)

    def neutral(self) -> None:
        self.states.append(InputState.neutral())

    def close(self) -> None:
        self.neutral()
        self.closed = True
```

この fake は `swbt-python` へ依存してもよいですが、unit test の速度を優先するなら `InputState` も薄い値 object に置き換えられるよう Protocol を用意します。
