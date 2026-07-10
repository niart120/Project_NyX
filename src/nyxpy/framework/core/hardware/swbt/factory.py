"""swbt ControllerOutputPort factory。"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, SwbtControllerType
from nyxpy.framework.core.hardware.swbt.controller import SwbtControllerOutputPort
from nyxpy.framework.core.hardware.swbt.session import (
    DummySwbtControllerSession,
    SwbtControllerSession,
    SwbtControllerSessionProtocol,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError, DeviceError

type SessionFactory = Callable[[SwbtControllerConfig], SwbtControllerSessionProtocol]
type DummySessionFactory = Callable[[], SwbtControllerSessionProtocol]


@dataclass(frozen=True, slots=True)
class SwbtSessionKey:
    """factory session cache の key。"""

    controller_type: SwbtControllerType
    adapter: str | None
    key_store_path: Path
    report_period_us: int | None


class SwbtControllerOutputPortFactory:
    """swbt session cache と lifecycle 操作を所有する factory。"""

    def __init__(
        self,
        *,
        session_factory: SessionFactory | None = None,
        dummy_session_factory: DummySessionFactory | None = None,
    ) -> None:
        """Session factory と cache を初期化する。"""
        self._session_factory = session_factory or (lambda config: SwbtControllerSession(config))
        self._dummy_session_factory = dummy_session_factory or DummySwbtControllerSession
        self._sessions: dict[SwbtSessionKey, SwbtControllerSessionProtocol] = {}
        self._dummy_session_keys: set[SwbtSessionKey] = set()
        self._active_ports: dict[SwbtSessionKey, SwbtControllerOutputPort] = {}
        self._lock = RLock()

    def create(
        self,
        *,
        config: SwbtControllerConfig,
        allow_dummy: bool,
        timeout_sec: float | None = None,
    ) -> SwbtControllerOutputPort:
        """Runtime / GUI lifetime 用 port を作る。pairing は暗黙実行しない。"""
        with self._lock:
            key = session_key(config)
            session = self._sessions.get(key)
            if session is not None and key in self._dummy_session_keys and not allow_dummy:
                self._discard_session(key, session)
                session = None
            if session is None:
                session = self._session_factory(config)
                self._sessions[key] = session
                self._dummy_session_keys.discard(key)
            try:
                session.open()
                if not session.connected:
                    session.reconnect(timeout_sec=timeout_sec or config.connect_timeout_sec)
            except (ConfigurationError, DeviceError):
                self._discard_session(key, session)
                if not allow_dummy:
                    raise
                session = self._dummy_session_factory()
                session.open()
                session.reconnect(timeout_sec=timeout_sec or config.connect_timeout_sec)
                self._sessions[key] = session
                self._dummy_session_keys.add(key)
            return self._activate_port(key, session, config)

    def pair(self, config: SwbtControllerConfig, *, timeout_sec: float | None = None) -> object:
        """明示 pairing を実行する。dummy fallback はしない。"""
        with self._lock:
            key = session_key(config)
            self._close_active_port(key)
            session = self._session_for(config)
            try:
                session.open()
                return session.pair(timeout_sec=timeout_sec or config.connect_timeout_sec)
            except (ConfigurationError, DeviceError):
                self._discard_session(key, session)
                raise

    def reconnect(
        self, config: SwbtControllerConfig, *, timeout_sec: float | None = None
    ) -> object:
        """明示 reconnect を実行する。dummy fallback はしない。"""
        with self._lock:
            key = session_key(config)
            self._close_active_port(key)
            session = self._session_for(config)
            try:
                session.open()
                return session.reconnect(timeout_sec=timeout_sec or config.connect_timeout_sec)
            except (ConfigurationError, DeviceError):
                self._discard_session(key, session)
                raise

    def disconnect(self, config: SwbtControllerConfig) -> None:
        """factory-managed cached session だけを閉じる。"""
        with self._lock:
            key = session_key(config)
            session = self._sessions.pop(key, None)
            self._dummy_session_keys.discard(key)
            active_port = self._active_ports.pop(key, None)
            if session is None and active_port is None:
                return
            try:
                if active_port is not None:
                    active_port.close()
                elif session is not None:
                    session.neutral()
            finally:
                if session is not None:
                    session.close()

    def status(self, config: SwbtControllerConfig) -> object | None:
        """factory-managed cached session の status を返す。"""
        with self._lock:
            session = self._sessions.get(session_key(config))
            if session is None:
                return None
            return session.status()

    def close(self) -> None:
        """Cache している session をすべて閉じる。"""
        with self._lock:
            errors: list[Exception] = []
            ports = tuple(self._active_ports.values())
            sessions = tuple(self._sessions.values())
            self._active_ports.clear()
            self._sessions.clear()
            self._dummy_session_keys.clear()
            for port in ports:
                try:
                    port.close()
                except Exception as exc:
                    errors.append(exc)
            for session in sessions:
                try:
                    session.close()
                except Exception as exc:
                    errors.append(exc)
            if errors:
                raise ExceptionGroup("SwbtControllerOutputPortFactory close failed", errors)

    def _session_for(self, config: SwbtControllerConfig) -> SwbtControllerSessionProtocol:
        key = session_key(config)
        session = self._sessions.get(key)
        if session is not None and key in self._dummy_session_keys:
            self._discard_session(key, session)
            session = None
        if session is None:
            session = self._session_factory(config)
            self._sessions[key] = session
            self._dummy_session_keys.discard(key)
        return session

    def _activate_port(
        self,
        key: SwbtSessionKey,
        session: SwbtControllerSessionProtocol,
        config: SwbtControllerConfig,
    ) -> SwbtControllerOutputPort:
        """同じ session key の有効 port を 1 つに入れ替える。"""
        self._close_active_port(key)
        port = SwbtControllerOutputPort(
            session=session,
            model=config.model,
            on_close=lambda closed_port: self._discard_active_port(key, closed_port),
        )
        self._active_ports[key] = port
        return port

    def _close_active_port(self, key: SwbtSessionKey) -> None:
        port = self._active_ports.pop(key, None)
        if port is None:
            return
        port.close()

    def _discard_active_port(
        self,
        key: SwbtSessionKey,
        port: SwbtControllerOutputPort,
    ) -> None:
        with self._lock:
            if self._active_ports.get(key) is port:
                self._active_ports.pop(key, None)

    def _discard_session(
        self,
        key: SwbtSessionKey,
        session: SwbtControllerSessionProtocol,
    ) -> None:
        """失敗した session を cache から外し、adapter を解放する。"""
        active_port = self._active_ports.pop(key, None)
        if active_port is not None:
            with suppress(Exception):
                active_port.close()
        if self._sessions.get(key) is session:
            self._sessions.pop(key, None)
        self._dummy_session_keys.discard(key)
        with suppress(Exception):
            session.close()


def session_key(config: SwbtControllerConfig) -> SwbtSessionKey:
    """Config から session cache key を作る。"""
    return SwbtSessionKey(
        controller_type=config.model.controller_type,
        adapter=config.adapter,
        key_store_path=config.key_store_path,
        report_period_us=config.report_period_us,
    )
