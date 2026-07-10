"""swbt ControllerOutputPort factory。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, SwbtControllerType
from nyxpy.framework.core.hardware.swbt.controller import SwbtControllerOutputPort
from nyxpy.framework.core.hardware.swbt.diagnostics import DiagnosticsWriter
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
        diagnostics_writer: DiagnosticsWriter | None = None,
    ) -> None:
        """Session factory と cache を初期化する。"""
        self._session_factory = session_factory or (
            lambda config: SwbtControllerSession(
                config,
                diagnostics_writer=diagnostics_writer,
            )
        )
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
            self._release_conflicting_adapter_sessions(key)
            self._prepare_active_port_replacement(key)
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
                return self._activate_port(key, session, config)
            except (ConfigurationError, DeviceError) as primary_error:
                self._discard_failed_session(
                    key,
                    session,
                    primary_error=primary_error,
                    operation="create",
                )
                if not allow_dummy:
                    raise
                session = self._dummy_session_factory()
                session.open()
                session.reconnect(timeout_sec=timeout_sec or config.connect_timeout_sec)
                self._sessions[key] = session
                self._dummy_session_keys.add(key)
            return self._activate_port(key, session, config)

    def pair(self, config: SwbtControllerConfig, *, timeout_sec: float | None = None) -> None:
        """明示 pairing を実行する。dummy fallback はしない。"""
        with self._lock:
            key = session_key(config)
            self._release_conflicting_adapter_sessions(key)
            self._prepare_active_port_replacement(key)
            session = self._session_for(config)
            try:
                session.open()
                session.pair(timeout_sec=timeout_sec or config.connect_timeout_sec)
            except (ConfigurationError, DeviceError) as primary_error:
                self._discard_failed_session(
                    key,
                    session,
                    primary_error=primary_error,
                    operation="pair",
                )
                raise

    def reconnect(self, config: SwbtControllerConfig, *, timeout_sec: float | None = None) -> None:
        """明示 reconnect を実行する。dummy fallback はしない。"""
        with self._lock:
            key = session_key(config)
            self._release_conflicting_adapter_sessions(key)
            self._prepare_active_port_replacement(key)
            session = self._session_for(config)
            try:
                session.open()
                session.reconnect(timeout_sec=timeout_sec or config.connect_timeout_sec)
            except (ConfigurationError, DeviceError) as primary_error:
                self._discard_failed_session(
                    key,
                    session,
                    primary_error=primary_error,
                    operation="reconnect",
                )
                raise

    def disconnect(self, config: SwbtControllerConfig) -> None:
        """factory-managed cached session だけを閉じる。"""
        with self._lock:
            key = session_key(config)
            session = self._sessions.get(key)
            active_port = self._active_ports.get(key)
            if session is None and active_port is None:
                return
            if session is None:
                try:
                    self._close_active_port(key)
                except Exception as exc:
                    raise ExceptionGroup(
                        "swbt disconnect failed",
                        _leaf_exceptions(exc),
                    ) from exc
                return
            self._close_cached_session(
                key,
                session,
                message="swbt disconnect failed",
                neutral_without_port=True,
            )

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
            for key, session in tuple(self._sessions.items()):
                try:
                    self._close_cached_session(
                        key,
                        session,
                        message="swbt cached session cleanup failed",
                    )
                except Exception as exc:
                    errors.extend(_leaf_exceptions(exc))
            if errors:
                raise ExceptionGroup("SwbtControllerOutputPortFactory close failed", errors)

    def _prepare_active_port_replacement(self, key: SwbtSessionKey) -> None:
        """既存 port を閉じ、失敗時は session の終端 close で回復する。"""
        if self._active_ports.get(key) is None:
            return
        try:
            self._close_active_port(key)
        except Exception as port_error:
            session = self._sessions.get(key)
            if session is None:
                raise ExceptionGroup(
                    "swbt active port cleanup failed",
                    _leaf_exceptions(port_error),
                ) from port_error
            self._close_cached_session(
                key,
                session,
                message="swbt active port cleanup failed",
                prior_errors=tuple(_leaf_exceptions(port_error)),
                close_active_port=False,
            )

    def _discard_failed_session(
        self,
        key: SwbtSessionKey,
        session: SwbtControllerSessionProtocol,
        *,
        primary_error: ConfigurationError | DeviceError,
        operation: str,
    ) -> None:
        """本体失敗後の cleanup 失敗を元例外と一緒に保持する。"""
        try:
            self._discard_session(key, session)
        except Exception as cleanup_error:
            raise ExceptionGroup(
                f"swbt {operation} and cleanup failed",
                [primary_error, *_leaf_exceptions(cleanup_error)],
            ) from primary_error

    def _close_cached_session(
        self,
        key: SwbtSessionKey,
        session: SwbtControllerSessionProtocol,
        *,
        message: str,
        prior_errors: tuple[Exception, ...] = (),
        close_active_port: bool = True,
        neutral_without_port: bool = False,
    ) -> None:
        """Port の失敗後も session close を試し、最終所有権を確定する。"""
        errors = list(prior_errors)
        owned = self._sessions.get(key) is session
        active_port = self._active_ports.get(key) if owned else None
        if active_port is not None and close_active_port:
            try:
                active_port.close()
            except Exception as exc:
                errors.extend(_leaf_exceptions(exc))
        elif active_port is None and neutral_without_port:
            try:
                if session.connected:
                    session.neutral()
            except Exception as exc:
                errors.extend(_leaf_exceptions(exc))

        try:
            session.close()
        except Exception as close_error:
            errors.extend(_leaf_exceptions(close_error))
            raise ExceptionGroup(message, errors) from close_error

        # session.close(neutral=True) が成功したため、先行 neutral 失敗は
        # 終端状態へ回復済み。外部参照の port も追加送信なしで無効化する。
        if active_port is not None:
            active_port._invalidate_after_session_close()
        if owned:
            self._active_ports.pop(key, None)
            self._sessions.pop(key, None)
            self._dummy_session_keys.discard(key)

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
        port = self._active_ports.get(key)
        if port is None:
            return
        port.close()
        self._active_ports.pop(key, None)

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
        self._close_cached_session(
            key,
            session,
            message="swbt session cleanup failed",
        )

    def _release_conflicting_adapter_sessions(self, key: SwbtSessionKey) -> None:
        """同じ物理 adapter を所有する別設定の session を先に閉じる。"""
        if key.adapter is None:
            return
        conflicts = tuple(
            (cached_key, session)
            for cached_key, session in self._sessions.items()
            if cached_key != key and cached_key.adapter == key.adapter
        )
        for cached_key, session in conflicts:
            self._discard_session(cached_key, session)


def session_key(config: SwbtControllerConfig) -> SwbtSessionKey:
    """Config から session cache key を作る。"""
    return SwbtSessionKey(
        controller_type=config.model.controller_type,
        adapter=config.adapter,
        key_store_path=config.key_store_path,
        report_period_us=config.report_period_us,
    )


def _leaf_exceptions(error: Exception) -> list[Exception]:
    """Nested ExceptionGroup を発生順の leaf exception へ平坦化する。"""
    if not isinstance(error, ExceptionGroup):
        return [error]
    leaves: list[Exception] = []
    for nested in error.exceptions:
        leaves.extend(_leaf_exceptions(nested))
    return leaves
