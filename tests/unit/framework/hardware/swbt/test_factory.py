import io
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread

import pytest
from swbt import GamepadStatus

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, resolve_controller_model
from nyxpy.framework.core.hardware.swbt.factory import (
    SwbtControllerOutputPortFactory,
    session_key,
)
from nyxpy.framework.core.hardware.swbt.session import SwbtControllerSession
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class RecordingSession:
    def __init__(
        self,
        *,
        fail_pair: bool = False,
        fail_reconnect: bool = False,
        close_failures: int = 0,
        neutral_failures: int = 0,
    ) -> None:
        self.fail_pair = fail_pair
        self.fail_reconnect = fail_reconnect
        self.close_failures = close_failures
        self.neutral_failures = neutral_failures
        self.open_calls = 0
        self.pair_calls = 0
        self.reconnect_calls = 0
        self.neutral_calls = 0
        self.close_calls = 0
        self.connected = False

    def open(self) -> None:
        self.open_calls += 1

    def pair(self, *, timeout_sec: float) -> None:
        self.pair_calls += 1
        if self.fail_pair:
            raise ConfigurationError("pair failed", code="NYX_SWBT_CONNECTION_FAILED")
        self.connected = True

    def reconnect(self, *, timeout_sec: float) -> None:
        self.reconnect_calls += 1
        if self.fail_reconnect:
            raise ConfigurationError("reconnect failed", code="NYX_SWBT_CONNECTION_FAILED")
        self.connected = True

    def apply(self, state) -> None:
        pass

    def neutral(self) -> None:
        self.neutral_calls += 1
        if self.neutral_failures:
            self.neutral_failures -= 1
            raise ConfigurationError("neutral failed", code="NYX_SWBT_CONNECTION_FAILED")

    def status(self):
        return {"open_calls": self.open_calls}

    def close(self) -> None:
        self.close_calls += 1
        if self.close_failures:
            self.close_failures -= 1
            raise ConfigurationError("close failed", code="NYX_SWBT_CONNECTION_FAILED")
        self.connected = False


class RemoteAwareRecordingSession(RecordingSession):
    @property
    def connected(self) -> bool:
        return self.connection_state == "connected"

    @connected.setter
    def connected(self, value: bool) -> None:
        self.connection_state = "connected" if value else "closed"

    def status(self) -> GamepadStatus:
        return GamepadStatus(
            connection_state=self.connection_state,
            report_counters={},
            last_subcommand_id=None,
            raw_rumble=None,
            last_error=None,
        )


def config(adapter: str = "usb:0") -> SwbtControllerConfig:
    model = resolve_controller_model("pro-controller")
    return SwbtControllerConfig(
        model=model,
        adapter=adapter,
        key_store_path=Path(".nyxpy/swbt/pro-controller-bond.json"),
    )


def test_factory_create_reconnects_without_pairing() -> None:
    sessions: list[RecordingSession] = []

    def make_session(_config):
        session = RecordingSession()
        sessions.append(session)
        return session

    factory = SwbtControllerOutputPortFactory(session_factory=make_session)

    port = factory.create(config=config(), allow_dummy=False, timeout_sec=3.0)

    assert port.supports_imu is True
    assert sessions[0].open_calls == 1
    assert sessions[0].reconnect_calls == 1
    assert sessions[0].pair_calls == 0
    assert sessions[0].neutral_calls == 1


def test_factory_reuses_session_for_same_key_and_ports_are_new() -> None:
    session = RecordingSession()
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)

    first = factory.create(config=config(), allow_dummy=False, timeout_sec=1.0)
    second = factory.create(config=config(), allow_dummy=False, timeout_sec=1.0)

    assert first is not second
    assert session.reconnect_calls == 1
    assert session.neutral_calls == 3
    assert session_key(config()) == session_key(config())
    with pytest.raises(Exception) as exc_info:
        first.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_reconnects_cached_session_after_remote_disconnect() -> None:
    session = RemoteAwareRecordingSession()
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)

    first = factory.create(config=config(), allow_dummy=False, timeout_sec=1.0)
    session.connection_state = "closed"
    factory.create(config=config(), allow_dummy=False, timeout_sec=1.0)

    assert session.reconnect_calls == 2
    with pytest.raises(Exception) as exc_info:
        first.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_closes_active_port_before_explicit_reconnect() -> None:
    session = RecordingSession()
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()

    port = factory.create(config=cfg, allow_dummy=False, timeout_sec=1.0)
    factory.reconnect(cfg, timeout_sec=2.0)

    assert session.reconnect_calls == 2
    assert session.neutral_calls == 2
    with pytest.raises(Exception) as exc_info:
        port.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_allows_dummy_fallback_only_for_create() -> None:
    real = RecordingSession(fail_reconnect=True)
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: real)

    port = factory.create(config=config(), allow_dummy=True, timeout_sec=1.0)

    assert port.supports_imu is True
    assert real.reconnect_calls == 1
    assert real.close_calls == 1

    explicit = RecordingSession(fail_reconnect=True)
    explicit_factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: explicit)

    with pytest.raises(ConfigurationError):
        explicit_factory.reconnect(config(), timeout_sec=1.0)

    assert explicit.close_calls == 1


@pytest.mark.parametrize("operation", ("create", "pair", "reconnect"))
def test_factory_preserves_primary_and_cleanup_errors(operation: str) -> None:
    session = RecordingSession(
        fail_pair=operation == "pair",
        fail_reconnect=operation != "pair",
        close_failures=1,
    )
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()

    with pytest.raises(ExceptionGroup) as exc_info:
        if operation == "create":
            factory.create(config=cfg, allow_dummy=False)
        else:
            getattr(factory, operation)(cfg)

    primary_message = "pair failed" if operation == "pair" else "reconnect failed"
    assert [str(error) for error in exc_info.value.exceptions] == [
        primary_message,
        "close failed",
    ]
    assert [getattr(error, "code", None) for error in exc_info.value.exceptions] == [
        "NYX_SWBT_CONNECTION_FAILED",
        "NYX_SWBT_CONNECTION_FAILED",
    ]
    assert factory.status(cfg) is not None
    factory.close()
    assert factory.status(cfg) is None


def test_factory_pair_discards_cached_dummy_session() -> None:
    failed_real = RecordingSession(fail_reconnect=True)
    next_real = RecordingSession()
    dummy = RecordingSession()
    sessions = iter((failed_real, next_real))
    factory = SwbtControllerOutputPortFactory(
        session_factory=lambda _config: next(sessions),
        dummy_session_factory=lambda: dummy,
    )
    cfg = config()

    factory.create(config=cfg, allow_dummy=True, timeout_sec=1.0)
    factory.pair(cfg, timeout_sec=2.0)

    assert failed_real.close_calls == 1
    assert dummy.close_calls == 1
    assert dummy.pair_calls == 0
    assert next_real.open_calls == 1
    assert next_real.pair_calls == 1


def test_factory_create_without_dummy_discards_cached_dummy_session() -> None:
    failed_real = RecordingSession(fail_reconnect=True)
    next_real = RecordingSession()
    dummy = RecordingSession()
    sessions = iter((failed_real, next_real))
    factory = SwbtControllerOutputPortFactory(
        session_factory=lambda _config: next(sessions),
        dummy_session_factory=lambda: dummy,
    )
    cfg = config()

    factory.create(config=cfg, allow_dummy=True, timeout_sec=1.0)
    port = factory.create(config=cfg, allow_dummy=False, timeout_sec=2.0)

    assert port.supports_imu is True
    assert dummy.close_calls == 1
    assert next_real.open_calls == 1
    assert next_real.reconnect_calls == 1


def test_factory_discards_failed_create_session_without_dummy() -> None:
    session = RecordingSession(fail_reconnect=True)
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()

    with pytest.raises(ConfigurationError):
        factory.create(config=cfg, allow_dummy=False, timeout_sec=1.0)

    assert session.open_calls == 1
    assert session.reconnect_calls == 1
    assert session.close_calls == 1
    assert factory.status(cfg) is None


def test_factory_discards_failed_pair_session() -> None:
    session = RecordingSession(fail_pair=True)
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()

    with pytest.raises(ConfigurationError):
        factory.pair(cfg, timeout_sec=1.0)

    assert session.open_calls == 1
    assert session.pair_calls == 1
    assert session.close_calls == 1
    assert factory.status(cfg) is None


def test_factory_pair_reconnect_disconnect_and_status_are_explicit_operations() -> None:
    session = RecordingSession()
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()

    factory.pair(cfg, timeout_sec=2.0)
    factory.reconnect(cfg, timeout_sec=3.0)
    assert factory.status(cfg) == {"open_calls": 2}

    factory.disconnect(cfg)
    factory.disconnect(cfg)

    assert session.pair_calls == 1
    assert session.reconnect_calls == 1
    assert session.neutral_calls == 1
    assert session.close_calls == 1
    assert factory.status(cfg) is None


def test_factory_disconnect_closes_active_port_and_session() -> None:
    session = RecordingSession()
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()

    port = factory.create(config=cfg, allow_dummy=False, timeout_sec=1.0)
    factory.disconnect(cfg)

    assert session.neutral_calls == 2
    assert session.close_calls == 1
    with pytest.raises(Exception) as exc_info:
        port.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"
    assert factory.status(cfg) is None


def test_factory_disconnect_retains_failed_session_for_retry() -> None:
    session = RecordingSession(close_failures=1)
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()
    port = factory.create(config=cfg, allow_dummy=False)

    with pytest.raises(ExceptionGroup):
        factory.disconnect(cfg)
    factory.disconnect(cfg)

    assert session.close_calls == 2
    assert factory.status(cfg) is None
    with pytest.raises(Exception) as exc_info:
        port.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_close_closes_cached_sessions() -> None:
    first = RecordingSession()
    second = RecordingSession()
    sessions = iter((first, second))
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: next(sessions))

    factory.pair(config("usb:0"))
    factory.pair(config("usb:1"))
    factory.close()

    assert first.close_calls == 1
    assert second.close_calls == 1


def test_factory_close_retains_failed_session_for_retry() -> None:
    session = RecordingSession(close_failures=1)
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()
    factory.pair(cfg)

    with pytest.raises(ExceptionGroup):
        factory.close()
    factory.close()

    assert session.close_calls == 2
    assert factory.status(cfg) is None


def test_factory_close_cleans_active_port_when_session_close_recovers_neutral_failure() -> None:
    session = RecordingSession()
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()
    port = factory.create(config=cfg, allow_dummy=False)
    session.neutral_failures = 1

    factory.close()
    assert session.close_calls == 1
    assert factory.status(cfg) is None
    with pytest.raises(Exception) as exc_info:
        port.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_disconnect_cleans_port_when_session_close_recovers_neutral_failure() -> None:
    session = RecordingSession()
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()
    port = factory.create(config=cfg, allow_dummy=False)
    session.neutral_failures = 1

    factory.disconnect(cfg)
    assert session.close_calls == 1
    assert factory.status(cfg) is None
    with pytest.raises(Exception) as exc_info:
        port.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_create_recovers_active_port_then_preserves_reconnect_failure() -> None:
    session = RecordingSession()
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()
    port = factory.create(config=cfg, allow_dummy=False)
    session.connected = False
    session.fail_reconnect = True
    session.neutral_failures = 1

    with pytest.raises(ConfigurationError, match="reconnect failed"):
        factory.create(config=cfg, allow_dummy=False)

    assert session.close_calls == 2
    assert factory.status(cfg) is None
    with pytest.raises(Exception) as exc_info:
        port.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_releases_previous_session_when_same_adapter_key_changes() -> None:
    first = RecordingSession()
    second = RecordingSession()
    sessions = iter((first, second))
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: next(sessions))
    first_config = config()
    second_config = replace(
        first_config,
        key_store_path=Path(".nyxpy/swbt/other-pro-controller-bond.json"),
    )

    first_port = factory.create(config=first_config, allow_dummy=False)
    factory.create(config=second_config, allow_dummy=False)

    assert first.close_calls == 1
    assert factory.status(first_config) is None
    assert factory.status(second_config) == {"open_calls": 1}
    with pytest.raises(Exception) as exc_info:
        first_port.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_reconnect_recovers_active_port_when_session_close_succeeds() -> None:
    session = RecordingSession()
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    cfg = config()
    port = factory.create(config=cfg, allow_dummy=False, timeout_sec=1.0)
    session.neutral_failures = 1

    factory.reconnect(cfg, timeout_sec=2.0)

    assert session.close_calls == 1
    assert session.reconnect_calls == 2
    assert factory.status(cfg) is not None
    with pytest.raises(Exception) as exc_info:
        port.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_reconnect_retries_after_port_and_session_cleanup_failures() -> None:
    previous = RecordingSession()
    replacement = RecordingSession()
    sessions = iter((previous, replacement))
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: next(sessions))
    cfg = config()
    port = factory.create(config=cfg, allow_dummy=False)
    previous.neutral_failures = 2
    previous.close_failures = 1

    with pytest.raises(ExceptionGroup) as exc_info:
        factory.reconnect(cfg)

    assert [str(error) for error in exc_info.value.exceptions] == [
        "neutral failed",
        "close failed",
    ]
    assert factory.status(cfg) is not None

    factory.reconnect(cfg)

    assert previous.close_calls == 2
    assert replacement.reconnect_calls == 1
    assert factory.status(cfg) == {"open_calls": 1}
    with pytest.raises(Exception) as closed_info:
        port.press((Button.A,))
    assert getattr(closed_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_reconnect_recovers_real_session_after_event_loop_stop_timeout() -> None:
    class SyncController:
        def __init__(self) -> None:
            self.connection_state = "closed"

        def open(self) -> None:
            pass

        def reconnect(self, *, timeout: float) -> None:
            self.connection_state = "connected"

        def status(self) -> GamepadStatus:
            return GamepadStatus(
                connection_state=self.connection_state,
                report_counters={},
                last_subcommand_id=None,
                raw_rumble=None,
                last_error=None,
            )

        def neutral(self) -> None:
            pass

        def close(self, *, neutral: bool = True) -> None:
            self.connection_state = "closed"

    class NonStoppingLoop:
        def is_running(self) -> bool:
            return True

        def call_soon_threadsafe(self, callback) -> None:
            pass

    cfg = config()
    controller = SyncController()
    previous = SwbtControllerSession(
        cfg,
        controller_factory=lambda _config, _writer: controller,
    )
    replacement = RecordingSession()
    sessions = iter((previous, replacement))
    factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: next(sessions))
    port = factory.create(config=cfg, allow_dummy=False)

    release = Event()
    thread = Thread(target=release.wait, daemon=True)
    thread.start()
    previous._loop = NonStoppingLoop()
    previous._loop_thread = thread
    previous._loop_stop_timeout_sec = 0.01
    with pytest.raises(ConfigurationError):
        previous._stop_loop_locked()

    with pytest.raises(ExceptionGroup) as exc_info:
        factory.reconnect(cfg)
    assert [getattr(error, "code", None) for error in exc_info.value.exceptions] == [
        "NYX_SWBT_EVENT_LOOP_NOT_RUNNING",
        "NYX_SWBT_EVENT_LOOP_DID_NOT_STOP",
    ]
    assert factory._sessions[session_key(cfg)] is previous
    assert factory._active_ports[session_key(cfg)] is port

    release.set()
    thread.join()
    factory.reconnect(cfg)

    assert replacement.reconnect_calls == 1
    assert factory.status(cfg) == {"open_calls": 1}
    with pytest.raises(Exception) as closed_info:
        port.press((Button.A,))
    assert getattr(closed_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_factory_passes_diagnostics_writer_to_default_session() -> None:
    writer = io.StringIO()
    factory = SwbtControllerOutputPortFactory(diagnostics_writer=writer)

    session = factory._session_factory(config())

    assert getattr(session, "_diagnostics_writer") is writer


def test_factory_does_not_create_manual_session_type() -> None:
    root = Path("src/nyxpy/framework/core/hardware/swbt")

    assert not (root / "manual.py").exists()
    assert not any(path.name.startswith("swbt_") for path in root.glob("*.py"))

    import nyxpy.framework.core.hardware.swbt as swbt_backend

    assert not hasattr(swbt_backend, "SwbtManualInputSession")
