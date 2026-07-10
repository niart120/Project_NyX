from pathlib import Path

import pytest

from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, resolve_controller_model
from nyxpy.framework.core.hardware.swbt.session import (
    DummySwbtControllerSession,
    SwbtControllerSession,
)


class FakeSwbtController:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.closed = False

    def open(self) -> None:
        self.calls.append(("open", None))

    def pair(self, *, timeout: float) -> str:
        self.calls.append(("pair", timeout))
        return "paired"

    def reconnect(self, *, timeout: float) -> str:
        self.calls.append(("reconnect", timeout))
        return "reconnected"

    def apply(self, state) -> None:
        self.calls.append(("apply", state))

    def neutral(self) -> None:
        self.calls.append(("neutral", None))

    def status(self) -> str:
        self.calls.append(("status", None))
        return "connected"

    def close(self, *, neutral: bool = True) -> None:
        self.calls.append(("close", neutral))
        self.closed = True


class AwaitableFakeSwbtController(FakeSwbtController):
    async def open(self) -> None:
        self.calls.append(("open", None))

    async def pair(self, *, timeout: float) -> str:
        self.calls.append(("pair", timeout))
        return "paired"

    async def reconnect(self, *, timeout: float) -> str:
        self.calls.append(("reconnect", timeout))
        return "reconnected"

    async def apply(self, state) -> None:
        self.calls.append(("apply", state))

    async def neutral(self) -> None:
        self.calls.append(("neutral", None))

    async def close(self, *, neutral: bool = True) -> None:
        self.calls.append(("close", neutral))
        self.closed = True


def config() -> SwbtControllerConfig:
    model = resolve_controller_model("pro-controller")
    return SwbtControllerConfig(
        model=model,
        adapter="usb:0",
        key_store_path=Path(".nyxpy/swbt/pro-controller-bond.json"),
    )


def test_session_open_does_not_pair_or_reconnect() -> None:
    fake = FakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)

    session.open()
    session.open()

    assert fake.calls == [("open", None)]
    assert not session.connected


def test_session_pair_reconnect_apply_status_and_close() -> None:
    fake = FakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)

    assert session.pair(timeout_sec=10.0) == "paired"
    session.apply("state")
    assert session.status() == "connected"
    assert session.reconnect(timeout_sec=20.0) == "reconnected"
    session.neutral()
    session.close()
    session.close()

    assert fake.calls == [
        ("open", None),
        ("pair", 10.0),
        ("apply", "state"),
        ("status", None),
        ("reconnect", 20.0),
        ("neutral", None),
        ("close", True),
    ]
    assert fake.closed is True


def test_session_waits_for_awaitable_controller_methods() -> None:
    fake = AwaitableFakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)

    assert session.pair(timeout_sec=10.0) == "paired"
    session.apply("state")
    session.neutral()
    session.close()

    assert fake.calls == [
        ("open", None),
        ("pair", 10.0),
        ("apply", "state"),
        ("neutral", None),
        ("close", True),
    ]
    assert fake.closed is True


def test_session_requires_adapter_before_open() -> None:
    model = resolve_controller_model("pro-controller")
    session = SwbtControllerSession(
        SwbtControllerConfig(
            model=model,
            adapter=None,
            key_store_path=Path(".nyxpy/swbt/pro-controller-bond.json"),
        )
    )

    with pytest.raises(Exception) as exc_info:
        session.open()

    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_ADAPTER_NOT_SELECTED"


def test_dummy_session_records_state_without_bluetooth_transport() -> None:
    session = DummySwbtControllerSession()

    session.open()
    result = session.reconnect(timeout_sec=1.0)
    session.apply("state")
    session.neutral()
    session.close()

    assert result.connected is True
    assert session.opened is True
    assert session.reconnect_calls == 1
    assert session.states == ["state"]
    assert session.neutral_calls == 1
    assert session.closed is True
