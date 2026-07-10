"""swbt ControllerOutputPort 実装。"""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock

from nyxpy.framework.core.constants import IMUFrame, KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.hardware.swbt.config import SwbtControllerModel
from nyxpy.framework.core.hardware.swbt.errors import swbt_port_closed
from nyxpy.framework.core.hardware.swbt.mapper import NyxSwbtInputMapper, NyxSwbtState
from nyxpy.framework.core.io.ports import ControllerOutputPort

type CloseCallback = Callable[["SwbtControllerOutputPort"], None]


class SwbtControllerOutputPort(ControllerOutputPort):
    """swbt session に完全な InputState を渡す controller port。"""

    def __init__(
        self,
        *,
        session,
        model: SwbtControllerModel,
        mapper: NyxSwbtInputMapper | None = None,
        on_close: CloseCallback | None = None,
    ) -> None:
        """session、model、mapper、初期 state を保持し、neutral を送る。"""
        self._session = session
        self._mapper = mapper or NyxSwbtInputMapper(model)
        self._on_close = on_close
        self._state = NyxSwbtState.neutral()
        self._lock = RLock()
        self._closed = False
        self._session.neutral()

    @property
    def supports_imu(self) -> bool:
        """Swbt backend は IMU 入力に対応する。"""
        return True

    def press(self, keys: tuple[KeyType, ...]) -> None:
        """Keys を現在状態へ追加して送信する。"""
        with self._lock:
            self._ensure_open()
            self._state = self._mapper.press(self._state, keys)
            self._apply_locked()

    def hold(self, keys: tuple[KeyType, ...]) -> None:
        """現在状態を破棄し、keys だけを保持して送信する。"""
        with self._lock:
            self._ensure_open()
            self._state = self._mapper.hold(keys)
            self._apply_locked()

    def release(self, keys: tuple[KeyType, ...] = ()) -> None:
        """Keys を解放する。keys が空なら全入力を neutral に戻す。"""
        with self._lock:
            self._ensure_open()
            self._state = self._mapper.release(self._state, keys)
            if keys:
                self._apply_locked()
            else:
                self._session.neutral()

    def imu(self, *frames: IMUFrame) -> None:
        """IMU frame を現在状態へ反映して送信する。"""
        with self._lock:
            self._ensure_open()
            self._state = self._mapper.set_imu(self._state, frames)
            self._apply_locked()

    def keyboard(self, text: str) -> None:
        """Swbt backend は keyboard 入力を持たない。"""
        raise NotImplementedError("swbt backend does not support keyboard input.")

    def type_key(self, key: KeyCode | SpecialKeyCode) -> None:
        """Swbt backend は keyboard 入力を持たない。"""
        raise NotImplementedError("swbt backend does not support keyboard input.")

    def touch_down(self, x: int, y: int) -> None:
        """Swbt backend は touch 入力を持たない。"""
        raise NotImplementedError("swbt backend does not support touch input.")

    def touch_up(self) -> None:
        """Swbt backend は touch 入力を持たない。"""
        raise NotImplementedError("swbt backend does not support touch input.")

    def disable_sleep(self, enabled: bool = True) -> None:
        """Swbt backend は sleep control を持たない。"""
        raise NotImplementedError("swbt backend does not support sleep control.")

    def close(self) -> None:
        """Neutral を試みるが session 自体は閉じない。"""
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

    def _apply_locked(self) -> None:
        self._session.apply(self._mapper.to_input_state(self._state))

    def _ensure_open(self) -> None:
        if self._closed:
            raise swbt_port_closed()
