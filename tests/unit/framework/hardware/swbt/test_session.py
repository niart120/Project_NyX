import asyncio
import json
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread

import pytest
from swbt import GamepadStatus

from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, resolve_controller_model
from nyxpy.framework.core.hardware.swbt.errors import swbt_configuration_error
from nyxpy.framework.core.hardware.swbt.session import (
    DummySwbtControllerSession,
    SwbtControllerSession,
    is_swbt_status_connected,
)


def gamepad_status(connection_state: str) -> GamepadStatus:
    return GamepadStatus(
        connection_state=connection_state,
        report_counters={},
        last_subcommand_id=None,
        raw_rumble=None,
        last_error=None,
    )


class FakeSwbtController:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.closed = False
        self.connection_state = "closed"
        self.close_failures = 0

    def open(self) -> None:
        self.calls.append(("open", None))

    def pair(self, *, timeout: float) -> None:
        self.calls.append(("pair", timeout))
        self.connection_state = "connected"

    def reconnect(self, *, timeout: float) -> None:
        self.calls.append(("reconnect", timeout))
        self.connection_state = "connected"

    def apply(self, state) -> None:
        self.calls.append(("apply", state))

    def neutral(self) -> None:
        self.calls.append(("neutral", None))

    def status(self) -> GamepadStatus:
        self.calls.append(("status", None))
        return gamepad_status(self.connection_state)

    def close(self, *, neutral: bool = True) -> None:
        self.calls.append(("close", neutral))
        if self.close_failures:
            self.close_failures -= 1
            raise RuntimeError("close failed")
        self.closed = True
        self.connection_state = "closed"


class AwaitableFakeSwbtController(FakeSwbtController):
    async def open(self) -> None:
        self.calls.append(("open", None))

    async def pair(self, *, timeout: float) -> None:
        self.calls.append(("pair", timeout))
        self.connection_state = "connected"

    async def reconnect(self, *, timeout: float) -> None:
        self.calls.append(("reconnect", timeout))
        self.connection_state = "connected"

    async def apply(self, state) -> None:
        self.calls.append(("apply", state))

    async def neutral(self) -> None:
        self.calls.append(("neutral", None))

    async def close(self, *, neutral: bool = True) -> None:
        self.calls.append(("close", neutral))
        self.closed = True
        self.connection_state = "closed"


class SlowAwaitableFakeSwbtController(AwaitableFakeSwbtController):
    async def pair(self, *, timeout: float) -> None:
        self.calls.append(("pair", timeout))
        await asyncio.sleep(0.02)
        self.connection_state = "connected"


class HangingPairFakeSwbtController(AwaitableFakeSwbtController):
    def __init__(self) -> None:
        super().__init__()
        self.pair_started = Event()

    async def pair(self, *, timeout: float) -> None:
        self.calls.append(("pair", timeout))
        self.pair_started.set()
        await asyncio.sleep(3600)


class HangingReconnectFakeSwbtController(AwaitableFakeSwbtController):
    def __init__(self) -> None:
        super().__init__()
        self.reconnect_started = Event()

    async def reconnect(self, *, timeout: float) -> None:
        self.calls.append(("reconnect", timeout))
        self.reconnect_started.set()
        await asyncio.sleep(3600)


class CancellationAwareFakeSwbtController(AwaitableFakeSwbtController):
    async def apply(self, state) -> None:
        self.calls.append(("apply-start", state))
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.calls.append(("cancel-start", None))
            await asyncio.sleep(0.02)
            self.calls.append(("cancel-finished", None))
            raise


class ReportingReadyFakeSwbtController(FakeSwbtController):
    def __init__(self) -> None:
        super().__init__()
        self.status_calls = 0

    def status(self) -> GamepadStatus:
        self.calls.append(("status", None))
        self.status_calls += 1
        report_count = 15 if self.status_calls == 1 else 16
        return GamepadStatus(
            connection_state=self.connection_state,
            report_counters={0x30: report_count},
            last_subcommand_id=None,
            raw_rumble=None,
            last_error=None,
        )


def config() -> SwbtControllerConfig:
    model = resolve_controller_model("pro-controller")
    return SwbtControllerConfig(
        model=model,
        adapter="usb:0",
        profile_path=Path(".nyxpy/swbt/pro-controller-profile.json"),
    )


def _capture_error(errors: list[BaseException], operation) -> None:
    try:
        operation()
    except BaseException as exc:
        errors.append(exc)


@pytest.fixture(autouse=True)
def existing_profile(monkeypatch) -> None:
    """既存テストは作成済みprofileからのPair経路を検証する。"""
    monkeypatch.setattr(SwbtControllerSession, "_profile_exists", lambda _self: True)


def test_session_open_does_not_pair_or_reconnect() -> None:
    fake = FakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)

    session.open()
    session.open()

    assert fake.calls == [("open", None)]
    assert not session.connected


def test_session_pair_creates_profile_and_owns_returned_controller(monkeypatch) -> None:
    fake = FakeSwbtController()
    fake.connection_state = "connected"
    calls: list[tuple[SwbtControllerConfig, float]] = []

    async def create_profile(
        profile_config: SwbtControllerConfig,
        _writer,
        timeout_sec: float,
    ) -> FakeSwbtController:
        calls.append((profile_config, timeout_sec))
        return fake

    session = SwbtControllerSession(
        config(),
        controller_factory=lambda _config, _writer: pytest.fail(
            "normal controller construction must not run"
        ),
        profile_creator=create_profile,
    )
    monkeypatch.setattr(session, "_profile_exists", lambda: False)

    session.pair(timeout_sec=12.0)

    assert calls == [(session.config, 12.0)]
    assert fake.calls == [("status", None)]
    assert session.connected
    session.close()
    assert fake.closed


def test_session_pair_cancels_pending_awaitable_without_waiting_for_timeout() -> None:
    fake = HangingPairFakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)
    cancellation_event = Event()
    errors: list[BaseException] = []

    def pair() -> None:
        try:
            session.pair(timeout_sec=30.0, cancellation_event=cancellation_event)
        except BaseException as exc:
            errors.append(exc)

    thread = Thread(target=pair)
    thread.start()
    assert fake.pair_started.wait(1.0)

    cancellation_event.set()
    thread.join(1.0)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert getattr(errors[0], "code", None) == "NYX_SWBT_PAIR_CANCELLED"


def test_session_retries_pair_with_profile_left_after_create_cancellation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "pro-controller-profile.json"
    profile_started = Event()

    async def create_profile(
        _config: SwbtControllerConfig,
        _writer,
        _timeout_sec: float,
    ) -> object:
        profile_path.write_text('{"schema_version": 2}', encoding="utf-8")
        profile_started.set()
        await asyncio.sleep(3600)
        raise AssertionError("profile creation should be cancelled")

    first = SwbtControllerSession(
        replace(config(), profile_path=profile_path),
        profile_creator=create_profile,
    )
    monkeypatch.setattr(first, "_profile_exists", profile_path.is_file)
    cancellation_event = Event()
    errors: list[BaseException] = []
    thread = Thread(
        target=lambda: _capture_error(
            errors,
            lambda: first.pair(
                timeout_sec=30.0,
                cancellation_event=cancellation_event,
            ),
        )
    )
    thread.start()
    assert profile_started.wait(1.0)
    cancellation_event.set()
    thread.join(1.0)

    assert getattr(errors[0], "code", None) == "NYX_SWBT_PAIR_CANCELLED"
    assert profile_path.is_file()

    fake = FakeSwbtController()
    second = SwbtControllerSession(
        replace(config(), profile_path=profile_path),
        controller_factory=lambda _config, _writer: fake,
    )
    monkeypatch.setattr(second, "_profile_exists", profile_path.is_file)
    second.pair(timeout_sec=5.0)

    assert fake.calls[:3] == [("open", None), ("pair", 5.0), ("status", None)]


def test_session_reconnect_cancels_after_awaitable_started() -> None:
    fake = HangingReconnectFakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)
    cancellation_event = Event()
    errors: list[BaseException] = []

    def reconnect() -> None:
        try:
            session.reconnect(timeout_sec=30.0, cancellation_event=cancellation_event)
        except BaseException as exc:
            errors.append(exc)

    thread = Thread(target=reconnect)
    thread.start()
    assert fake.reconnect_started.wait(1.0)

    cancellation_event.set()
    thread.join(1.0)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert getattr(errors[0], "code", None) == "NYX_SWBT_RECONNECT_CANCELLED"


def test_session_pair_reconnect_apply_status_and_close() -> None:
    fake = FakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)

    assert session.pair(timeout_sec=10.0) is None
    assert session.connected
    session.apply("state")
    assert session.status() == gamepad_status("connected")
    assert session.reconnect(timeout_sec=20.0) is None
    session.neutral()
    session.close()
    session.close()

    assert fake.calls[0:3] == [("open", None), ("pair", 10.0), ("status", None)]
    assert ("apply", "state") in fake.calls
    assert ("reconnect", 20.0) in fake.calls
    assert fake.calls[-1] == ("close", True)
    assert fake.closed is True


def test_session_waits_for_periodic_input_report_after_reconnect() -> None:
    fake = ReportingReadyFakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)

    session.reconnect(timeout_sec=1.0)

    assert fake.status_calls == 2
    assert fake.calls[:4] == [
        ("open", None),
        ("reconnect", 1.0),
        ("status", None),
        ("status", None),
    ]


def test_session_waits_for_awaitable_controller_methods() -> None:
    fake = AwaitableFakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)

    assert session.pair(timeout_sec=10.0) is None
    session.apply("state")
    session.neutral()
    session.close()

    assert fake.calls[0:3] == [("open", None), ("pair", 10.0), ("status", None)]
    assert ("apply", "state") in fake.calls
    assert fake.calls[-1] == ("close", True)
    assert fake.closed is True


def test_session_connection_state_is_refreshed_after_remote_disconnect() -> None:
    fake = FakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)

    session.reconnect(timeout_sec=1.0)
    fake.connection_state = "closed"

    with pytest.raises(Exception) as exc_info:
        session.apply("state")
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_NOT_CONNECTED"
    assert ("apply", "state") not in fake.calls


def test_session_connection_timeout_does_not_race_longer_pair_timeout() -> None:
    fake = SlowAwaitableFakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)
    session._operation_timeout_sec = 0.01

    session.pair(timeout_sec=0.05)

    assert session.connected


def test_session_waits_for_cancelled_operation_cleanup_before_returning() -> None:
    fake = CancellationAwareFakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)
    session._operation_timeout_sec = 0.01
    session._cancellation_timeout_sec = 0.1
    session.reconnect(timeout_sec=0.05)

    with pytest.raises(Exception) as exc_info:
        session.apply("state")

    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_CONNECTION_TIMED_OUT"
    assert fake.calls[-1] == ("cancel-finished", None)
    loop_thread = session._loop_thread
    session.close()
    assert loop_thread is not None and not loop_thread.is_alive()
    assert session._loop is None


def test_session_keeps_live_event_loop_reference_when_stop_times_out() -> None:
    session = SwbtControllerSession(config())
    release = Event()
    thread = Thread(target=release.wait, daemon=True)

    class NonStoppingLoop:
        def is_running(self) -> bool:
            return True

        def call_soon_threadsafe(self, callback) -> None:
            pass

    loop = NonStoppingLoop()
    thread.start()
    session._loop = loop
    session._loop_thread = thread
    session._loop_stop_timeout_sec = 0.01

    with pytest.raises(Exception) as exc_info:
        session._stop_loop_locked()

    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_EVENT_LOOP_DID_NOT_STOP"
    assert session._loop is loop
    assert session._loop_thread is thread
    assert session._loop_stopping

    release.set()
    thread.join()
    session._stop_loop_locked()
    assert session._loop is None
    assert session._loop_thread is None
    assert not session._loop_stopping


def test_session_preserves_internal_event_loop_stop_error(monkeypatch) -> None:
    fake = FakeSwbtController()
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)
    session.reconnect(timeout_sec=1.0)
    original_call = session._call_controller

    def fail_apply(controller, method_name, *args, **kwargs):
        if method_name == "apply":
            raise swbt_configuration_error(
                "swbt event loop did not stop",
                code="NYX_SWBT_EVENT_LOOP_DID_NOT_STOP",
                component="SwbtControllerSession",
            )
        return original_call(controller, method_name, *args, **kwargs)

    monkeypatch.setattr(session, "_call_controller", fail_apply)

    with pytest.raises(Exception) as exc_info:
        session.apply("state")

    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_EVENT_LOOP_DID_NOT_STOP"
    assert exc_info.value.__cause__ is None


def test_session_close_can_be_retried_after_failure() -> None:
    fake = FakeSwbtController()
    fake.close_failures = 1
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)
    session.reconnect(timeout_sec=1.0)

    with pytest.raises(Exception):
        session.close()
    session.close()

    assert fake.calls.count(("close", True)) == 2
    assert fake.closed


def test_session_close_preserves_controller_and_loop_stop_errors(monkeypatch) -> None:
    fake = FakeSwbtController()
    fake.close_failures = 1
    session = SwbtControllerSession(config(), controller_factory=lambda _config, _writer: fake)
    session.reconnect(timeout_sec=1.0)
    original_stop = session._stop_loop_locked
    stop_error = swbt_configuration_error(
        "swbt event loop did not stop",
        code="NYX_SWBT_EVENT_LOOP_DID_NOT_STOP",
        component="SwbtControllerSession",
    )
    monkeypatch.setattr(session, "_stop_loop_locked", lambda: (_ for _ in ()).throw(stop_error))

    with pytest.raises(ExceptionGroup) as exc_info:
        session.close()

    assert [getattr(error, "code", None) for error in exc_info.value.exceptions] == [
        "NYX_SWBT_CONNECTION_FAILED",
        "NYX_SWBT_EVENT_LOOP_DID_NOT_STOP",
    ]
    monkeypatch.setattr(session, "_stop_loop_locked", original_stop)
    session.close()
    assert fake.closed


@pytest.mark.parametrize(
    ("connection_state", "expected"),
    [("connected", True), ("closed", False), ("reconnecting", False), ("failed", False)],
)
def test_status_connected_helper_uses_real_api_shape(connection_state: str, expected: bool) -> None:
    assert is_swbt_status_connected(gamepad_status(connection_state)) is expected


def test_session_requires_adapter_before_open() -> None:
    model = resolve_controller_model("pro-controller")
    session = SwbtControllerSession(
        SwbtControllerConfig(
            model=model,
            adapter=None,
            profile_path=Path(".nyxpy/swbt/pro-controller-profile.json"),
        )
    )

    with pytest.raises(Exception) as exc_info:
        session.open()

    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_ADAPTER_NOT_SELECTED"


def test_session_reconnect_without_profile_reports_profile_not_found(tmp_path: Path) -> None:
    profile_path = tmp_path / "missing-profile.json"
    session = SwbtControllerSession(replace(config(), profile_path=profile_path))

    with pytest.raises(Exception) as exc_info:
        session.reconnect(timeout_sec=1.0)

    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PROFILE_NOT_FOUND"


@pytest.mark.parametrize(
    "payload",
    [
        {"legacy": "key-store"},
        {
            "format": "swbt.profile",
            "schema_version": 1,
            "controller_kind": "pro",
            "identity": {"kind": "adapter-default"},
            "key_store": {"namespaces": {}},
        },
    ],
)
def test_session_rejects_legacy_and_schema_v1_profiles(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    profile_path = tmp_path / "legacy.json"
    profile_path.write_text(json.dumps(payload), encoding="utf-8")
    session = SwbtControllerSession(replace(config(), profile_path=profile_path))

    with pytest.raises(Exception) as exc_info:
        session.open()

    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PROFILE_INVALID"


def test_session_rejects_profile_for_different_controller_type(tmp_path: Path) -> None:
    profile_path = tmp_path / "joy-con-l-profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "format": "swbt.profile",
                "schema_version": 2,
                "controller_kind": "joycon_l",
                "identity": {"kind": "adapter-default"},
                "key_store": {"namespaces": {}},
            }
        ),
        encoding="utf-8",
    )
    session = SwbtControllerSession(replace(config(), profile_path=profile_path))

    with pytest.raises(Exception) as exc_info:
        session.open()

    assert getattr(exc_info.value, "code", None) == ("NYX_SWBT_PROFILE_CONTROLLER_MISMATCH")


def test_dummy_session_records_state_without_bluetooth_transport() -> None:
    session = DummySwbtControllerSession()

    session.open()
    result = session.reconnect(timeout_sec=1.0)
    session.apply("state")
    session.neutral()
    session.close()

    assert result is None
    assert session.opened is True
    assert session.reconnect_calls == 1
    assert session.states == ["state"]
    assert session.neutral_calls == 1
    assert session.closed is True
    assert session.status().connection_state == "closed"
