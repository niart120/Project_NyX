import pytest

from nyxpy.framework.core.hardware.device_discovery import DUMMY_DEVICE_NAME, DeviceInfo
from nyxpy.framework.core.io.device_factories import (
    ControllerOutputPortFactory,
    FrameSourcePortFactory,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class Discovery:
    def __init__(self) -> None:
        self.serial = DeviceInfo(kind="serial", name="COM1", identifier="COM1")
        self.capture = DeviceInfo(kind="capture", name="Camera1", identifier=1)

    def serial_names(self) -> list[str]:
        return [self.serial.name]

    def capture_names(self) -> list[str]:
        return [self.capture.name]

    def find_serial(self, name: str, timeout_sec: float) -> DeviceInfo | None:
        return self.serial if name == self.serial.name else None

    def find_capture(self, name: str, timeout_sec: float) -> DeviceInfo | None:
        return self.capture if name == self.capture.name else None


class SerialDevice:
    instances = []

    def __init__(self, port: str) -> None:
        self.port = port
        self.open_calls = []
        self.closed = False
        SerialDevice.instances.append(self)

    def open(self, baudrate: int) -> None:
        self.open_calls.append(baudrate)

    def send(self, data) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class Protocol:
    def build_release_command(self, keys):
        return b""


class CaptureDevice:
    instances = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.initialize_calls = 0
        self.release_calls = 0
        CaptureDevice.instances.append(self)

    def initialize(self) -> None:
        self.initialize_calls += 1

    def get_frame(self):
        return object()

    def release(self) -> None:
        self.release_calls += 1


def test_controller_factory_reuses_named_device_and_closes_once() -> None:
    SerialDevice.instances.clear()
    factory = ControllerOutputPortFactory(
        discovery=Discovery(),
        protocol=Protocol(),
        serial_factory=SerialDevice,
    )

    first = factory.create(name="COM1", baudrate=115200, allow_dummy=False, timeout_sec=0)
    second = factory.create(name="COM1", baudrate=9600, allow_dummy=False, timeout_sec=0)

    assert first.serial_device is second.serial_device
    assert SerialDevice.instances[0].open_calls == [115200]

    factory.close()

    assert SerialDevice.instances[0].closed is True


def test_frame_source_factory_reuses_device_and_initializes_once() -> None:
    CaptureDevice.instances.clear()
    factory = FrameSourcePortFactory(
        discovery=Discovery(),
        capture_factory=CaptureDevice,
    )

    first = factory.create(name="Camera1", allow_dummy=False, timeout_sec=0)
    second = factory.create(name="Camera1", allow_dummy=False, timeout_sec=0)

    assert first.capture_device is second.capture_device
    first.initialize()
    second.initialize()

    assert CaptureDevice.instances[0].initialize_calls == 1

    factory.close()

    assert CaptureDevice.instances[0].release_calls == 1


@pytest.mark.parametrize("name", [None, DUMMY_DEVICE_NAME])
def test_controller_factory_rejects_dummy_without_explicit_permission(name) -> None:
    factory = ControllerOutputPortFactory(
        discovery=Discovery(),
        protocol=Protocol(),
        serial_factory=SerialDevice,
    )

    with pytest.raises(ConfigurationError):
        factory.create(name=name, baudrate=None, allow_dummy=False, timeout_sec=0)
