# SwbtControllerOutputPort の契約

`SwbtControllerOutputPort` は NyXPy の `ControllerOutputPort` を実装します。責務は、NyXPy の `KeyType` 入力を内部状態へ反映し、その完全状態を `SwbtGamepadService` へ渡すことです。

## public surface

```python
class SwbtControllerOutputPort(ControllerOutputPort):
    def press(self, keys: tuple[KeyType, ...]) -> None:
        ...

    def hold(self, keys: tuple[KeyType, ...]) -> None:
        ...

    def release(self, keys: tuple[KeyType, ...] = ()) -> None:
        ...

    def keyboard(self, text: str) -> None:
        raise NotImplementedError("swbt backend does not support keyboard input.")

    def type_key(self, key: KeyCode | SpecialKeyCode) -> None:
        raise NotImplementedError("swbt backend does not support keyboard input.")

    def close(self) -> None:
        ...
```

`supports_touch` は既定値 `False` のままにします。`touch_down()`、`touch_up()`、`disable_sleep()` は `ControllerOutputPort` の既定実装に任せ、非対応を明示します。

## 操作の意味

NyXPy の `Command.press()` は次の意味です。

```text
controller.press(keys)
wait(dur)
controller.release(keys)
wait(wait)
```

このため、`SwbtControllerOutputPort.press()` の中で `swbt.tap()` は使いません。`tap()` は押下 report と release report を即時送信する action API であり、NyXPy の `press()` / `release()` の分離と意味がずれます。

swbt backend では次の対応にします。

| NyXPy port 操作 | swbt 側の処理 |
|---|---|
| `press(keys)` | 現在状態へ keys を追加し、完全状態を service へ反映する |
| `hold(keys)` | 現在状態を破棄し、keys のみを保持する状態を service へ反映する |
| `release(keys)` | 現在状態から keys を除去し、完全状態を service へ反映する |
| `release()` | 全入力を neutral へ戻す |
| `keyboard(text)` | 非対応として `NotImplementedError` |
| `type_key(key)` | 非対応として `NotImplementedError` |
| `touch_down` / `touch_up` | 非対応として `NotImplementedError` |
| `disable_sleep` | 非対応として `NotImplementedError` |

## 状態管理

port 側に NyXPy 用の状態を持たせます。service に差分操作を連続で投げるより、毎回 `InputState` を作って `apply()` へ渡す方が同時入力の扱いが明確です。

```python
from dataclasses import dataclass, field

from swbt import Button as SwbtButton
from swbt import Stick as SwbtStick


@dataclass
class NyxSwbtState:
    buttons: set[SwbtButton] = field(default_factory=set)
    left_stick: SwbtStick = field(default_factory=SwbtStick.center)
    right_stick: SwbtStick = field(default_factory=SwbtStick.center)
```

完全状態の生成は mapper に集約します。

```python
from swbt import InputState


def to_input_state(state: NyxSwbtState) -> InputState:
    return (
        InputState.neutral()
        .with_buttons(state.buttons)
        .with_sticks(
            left_stick=state.left_stick,
            right_stick=state.right_stick,
        )
    )
```

## 実装骨子

```python
from threading import RLock

from nyxpy.framework.core.constants import KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.io.ports import ControllerOutputPort


class SwbtControllerOutputPort(ControllerOutputPort):
    def __init__(
        self,
        *,
        service: SwbtGamepadService,
        mapper: NyxSwbtInputMapper,
    ) -> None:
        self._service = service
        self._mapper = mapper
        self._state = NyxSwbtState()
        self._lock = RLock()
        self._closed = False

    def press(self, keys: tuple[KeyType, ...]) -> None:
        with self._lock:
            self._ensure_open()
            self._mapper.add_to_state(self._state, keys)
            self._apply_locked()

    def hold(self, keys: tuple[KeyType, ...]) -> None:
        with self._lock:
            self._ensure_open()
            self._state = NyxSwbtState()
            self._mapper.add_to_state(self._state, keys)
            self._apply_locked()

    def release(self, keys: tuple[KeyType, ...] = ()) -> None:
        with self._lock:
            self._ensure_open()
            if not keys:
                self._state = NyxSwbtState()
                self._service.neutral()
                return
            self._mapper.remove_from_state(self._state, keys)
            self._apply_locked()

    def keyboard(self, text: str) -> None:
        raise NotImplementedError("swbt backend does not support keyboard input.")

    def type_key(self, key: KeyCode | SpecialKeyCode) -> None:
        raise NotImplementedError("swbt backend does not support keyboard input.")

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._state = NyxSwbtState()
            self._service.neutral()
            self._closed = True

    def _apply_locked(self) -> None:
        state = self._mapper.to_input_state(self._state)
        self._service.apply(state)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("controller output port is closed")
```

この skeleton では `RuntimeError` を使っていますが、最終実装では NyXPy の例外体系に合わせて `DeviceError` または `ConfigurationError` 派生の専用例外へ寄せます。

## 例外変換

`swbt-python` の例外は NyXPy の framework error へ変換します。macro 側へ `SwbtError` をそのまま漏らさない方針です。

| swbt 側 | NyXPy 側 |
|---|---|
| `TransportOpenError` | `ConfigurationError(code="NYX_SWBT_TRANSPORT_OPEN_FAILED")` |
| `ConnectionTimeoutError` | `ConfigurationError(code="NYX_SWBT_CONNECTION_TIMED_OUT")` |
| `ConnectionFailedError` | `ConfigurationError(code="NYX_SWBT_CONNECTION_FAILED")` |
| `InvalidKeyStoreError` | `ConfigurationError(code="NYX_SWBT_KEY_STORE_INVALID")` |
| `InvalidInputError` | `ValueError` または `DeviceError(code="NYX_SWBT_INPUT_INVALID")` |
| `ClosedError` | `DeviceError(code="NYX_SWBT_NOT_CONNECTED")` |

`ConfigurationError` に寄せるのは、adapter、key store、pairing 許可、connect timeout といった構成問題が多いためです。実行中の切断は `DeviceError` として扱います。

## close と finalize

`MacroRuntime` は実行終了時に controller port を close します。swbt backend では `close()` で neutral を送るため、マクロの `finalize()` でも `cmd.release()` を呼ぶと二重 neutral になります。これは許容します。二重 neutral は安全側の操作であり、状態を壊しません。

## 即時送信について

`swbt-python` の `press()`、`release()`、`sticks()`、`neutral()` は state update API であり、即時送信を保証しません。`tap()` は即時 report を送る action API ですが、NyXPy の port 契約とは一致しません。

そのため、初期実装では「NyXPy の状態を swbt の local state へ反映し、周期 report loop で送る」設計にします。厳密な即時送信が必要になった場合は、`swbt-python` 側に public `flush()` または `send_current()` 相当を追加してから使います。private method へ依存しません。
