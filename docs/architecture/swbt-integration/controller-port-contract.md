# SwbtControllerOutputPort の契約

`SwbtControllerOutputPort` は NyXPy の `ControllerOutputPort` を実装する。責務は、NyXPy の `KeyType` / `IMUFrame` 入力を内部状態へ反映し、完全な `swbt.InputState` として `SwbtControllerSession.apply()` へ渡すことに限定する。

実装 module は `nyxpy.framework.core.hardware.swbt.controller` である。

## public surface

```python
class SwbtControllerOutputPort(ControllerOutputPort):
    def press(self, keys: tuple[KeyType, ...]) -> None: ...
    def hold(self, keys: tuple[KeyType, ...]) -> None: ...
    def release(self, keys: tuple[KeyType, ...] = ()) -> None: ...
    def imu(self, *frames: IMUFrame) -> None: ...

    def keyboard(self, text: str) -> None:
        raise NotImplementedError("swbt backend does not support keyboard input.")

    def type_key(self, key: KeyCode | SpecialKeyCode) -> None:
        raise NotImplementedError("swbt backend does not support keyboard input.")

    def close(self) -> None: ...

    @property
    def supports_imu(self) -> bool:
        return True
```

`supports_touch` は `False` である。`touch_down()`、`touch_up()`、`disable_sleep()` は非対応を明示する。

## 操作の意味

NyXPy の `Command.press()` は次の手順である。

```text
controller.press(keys)
wait(dur)
controller.release(keys)
wait(wait)
```

そのため、`SwbtControllerOutputPort.press()` では `swbt.tap()` を使わない。`tap()` は押下 report と押上 report を含む action API であり、NyXPy port の `press()` / `release()` 分離と一致しない。

NyXPy の `Command.hold()` は、現在のキー入力の内部状態を破棄し、指定されたキー入力に変更する操作である。swbt backend でもこの意味に合わせる。

| NyXPy port 操作 | swbt backend の処理 |
|---|---|
| `press(keys)` | 現在状態へ keys を追加し、完全状態を `apply()` する |
| `hold(keys)` | 現在状態を破棄し、keys だけを保持する状態を `apply()` する |
| `release(keys)` | 現在状態から keys を除去し、完全状態を `apply()` する |
| `release()` | 全入力を neutral へ戻す。IMU も neutral に戻す |
| `imu(*frames)` | 現在状態の IMU 部分だけを置き換え、完全状態を `apply()` する |
| `keyboard(text)` | 非対応として `NotImplementedError` |
| `type_key(key)` | 非対応として `NotImplementedError` |
| `touch_down` / `touch_up` | 非対応として `NotImplementedError` |
| `disable_sleep` | 非対応として `NotImplementedError` |

## 状態管理

port 側に NyXPy 用の入力状態を持たせる。session に部分更新を投げ続けるのではなく、毎回 `InputState` を構築して `apply()` する。

```python
from dataclasses import dataclass, field
from swbt import Button as SwbtButton
from swbt import IMUFrame as SwbtIMUFrame
from swbt import Stick as SwbtStick


@dataclass
class NyxSwbtState:
    buttons: frozenset[Button] = field(default_factory=frozenset)
    dpad_buttons: frozenset[object] = field(default_factory=frozenset)
    left_stick: LStick | None = None
    right_stick: RStick | None = None
    imu_frames: tuple[IMUFrame, IMUFrame, IMUFrame] = field(default_factory=_neutral_imu_frames)
```

完全状態の構築は mapper に集約する。

```python
from swbt import InputState


class NyxSwbtInputMapper:
    def to_input_state(self, state: NyxSwbtState) -> InputState:
        return (
            InputState.neutral()
            .with_buttons(state.buttons)
            .with_sticks(
                left_stick=state.left_stick,
                right_stick=state.right_stick,
            )
            .with_imu(*state.imu_frames)
        )
```

## 実装骨子

```python
from threading import RLock

from nyxpy.framework.core.constants import IMUFrame, KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.io.ports import ControllerOutputPort


class SwbtControllerOutputPort(ControllerOutputPort):
    def __init__(
        self,
        *,
        session: SwbtControllerSession,
        model: SwbtControllerModel,
        mapper: NyxSwbtInputMapper | None = None,
        on_close: CloseCallback | None = None,
    ) -> None:
        self._session = session
        self._mapper = mapper or NyxSwbtInputMapper(model)
        self._on_close = on_close
        self._state = NyxSwbtState.neutral()
        self._lock = RLock()
        self._closed = False
        self._session.neutral()

    def press(self, keys: tuple[KeyType, ...]) -> None:
        with self._lock:
            self._ensure_open()
            self._apply_locked(self._mapper.press(self._state, keys))

    def hold(self, keys: tuple[KeyType, ...]) -> None:
        with self._lock:
            self._ensure_open()
            self._apply_locked(self._mapper.hold(keys))

    def release(self, keys: tuple[KeyType, ...] = ()) -> None:
        with self._lock:
            self._ensure_open()
            next_state = self._mapper.release(self._state, keys)
            if keys:
                self._apply_locked(next_state)
            else:
                self._session.neutral()
                self._state = next_state

    def imu(self, *frames: IMUFrame) -> None:
        with self._lock:
            self._ensure_open()
            self._apply_locked(self._mapper.set_imu(self._state, frames))

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._state = NyxSwbtState.neutral()
            try:
                self._session.neutral()
            finally:
                self._closed = True
                if self._on_close is not None:
                    self._on_close(self)

    def _apply_locked(self, next_state: NyxSwbtState) -> None:
        self._session.apply(self._mapper.to_input_state(next_state))
        self._state = next_state
```

## close と finalize

`MacroRuntime` は実行終了時に controller port を close する。swbt backend では `close()` で neutral を試みる。マクロの `finalize()` でも `cmd.release()` を呼ぶ場合、neutral が重なるが、安全側の操作として許容する。

transport の完全 close は `SwbtControllerOutputPortFactory.close()` から `SwbtControllerSession.close()` を呼ぶことで行う。

`SwbtControllerOutputPort` は close 時に factory へ通知し、factory は session key ごとの active port cache から閉じた port を外す。これにより、GUI manual input と macro runtime が同じ session に対して別々の state holder として残らない。

port 作成時の neutral は常に試みる。`reset_on_port_create` という設定や constructor 引数は持たない。

## 短い押下の扱い

swbt backendは押下と解放をそれぞれ完全な `InputState` として `send()` する。周期report loopが押下状態を観測することには依存しない。

`send()` の完了はHCI送信完了やSwitch側の認識完了を意味しない。実機で短い入力を多用するマクロは16ms、33ms、50msを個別に確認し、確認済みの最小durationを利用者向け文書へ記録する。
