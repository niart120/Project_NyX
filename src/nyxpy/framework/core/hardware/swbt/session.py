"""swbt controller lifecycle session。"""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from threading import Event, RLock, Thread, current_thread
from typing import Protocol, TextIO, cast

from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, SwbtControllerType
from nyxpy.framework.core.hardware.swbt.diagnostics import DiagnosticsWriter
from nyxpy.framework.core.hardware.swbt.errors import (
    map_swbt_exception,
    swbt_configuration_error,
    swbt_not_connected,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError, DeviceError

type SwbtControllerFactory = Callable[[SwbtControllerConfig, DiagnosticsWriter | None], object]


class SwbtControllerSessionProtocol(Protocol):
    """Factory と port が使う swbt session protocol。"""

    @property
    def connected(self) -> bool: ...

    def open(self) -> None: ...

    def pair(self, *, timeout_sec: float, cancellation_event: Event | None = None) -> None: ...

    def reconnect(self, *, timeout_sec: float, cancellation_event: Event | None = None) -> None: ...

    def apply(self, state: object) -> None: ...

    def neutral(self) -> None: ...

    def status(self) -> object: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class DummySwbtStatus:
    """実 ``swbt.GamepadStatus`` と同じ公開形状の dummy status。"""

    connection_state: str
    report_counters: dict[int, int] = field(default_factory=dict)
    last_subcommand_id: int | None = None
    raw_rumble: bytes | None = None
    last_error: object | None = None


def is_swbt_status_connected(status: object) -> bool:
    """Swbt status が接続完了状態かを実 API の field から判定する。"""
    return getattr(status, "connection_state", None) == "connected"


class SwbtControllerSession:
    """swbt controller instance と lifecycle を所有する session。"""

    def __init__(
        self,
        config: SwbtControllerConfig,
        *,
        controller_factory: SwbtControllerFactory | None = None,
        diagnostics_writer: DiagnosticsWriter | None = None,
    ) -> None:
        """config、controller factory、diagnostics writer を保持する。"""
        self.config = config
        self._controller_factory = controller_factory or create_swbt_controller
        self._diagnostics_writer = diagnostics_writer
        self._controller: object | None = None
        self._lock = RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: Thread | None = None
        self._loop_ready = Event()
        self._loop_stopping = False
        self._cancellation_timeout_sec = 1.0
        self._loop_stop_timeout_sec = 1.0
        self._operation_timeout_sec = max(5.0, config.connect_timeout_sec)
        self._opened = False
        self._connected = False
        self._closed = False

    @property
    def connected(self) -> bool:
        """Session が接続済みかどうか。"""
        with self._lock:
            if not self._connected or not self._opened or self._controller is None:
                return False
            try:
                status = self._call_controller(self._controller, "status")
            except (ConfigurationError, DeviceError):
                raise
            except Exception:
                self._connected = False
                return False
            self._connected = is_swbt_status_connected(status)
            return self._connected

    def open(self) -> None:
        """Controller resource を開く。pairing / reconnect は開始しない。"""
        with self._lock:
            if self._opened:
                return
            if not self.config.adapter:
                raise swbt_configuration_error(
                    "swbt adapter is not selected",
                    code="NYX_SWBT_ADAPTER_NOT_SELECTED",
                    component=type(self).__name__,
                )
            try:
                controller = self._controller_factory(self.config, self._diagnostics_writer)
                self._call_controller(controller, "open")
            except (ConfigurationError, DeviceError):
                self._stop_loop_locked()
                raise
            except Exception as exc:
                self._stop_loop_locked()
                raise map_swbt_exception(exc, component=type(self).__name__) from exc
            self._controller = controller
            self._opened = True
            self._closed = False

    def pair(self, *, timeout_sec: float, cancellation_event: Event | None = None) -> None:
        """明示 pairing を実行する。"""
        with self._lock:
            self.open()
            controller = self._require_controller()
            try:
                self._call_controller(
                    controller,
                    "pair",
                    timeout=timeout_sec,
                    _wait_timeout_sec=self._connection_wait_timeout(timeout_sec),
                    _cancellation_event=cancellation_event,
                    _cancellation_code="NYX_SWBT_PAIR_CANCELLED",
                )
                status = self._call_controller(controller, "status")
            except (ConfigurationError, DeviceError):
                raise
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc
            self._connected = is_swbt_status_connected(status)
            if not self._connected:
                raise swbt_not_connected(type(self).__name__)

    def reconnect(self, *, timeout_sec: float, cancellation_event: Event | None = None) -> None:
        """保存済み pairing key に基づく reconnect を実行する。"""
        with self._lock:
            self.open()
            controller = self._require_controller()
            try:
                self._call_controller(
                    controller,
                    "reconnect",
                    timeout=timeout_sec,
                    _wait_timeout_sec=self._connection_wait_timeout(timeout_sec),
                    _cancellation_event=cancellation_event,
                    _cancellation_code="NYX_SWBT_RECONNECT_CANCELLED",
                )
                status = self._call_controller(controller, "status")
            except (ConfigurationError, DeviceError):
                raise
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc
            self._connected = is_swbt_status_connected(status)
            if not self._connected:
                raise swbt_not_connected(type(self).__name__)

    def apply(self, state: object) -> None:
        """完全な swbt InputState を controller へ適用する。"""
        with self._lock:
            controller = self._require_connected_controller()
            try:
                self._call_controller(controller, "apply", state)
            except (ConfigurationError, DeviceError):
                raise
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc

    def neutral(self) -> None:
        """全入力を neutral に戻す。"""
        with self._lock:
            controller = self._require_connected_controller()
            try:
                self._call_controller(controller, "neutral")
            except (ConfigurationError, DeviceError):
                raise
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc

    def status(self) -> object:
        """Controller status を返す。"""
        with self._lock:
            controller = self._require_controller()
            try:
                status = self._call_controller(controller, "status")
            except (ConfigurationError, DeviceError):
                raise
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc
            self._connected = is_swbt_status_connected(status)
            return status

    def close(self) -> None:
        """neutral=True で controller を閉じる。idempotent。"""
        with self._lock:
            if self._loop_stopping:
                self._stop_loop_locked()
            if self._closed:
                return
            controller = self._controller
            self._connected = False
            if controller is None:
                self._opened = False
                self._closed = True
                self._stop_loop_locked()
                return

            controller_error: Exception | None = None
            try:
                self._call_controller(controller, "close", neutral=True)
            except (ConfigurationError, DeviceError) as exc:
                controller_error = exc
            except Exception as exc:
                controller_error = map_swbt_exception(exc, component=type(self).__name__)
            else:
                # controller の終端 close が成功した時点で再送信は不要。loop の
                # thread 所有だけが残った場合は次回 close 冒頭で回収する。
                self._opened = False
                self._closed = True

            loop_error: Exception | None = None
            try:
                self._stop_loop_locked()
            except (ConfigurationError, DeviceError) as exc:
                loop_error = exc

            errors = [error for error in (controller_error, loop_error) if error is not None]
            if len(errors) == 1:
                raise errors[0]
            if errors:
                raise ExceptionGroup("swbt session close failed", errors)

    def _require_controller(self) -> object:
        if self._controller is None:
            raise swbt_not_connected(type(self).__name__)
        return self._controller

    def _require_connected_controller(self) -> object:
        if not self.connected:
            raise swbt_not_connected(type(self).__name__)
        return self._require_controller()

    def _call_controller(
        self,
        controller: object,
        method_name: str,
        *args,
        _wait_timeout_sec: float | None = None,
        _cancellation_event: Event | None = None,
        _cancellation_code: str = "NYX_SWBT_OPERATION_CANCELLED",
        **kwargs,
    ) -> object:
        if self._loop_stopping:
            raise swbt_configuration_error(
                "swbt event loop is stopping",
                code="NYX_SWBT_EVENT_LOOP_NOT_RUNNING",
                component=type(self).__name__,
            )
        result = getattr(controller, method_name)(*args, **kwargs)
        if inspect.isawaitable(result):
            self._ensure_loop_locked()
            return self._run_awaitable(
                result,
                timeout_sec=_wait_timeout_sec or self._operation_timeout_sec,
                cancellation_event=_cancellation_event,
                cancellation_code=_cancellation_code,
            )
        return result

    def _run_awaitable(
        self,
        awaitable: Awaitable[object],
        *,
        timeout_sec: float,
        cancellation_event: Event | None = None,
        cancellation_code: str = "NYX_SWBT_OPERATION_CANCELLED",
    ) -> object:
        loop = self._loop
        if loop is None or not loop.is_running():
            raise swbt_configuration_error(
                "swbt event loop is not running",
                code="NYX_SWBT_EVENT_LOOP_NOT_RUNNING",
                component=type(self).__name__,
            )
        completed = Event()
        future = asyncio.run_coroutine_threadsafe(_await_result(awaitable, completed), loop)
        try:
            if cancellation_event is None:
                return future.result(timeout=timeout_sec)
            deadline = time.monotonic() + timeout_sec
            while True:
                if cancellation_event.is_set():
                    future.cancel()
                    completed.wait(timeout=self._cancellation_timeout_sec)
                    raise DeviceError(
                        "swbt connection operation was cancelled",
                        code=cancellation_code,
                        component=type(self).__name__,
                        recoverable=True,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return future.result(timeout=0)
                try:
                    return future.result(timeout=min(0.05, remaining))
                except FutureTimeoutError:
                    continue
        except FutureTimeoutError:
            future.cancel()
            if not completed.wait(timeout=self._cancellation_timeout_sec):
                self._stop_loop_locked()
            raise

    def _connection_wait_timeout(self, connection_timeout_sec: float) -> float:
        """Swbt 自身の接続 timeout より外側の待機期限を長くする。"""
        return max(self._operation_timeout_sec, connection_timeout_sec + 1.0)

    def _ensure_loop_locked(self) -> None:
        if self._loop_stopping:
            raise swbt_configuration_error(
                "swbt event loop is stopping",
                code="NYX_SWBT_EVENT_LOOP_NOT_RUNNING",
                component=type(self).__name__,
            )

        loop = self._loop
        thread = self._loop_thread
        if thread is not None:
            if thread.is_alive():
                if loop is not None and loop.is_running():
                    return
                raise swbt_configuration_error(
                    "swbt event loop thread is alive but not running",
                    code="NYX_SWBT_EVENT_LOOP_NOT_RUNNING",
                    component=type(self).__name__,
                )
            self._loop = None
            self._loop_thread = None
        elif loop is not None:
            self._loop = None

        self._loop_ready.clear()

        def run_loop() -> None:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            self._loop_ready.set()
            loop.run_forever()
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

        self._loop_thread = Thread(
            target=run_loop,
            name="SwbtControllerSessionLoop",
            daemon=True,
        )
        self._loop_thread.start()
        if not self._loop_ready.wait(timeout=self._operation_timeout_sec):
            raise swbt_configuration_error(
                "swbt event loop did not start",
                code="NYX_SWBT_EVENT_LOOP_NOT_RUNNING",
                component=type(self).__name__,
            )

    def _stop_loop_locked(self) -> None:
        loop = self._loop
        thread = self._loop_thread
        if thread is None or not thread.is_alive():
            self._loop = None
            self._loop_thread = None
            self._loop_stopping = False
            return
        if thread is current_thread():
            raise swbt_configuration_error(
                "swbt event loop cannot stop itself synchronously",
                code="NYX_SWBT_EVENT_LOOP_DID_NOT_STOP",
                component=type(self).__name__,
            )

        self._loop_stopping = True
        if loop is not None and loop.is_running():
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception as exc:
                raise swbt_configuration_error(
                    "swbt event loop stop request failed",
                    code="NYX_SWBT_EVENT_LOOP_DID_NOT_STOP",
                    component=type(self).__name__,
                    cause=exc,
                ) from exc
        thread.join(timeout=self._loop_stop_timeout_sec)
        if thread.is_alive():
            raise swbt_configuration_error(
                "swbt event loop did not stop",
                code="NYX_SWBT_EVENT_LOOP_DID_NOT_STOP",
                component=type(self).__name__,
            )
        self._loop = None
        self._loop_thread = None
        self._loop_stopping = False


async def _await_result(awaitable: Awaitable[object], completed: Event) -> object:
    try:
        return await awaitable
    finally:
        completed.set()


class DummySwbtControllerSession:
    """実機なしテストで InputState を記録する session double。"""

    def __init__(self) -> None:
        """記録用の状態を初期化する。"""
        self.opened = False
        self.connected = False
        self.closed = False
        self.pair_calls = 0
        self.reconnect_calls = 0
        self.states: list[object] = []
        self.neutral_calls = 0

    def open(self) -> None:
        """Bluetooth transport を開かず opened にする。"""
        self.opened = True
        self.closed = False

    def pair(self, *, timeout_sec: float, cancellation_event: Event | None = None) -> None:
        """Dummy pairing を記録する。"""
        self.open()
        self.pair_calls += 1
        self.connected = True

    def reconnect(self, *, timeout_sec: float, cancellation_event: Event | None = None) -> None:
        """Dummy reconnect を記録する。"""
        self.open()
        self.reconnect_calls += 1
        self.connected = True

    def apply(self, state: object) -> None:
        """適用された state を記録する。"""
        if not self.connected:
            raise swbt_not_connected(type(self).__name__)
        self.states.append(state)

    def neutral(self) -> None:
        """Neutral 呼び出しを記録する。"""
        if not self.connected:
            raise swbt_not_connected(type(self).__name__)
        self.neutral_calls += 1

    def status(self) -> DummySwbtStatus:
        """Dummy status を返す。"""
        return DummySwbtStatus(
            connection_state="connected" if self.connected else "closed",
        )

    def close(self) -> None:
        """Dummy session を閉じる。"""
        self.closed = True
        self.connected = False


def create_swbt_controller(
    config: SwbtControllerConfig,
    diagnostics_writer: DiagnosticsWriter | None = None,
) -> object:
    """SwbtControllerConfig から swbt controller instance を作る。"""
    controller_cls = resolve_swbt_controller_class(config.model.controller_type)
    diagnostics = None
    if diagnostics_writer is not None:
        from swbt import DiagnosticsConfig

        diagnostics = DiagnosticsConfig(trace_writer=cast(TextIO, diagnostics_writer))
    return controller_cls(
        adapter=config.adapter,
        key_store_path=str(config.key_store_path),
        report_period_us=config.report_period_us,
        diagnostics=diagnostics,
    )


def resolve_swbt_controller_class(controller_type: SwbtControllerType):
    """Controller type に対応する swbt root module の class を返す。"""
    from swbt import JoyConL, JoyConR, ProController

    if controller_type is SwbtControllerType.PRO_CONTROLLER:
        return ProController
    if controller_type is SwbtControllerType.JOY_CON_L:
        return JoyConL
    if controller_type is SwbtControllerType.JOY_CON_R:
        return JoyConR
    raise swbt_configuration_error(
        f"unsupported swbt controller type: {controller_type}",
        code="NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED",
        component="SwbtControllerSession",
    )
