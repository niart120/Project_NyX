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
    buttons: set[SwbtButton] = field(default_factory=set)
    left_stick: SwbtStick = field(default_factory=SwbtStick.center)
    right_stick: SwbtStick = field(default_factory=SwbtStick.center)
    imu_frames: tuple[SwbtIMUFrame, SwbtIMUFrame, SwbtIMUFrame] = field(
        default_factory=lambda: (
            SwbtIMUFrame.neutral(),
            SwbtIMUFrame.neutral(),
            SwbtIMUFrame.neutral(),
        )
    )
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
        mapper: NyxSwbtInputMapper,
    ) -> None:
        self._session = session
        self._mapper = mapper
        self._state = NyxSwbtState()
        self._lock = RLock()
        self._closed = False
        self._session.neutral()

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
                self._session.neutral()
                return
            self._mapper.remove_from_state(self._state, keys)
            self._apply_locked()

    def imu(self, *frames: IMUFrame) -> None:
        with self._lock:
            self._ensure_open()
            self._mapper.set_imu(self._state, frames)
            self._apply_locked()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._state = NyxSwbtState()
            self._session.neutral()
            self._closed = True

    def _apply_locked(self) -> None:
        state = self._mapper.to_input_state(self._state)
        self._session.apply(state)
```

## close と finalize

`MacroRuntime` は実行終了時に controller port を close する。swbt backend では `close()` で neutral を試みる。マクロの `finalize()` でも `cmd.release()` を呼ぶ場合、neutral が重なるが、安全側の操作として許容する。

transport の完全 close は `SwbtControllerOutputPortFactory.close()` から `SwbtControllerSession.close()` を呼ぶことで行う。

port 作成時の neutral は常に試みる。`reset_on_port_create` という設定や constructor 引数は持たない。

## 短い押下の扱い

swbt の state update API は即時送信を保証しない。NyXPy の `press(dur=...)` は、report loop による反映を前提にする。

`dur` が `report_period_us` より短い場合、対象機器が押下を観測できない可能性がある。実機で短い入力を多用するマクロは、backend ごとの最小押下時間を検証する。
