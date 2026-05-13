import pytest

from nyxpy.framework.core.hardware.capture_source import (
    CameraCaptureSourceConfig,
    CaptureRect,
    ScreenRegionCaptureSourceConfig,
    WindowCaptureSourceConfig,
)
from nyxpy.framework.core.hardware.device_discovery import DUMMY_DEVICE_NAME, DeviceInfo
from nyxpy.framework.core.hardware.window_capture import WindowCaptureBackend, WindowCaptureSession
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


class Session(WindowCaptureSession):
    def start(self) -> None:
        pass

    def latest_frame(self):
        return object()

    def stop(self) -> None:
        pass


class Backend(WindowCaptureBackend):
    def __init__(self) -> None:
        self.release_calls = 0

    def create_session(self, config, locator):
        return Session()

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

    source = CameraCaptureSourceConfig(device_name="Camera1")
    first = factory.create(source=source, allow_dummy=False, timeout_sec=0)
    second = factory.create(source=source, allow_dummy=False, timeout_sec=0)

    assert first.capture_device is second.capture_device
    first.initialize()
    second.initialize()

    assert CaptureDevice.instances[0].initialize_calls == 1

    factory.close()

    assert CaptureDevice.instances[0].release_calls == 1


def test_frame_source_factory_recreates_device_when_key_changes() -> None:
    CaptureDevice.instances.clear()
    factory = FrameSourcePortFactory(
        discovery=Discovery(),
        capture_factory=CaptureDevice,
    )

    first = factory.create(
        source=CameraCaptureSourceConfig(device_name="Camera1", fps=30.0),
        allow_dummy=False,
        timeout_sec=0,
    )
    second = factory.create(
        source=CameraCaptureSourceConfig(device_name="Camera1", fps=60.0),
        allow_dummy=False,
        timeout_sec=0,
    )

    assert first.capture_device is not second.capture_device


def test_frame_source_factory_creates_screen_region_source() -> None:
    backend = Backend()
    factory = FrameSourcePortFactory(
        discovery=Discovery(),
        window_backend_factory=lambda _name: backend,
    )

    source = ScreenRegionCaptureSourceConfig(CaptureRect(0, 0, 1280, 720))
    first = factory.create(source=source, allow_dummy=False, timeout_sec=0)
    second = factory.create(source=source, allow_dummy=False, timeout_sec=0)

    assert first.capture_device is second.capture_device


def test_frame_source_factory_creates_window_source() -> None:
    backend = Backend()
    factory = FrameSourcePortFactory(
        discovery=Discovery(),
        window_backend_factory=lambda _name: backend,
    )

    port = factory.create(
        source=WindowCaptureSourceConfig(title_pattern="Viewer"),
        allow_dummy=False,
        timeout_sec=0,
    )

    assert port.capture_device is not None


@pytest.mark.parametrize("name", [None, DUMMY_DEVICE_NAME])
def test_controller_factory_rejects_dummy_without_explicit_permission(name) -> None:
    factory = ControllerOutputPortFactory(
        discovery=Discovery(),
        protocol=Protocol(),
        serial_factory=SerialDevice,
    )

    with pytest.raises(ConfigurationError):
        factory.create(name=name, baudrate=None, allow_dummy=False, timeout_sec=0)
