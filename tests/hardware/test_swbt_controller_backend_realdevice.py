from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from nyxpy.framework.core.constants import Button, Hat, IMUFrame, LStick, RStick
from nyxpy.framework.core.hardware.swbt.config import (
    SwbtControllerConfig,
    SwbtControllerModel,
    resolve_controller_model,
)
from nyxpy.framework.core.hardware.swbt.controller import SwbtControllerOutputPort
from nyxpy.framework.core.hardware.swbt.discovery import (
    SwbtAdapterDiscoveryService,
    resolve_adapter,
)
from nyxpy.framework.core.hardware.swbt.session import SwbtControllerSession
from nyxpy.framework.core.macro.command import DefaultCommand
from tests.hardware.swbt_realdevice_support import (
    SwbtEvidenceResult,
    SwbtEvidenceWriter,
    SwbtRealDeviceEnvironmentMissing,
    SwbtRealDeviceOptions,
    current_git_commit,
    installed_swbt_python_version,
    load_swbt_realdevice_options,
    resolve_operator_result,
)
from tests.support.fake_execution_context import make_fake_execution_context

pytestmark = [pytest.mark.realdevice, pytest.mark.swbt]


@dataclass(slots=True)
class SwbtRealDeviceRun:
    options: SwbtRealDeviceOptions
    writer: SwbtEvidenceWriter
    results: list[SwbtEvidenceResult] = field(default_factory=list)

    @property
    def model(self) -> SwbtControllerModel:
        return resolve_controller_model(self.options.controller_type)

    def config(self) -> SwbtControllerConfig:
        return SwbtControllerConfig(
            model=self.model,
            adapter=self.options.adapter,
            key_store_path=self.options.key_store_path,
        )

    def record(self, test_name: str, status: str, **details: object) -> None:
        self.results.append(SwbtEvidenceResult(test_name=test_name, status=status, details=details))


@pytest.fixture(scope="session")
def swbt_run() -> Iterator[SwbtRealDeviceRun]:
    try:
        options = load_swbt_realdevice_options()
    except SwbtRealDeviceEnvironmentMissing as exc:
        pytest.skip(str(exc))

    writer = SwbtEvidenceWriter(options.evidence_dir)
    writer.write_run_metadata(
        options,
        command=(
            "uv",
            "run",
            "pytest",
            "tests/hardware/test_swbt_controller_backend_realdevice.py",
            "-m",
            "realdevice and swbt",
        ),
        git_commit=current_git_commit(),
        swbt_version=installed_swbt_python_version(),
    )
    run = SwbtRealDeviceRun(options=options, writer=writer)
    yield run
    writer.write_summary(options, run.results)


def test_swbt_adapter_discovery_realdevice(swbt_run: SwbtRealDeviceRun) -> None:
    adapters = SwbtAdapterDiscoveryService().list_adapters()
    selected = resolve_adapter(swbt_run.options.adapter, adapters)

    swbt_run.record(
        "test_swbt_adapter_discovery_realdevice",
        "pass",
        adapter_count=len(adapters),
        selected=selected.name,
        aliases=list(selected.aliases),
        vendor_id=selected.vendor_id,
        product_id=selected.product_id,
    )

    assert selected.name == swbt_run.options.adapter or swbt_run.options.adapter in selected.aliases


def test_swbt_pair_realdevice(swbt_run: SwbtRealDeviceRun) -> None:
    _require_operator_confirmation(swbt_run, "test_swbt_pair_realdevice")
    swbt_run.options.key_store_path.parent.mkdir(parents=True, exist_ok=True)

    with _session(swbt_run) as session:
        result = session.pair(timeout_sec=swbt_run.options.timeout_sec)
        assert session.connected is True

    assert swbt_run.options.key_store_path.exists()
    _record_operator_result(
        swbt_run,
        "test_swbt_pair_realdevice",
        prompt="Switch 上で controller の接続が確認できたか (pass/fail/skip): ",
        details={
            "controller_type": swbt_run.options.controller_type,
            "key_store_exists": True,
            "result_type": type(result).__name__,
        },
    )


def test_swbt_reconnect_realdevice(swbt_run: SwbtRealDeviceRun) -> None:
    _require_key_store(swbt_run, "test_swbt_reconnect_realdevice")

    with _session(swbt_run) as session:
        result = session.reconnect(timeout_sec=swbt_run.options.timeout_sec)
        status = session.status()
        assert session.connected is True

    swbt_run.record(
        "test_swbt_reconnect_realdevice",
        "pass",
        result_type=type(result).__name__,
        status_type=type(status).__name__,
    )


def test_swbt_button_dpad_manual_realdevice(swbt_run: SwbtRealDeviceRun) -> None:
    _require_operator_confirmation(swbt_run, "test_swbt_button_dpad_manual_realdevice")

    with _connected_port(swbt_run) as port:
        button = _supported_button(swbt_run.model)
        port.press((button,))
        time.sleep(0.05)
        port.release((button,))
        port.press((Hat.UPRIGHT,))
        time.sleep(0.05)
        port.release((Hat.UPRIGHT,))

    _record_operator_result(
        swbt_run,
        "test_swbt_button_dpad_manual_realdevice",
        prompt=f"{button.name} と UPRIGHT が正しく入力されたか (pass/fail/skip): ",
        details={"button": button.name, "dpad": "UPRIGHT"},
    )


def test_swbt_stick_manual_realdevice(swbt_run: SwbtRealDeviceRun) -> None:
    _require_operator_confirmation(swbt_run, "test_swbt_stick_manual_realdevice")

    exercised: list[str] = []
    with _connected_port(swbt_run) as port:
        if swbt_run.model.capabilities.left_stick:
            port.press((LStick.UP,))
            time.sleep(0.05)
            port.release((LStick.UP,))
            exercised.append("left_stick_up")
        if swbt_run.model.capabilities.right_stick:
            port.press((RStick.UP,))
            time.sleep(0.05)
            port.release((RStick.UP,))
            exercised.append("right_stick_up")

    assert exercised
    _record_operator_result(
        swbt_run,
        "test_swbt_stick_manual_realdevice",
        prompt="対象 stick が上方向へ入力されたか (pass/fail/skip): ",
        details={"exercised": exercised, "expected_direction": "up"},
    )


def test_swbt_imu_realdevice(tmp_path: Path, swbt_run: SwbtRealDeviceRun) -> None:
    _require_operator_confirmation(swbt_run, "test_swbt_imu_realdevice")

    with _connected_port(swbt_run) as port:
        cmd = DefaultCommand(context=make_fake_execution_context(tmp_path, controller=port))
        cmd.imu(IMUFrame.neutral())
        cmd.imu(IMUFrame.gyro(x=100))
        port.release()

    _record_operator_result(
        swbt_run,
        "test_swbt_imu_realdevice",
        prompt="IMU frame 送信時に想定外の入力や切断がなかったか (pass/fail/skip): ",
        details={"frames": ["neutral", "gyro_x_100"]},
    )


def test_swbt_neutral_after_close_realdevice(swbt_run: SwbtRealDeviceRun) -> None:
    _require_operator_confirmation(swbt_run, "test_swbt_neutral_after_close_realdevice")

    button = _supported_button(swbt_run.model)
    with _connected_port(swbt_run) as port:
        port.press((button,))
        time.sleep(0.05)
        port.close()

    _record_operator_result(
        swbt_run,
        "test_swbt_neutral_after_close_realdevice",
        prompt=f"close 後に {button.name} が押下状態で残らなかったか (pass/fail/skip): ",
        details={"button": button.name},
    )


def test_swbt_short_press_duration_realdevice(
    tmp_path: Path,
    swbt_run: SwbtRealDeviceRun,
) -> None:
    _require_operator_confirmation(swbt_run, "test_swbt_short_press_duration_realdevice")

    button = (
        Button.A
        if Button.A in swbt_run.model.capabilities.buttons
        else _supported_button(swbt_run.model)
    )
    with _connected_port(swbt_run) as port:
        cmd = DefaultCommand(context=make_fake_execution_context(tmp_path, controller=port))
        for duration_ms in swbt_run.options.short_press_ms:
            cmd.press(button, dur=duration_ms / 1000, wait=0.05)

    _record_operator_result(
        swbt_run,
        "test_swbt_short_press_duration_realdevice",
        prompt=f"{button.name} の短押しが各 duration で認識されたか (pass/fail/skip): ",
        details={
            "button": button.name,
            "durations_ms": list(swbt_run.options.short_press_ms),
        },
    )


@contextmanager
def _session(run: SwbtRealDeviceRun) -> Iterator[SwbtControllerSession]:
    with run.writer.open_trace() as trace:
        session = SwbtControllerSession(run.config(), diagnostics_writer=trace)
        try:
            yield session
        finally:
            session.close()


@contextmanager
def _connected_port(
    run: SwbtRealDeviceRun,
) -> Iterator[SwbtControllerOutputPort]:
    _require_key_store(run, "connected_swbt_port")
    with _session(run) as session:
        session.reconnect(timeout_sec=run.options.timeout_sec)
        port = SwbtControllerOutputPort(session=session, model=run.model)
        try:
            yield port
        finally:
            port.close()


def _require_operator_confirmation(run: SwbtRealDeviceRun, test_name: str) -> None:
    if run.options.operator_confirmation:
        return
    details = {"reason": "NYX_SWBT_OPERATOR_CONFIRMATION=1 is required"}
    run.writer.record_operator_confirmation(
        test_name=test_name,
        result="skip",
        details=details,
    )
    run.record(test_name, "skip", **details)
    pytest.skip("NYX_SWBT_OPERATOR_CONFIRMATION=1 is required for this realdevice test")


def _record_operator_result(
    run: SwbtRealDeviceRun,
    test_name: str,
    *,
    prompt: str,
    details: Mapping[str, object],
) -> None:
    result = resolve_operator_result(run.options, test_name, prompt=prompt)
    recorded_details = {**details, "source": result.source}
    run.writer.record_operator_confirmation(
        test_name=test_name,
        result=result.status,
        details=recorded_details,
    )
    run.record(test_name, result.status, **recorded_details)
    if result.status == "fail":
        pytest.fail(f"operator reported failure for {test_name}")
    if result.status == "skip":
        pytest.skip(f"operator skipped {test_name}")


def _require_key_store(run: SwbtRealDeviceRun, test_name: str) -> None:
    if run.options.key_store_path.exists():
        return
    run.record(
        test_name,
        "skip",
        reason="pairing key store is missing; run test_swbt_pair_realdevice first",
        key_store=str(run.options.key_store_path),
    )
    pytest.skip("swbt key store is missing; run pair test first")


def _supported_button(model: SwbtControllerModel) -> Button:
    return sorted(model.capabilities.buttons, key=lambda button: button.name)[0]
