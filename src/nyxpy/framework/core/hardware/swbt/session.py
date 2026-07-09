"""swbt controller lifecycle session。"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from threading import Event, RLock, Thread, current_thread
from typing import Protocol, TextIO

from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, SwbtControllerType
from nyxpy.framework.core.hardware.swbt.errors import (
    map_swbt_exception,
    swbt_configuration_error,
    swbt_not_connected,
)

type SwbtControllerFactory = Callable[[SwbtControllerConfig, TextIO | None], object]


class SwbtControllerSessionProtocol(Protocol):
    """Factory と port が使う swbt session protocol。"""

    @property
    def connected(self) -> bool: ...

    def open(self) -> None: ...

    def pair(self, *, timeout_sec: float) -> object: ...

    def reconnect(self, *, timeout_sec: float) -> object: ...

    def apply(self, state: object) -> None: ...

    def neutral(self) -> None: ...

    def status(self) -> object: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class DummySwbtStatus:
    """Dummy session が返す最小 status。"""

    connected: bool
    message: str = "dummy"


class SwbtControllerSession:
    """swbt controller instance と lifecycle を所有する session。"""

    def __init__(
        self,
        config: SwbtControllerConfig,
        *,
        controller_factory: SwbtControllerFactory | None = None,
        diagnostics_writer: TextIO | None = None,
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
        self._operation_timeout_sec = max(5.0, config.connect_timeout_sec)
        self._opened = False
        self._connected = False
        self._closed = False

    @property
    def connected(self) -> bool:
        """Session が接続済みかどうか。"""
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
            except Exception as exc:
                self._stop_loop_locked()
                raise map_swbt_exception(exc, component=type(self).__name__) from exc
            self._controller = controller
            self._opened = True
            self._closed = False

    def pair(self, *, timeout_sec: float) -> object:
        """明示 pairing を実行する。"""
        with self._lock:
            self.open()
            controller = self._require_controller()
            try:
                result = self._call_controller(controller, "pair", timeout=timeout_sec)
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc
            self._connected = True
            return result

    def reconnect(self, *, timeout_sec: float) -> object:
        """保存済み pairing key に基づく reconnect を実行する。"""
        with self._lock:
            self.open()
            controller = self._require_controller()
            try:
                result = self._call_controller(controller, "reconnect", timeout=timeout_sec)
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc
            self._connected = True
            return result

    def apply(self, state: object) -> None:
        """完全な swbt InputState を controller へ適用する。"""
        with self._lock:
            controller = self._require_connected_controller()
            try:
                self._call_controller(controller, "apply", state)
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc

    def neutral(self) -> None:
        """全入力を neutral に戻す。"""
        with self._lock:
            controller = self._require_connected_controller()
            try:
                self._call_controller(controller, "neutral")
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc

    def status(self) -> object:
        """Controller status を返す。"""
        with self._lock:
            controller = self._require_controller()
            try:
                return self._call_controller(controller, "status")
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc

    def close(self) -> None:
        """neutral=True で controller を閉じる。idempotent。"""
        with self._lock:
            if self._closed:
                return
            controller = self._controller
            self._connected = False
            self._opened = False
            self._closed = True
            if controller is None:
                self._stop_loop_locked()
                return
            try:
                self._call_controller(controller, "close", neutral=True)
            except Exception as exc:
                raise map_swbt_exception(exc, component=type(self).__name__) from exc
            finally:
                self._stop_loop_locked()

    def _require_controller(self) -> object:
        if self._controller is None:
            raise swbt_not_connected(type(self).__name__)
        return self._controller

    def _require_connected_controller(self) -> object:
        if not self._connected:
            raise swbt_not_connected(type(self).__name__)
        return self._require_controller()

    def _call_controller(self, controller: object, method_name: str, *args, **kwargs) -> object:
        result = getattr(controller, method_name)(*args, **kwargs)
        if inspect.isawaitable(result):
            self._ensure_loop_locked()
            return self._run_awaitable(result)
        return result

    def _run_awaitable(self, awaitable: Awaitable[object]) -> object:
        loop = self._loop
        if loop is None or not loop.is_running():
            raise swbt_configuration_error(
                "swbt event loop is not running",
                code="NYX_SWBT_EVENT_LOOP_NOT_RUNNING",
                component=type(self).__name__,
            )
        future = asyncio.run_coroutine_threadsafe(_await_result(awaitable), loop)
        try:
            return future.result(timeout=self._operation_timeout_sec)
        except FutureTimeoutError:
            future.cancel()
            raise

    def _ensure_loop_locked(self) -> None:
        if self._loop is not None and self._loop.is_running():
            return

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
        self._loop = None
        self._loop_thread = None
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None and thread.is_alive() and thread is not current_thread():
            thread.join(timeout=self._operation_timeout_sec)


async def _await_result(awaitable: Awaitable[object]) -> object:
    return await awaitable


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

    def pair(self, *, timeout_sec: float) -> DummySwbtStatus:
        """Dummy pairing を記録する。"""
        self.open()
        self.pair_calls += 1
        self.connected = True
        return DummySwbtStatus(connected=True, message="paired")

    def reconnect(self, *, timeout_sec: float) -> DummySwbtStatus:
        """Dummy reconnect を記録する。"""
        self.open()
        self.reconnect_calls += 1
        self.connected = True
        return DummySwbtStatus(connected=True, message="reconnected")

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
        return DummySwbtStatus(connected=self.connected)

    def close(self) -> None:
        """Dummy session を閉じる。"""
        self.closed = True
        self.connected = False


def create_swbt_controller(
    config: SwbtControllerConfig,
    diagnostics_writer: TextIO | None = None,
) -> object:
    """SwbtControllerConfig から swbt controller instance を作る。"""
    controller_cls = resolve_swbt_controller_class(config.model.controller_type)
    diagnostics = None
    if diagnostics_writer is not None:
        from swbt import DiagnosticsConfig

        diagnostics = DiagnosticsConfig(trace_writer=diagnostics_writer)
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
