from pathlib import Path

import pytest

from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, resolve_controller_model
from nyxpy.framework.core.hardware.swbt.factory import (
    SwbtControllerOutputPortFactory,
    session_key,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class RecordingSession:
    def __init__(self, *, fail_pair: bool = False, fail_reconnect: bool = False) -> None:
        self.fail_pair = fail_pair
        self.fail_reconnect = fail_reconnect
        self.open_calls = 0
        self.pair_calls = 0
        self.reconnect_calls = 0
        self.neutral_calls = 0
        self.close_calls = 0
        self.connected = False

    def open(self) -> None:
        self.open_calls += 1

    def pair(self, *, timeout_sec: float):
        self.pair_calls += 1
        if self.fail_pair:
            raise ConfigurationError("pair failed", code="NYX_SWBT_CONNECTION_FAILED")
        self.connected = True
        return ("pair", timeout_sec)

    def reconnect(self, *, timeout_sec: float):
        self.reconnect_calls += 1
        if self.fail_reconnect:
            raise ConfigurationError("reconnect failed", code="NYX_SWBT_CONNECTION_FAILED")
        self.connected = True
        return ("reconnect", timeout_sec)

    def apply(self, state) -> None:
        pass

    def neutral(self) -> None:
        self.neutral_calls += 1

    def status(self):
        return {"open_calls": self.open_calls}

    def close(self) -> None:
        self.close_calls += 1
        self.connected = False


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
    assert session_key(config()) == session_key(config())


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

    assert factory.pair(cfg, timeout_sec=2.0) == ("pair", 2.0)
    assert factory.reconnect(cfg, timeout_sec=3.0) == ("reconnect", 3.0)
    assert factory.status(cfg) == {"open_calls": 2}

    factory.disconnect(cfg)
    factory.disconnect(cfg)

    assert session.pair_calls == 1
    assert session.reconnect_calls == 1
    assert session.neutral_calls == 1
    assert session.close_calls == 1
    assert factory.status(cfg) is None


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


def test_factory_does_not_create_manual_session_type() -> None:
    root = Path("src/nyxpy/framework/core/hardware/swbt")

    assert not (root / "manual.py").exists()
    assert not any(path.name.startswith("swbt_") for path in root.glob("*.py"))

    import nyxpy.framework.core.hardware.swbt as swbt_backend

    assert not hasattr(swbt_backend, "SwbtManualInputSession")
