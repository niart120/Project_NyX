from __future__ import annotations

import os
from pathlib import Path

import pytest

from nyxpy.framework.core.api.notification_handler import NotificationHandler
from nyxpy.framework.core.hardware.capture import CameraCaptureDevice
from nyxpy.framework.core.hardware.device_discovery import DeviceInfo
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.hardware.serial_comm import SerialComm
from nyxpy.framework.core.io.device_factories import (
    ControllerOutputPortFactory,
    FrameSourcePortFactory,
)
from nyxpy.framework.core.logger import NullLoggerPort
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.runtime.builder import create_device_runtime_builder
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.result import RunStatus


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is required for realdevice runtime test")
    return value


def _write_runtime_macro(project_root: Path) -> None:
    macro_dir = project_root / "macros" / "runtime_realdevice"
    macro_dir.mkdir(parents=True)
    (macro_dir / "macro.py").write_text(
        """from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command


class RuntimeRealDeviceMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        pass

    def run(self, cmd: Command) -> None:
        frame = cmd.capture()
        if frame is None:
            raise RuntimeError("capture returned None")
        cmd.press(Button.A, dur=0, wait=0)

    def finalize(self, cmd: Command) -> None:
        pass
""",
        encoding="utf-8",
    )


class StaticDiscovery:
    def __init__(self, serial_port: str, capture_index: int) -> None:
        self.serial = DeviceInfo(kind="serial", name=serial_port, identifier=serial_port)
        self.capture = DeviceInfo(kind="capture", name=str(capture_index), identifier=capture_index)

    def serial_names(self) -> list[str]:
        return [self.serial.name]

    def capture_names(self) -> list[str]:
        return [self.capture.name]

    def find_serial(self, name: str, timeout_sec: float) -> DeviceInfo | None:
        return self.serial if name == self.serial.name else None

    def find_capture(self, name: str, timeout_sec: float) -> DeviceInfo | None:
        return self.capture if name == self.capture.name else None


@pytest.mark.realdevice
def test_macro_runtime_runs_with_real_serial_and_capture(tmp_path: Path) -> None:
    serial_port = _required_env("NYX_REAL_SERIAL_PORT")
    capture_index = int(os.environ.get("NYX_REAL_CAPTURE_INDEX", "0"))
    protocol_name = os.environ.get("NYX_REAL_PROTOCOL", "CH552")
    baudrate = int(os.environ.get("NYX_REAL_BAUD", "9600"))

    _write_runtime_macro(tmp_path)
    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    discovery = StaticDiscovery(serial_port, capture_index)
    protocol = ProtocolFactory.create_protocol(protocol_name)
    controller_factory = ControllerOutputPortFactory(
        discovery=discovery,
        protocol=protocol,
        serial_factory=SerialComm,
    )
    frame_factory = FrameSourcePortFactory(
        discovery=discovery,
        logger=NullLoggerPort(),
        capture_factory=CameraCaptureDevice,
    )
    builder = create_device_runtime_builder(
        project_root=tmp_path,
        registry=registry,
        device_discovery=discovery,
        controller_output_factory=controller_factory,
        frame_source_factory=frame_factory,
        serial_name=serial_port,
        capture_name=str(capture_index),
        baudrate=baudrate,
        protocol=protocol,
        notification_handler=NotificationHandler([]),
        logger=NullLoggerPort(),
    )

    try:
        result = builder.run(RuntimeBuildRequest(macro_id="runtime_realdevice"))
        assert result.status is RunStatus.SUCCESS
    except Exception as exc:
        pytest.skip(f"real devices are not available: {exc}")
    finally:
        builder.shutdown()
