import time

from nyxpy.framework.core.hardware.capture_source import CaptureRect
from nyxpy.framework.core.hardware.device_discovery import (
    DUMMY_DEVICE_NAME,
    DeviceDiscoveryService,
    DeviceInfo,
)
from nyxpy.framework.core.hardware.window_discovery import (
    WindowDiscoveryDiagnostics,
    WindowInfo,
)


class Discovery(DeviceDiscoveryService):
    def __init__(self) -> None:
        super().__init__()
        self.delay = 0.0

    def _detect_serial_devices(self) -> list[DeviceInfo]:
        if self.delay:
            time.sleep(self.delay)
        return [DeviceInfo(kind="serial", name="COM1", identifier="COM1")]

    def _detect_capture_devices(self) -> list[DeviceInfo]:
        if self.delay:
            time.sleep(self.delay)
        return [DeviceInfo(kind="capture", name="Camera1", identifier=1)]


class WindowLocator:
    def list_windows(self) -> tuple[WindowInfo, ...]:
        return (WindowInfo("Viewer", "hwnd-1", CaptureRect(10, 20, 600, 720), 1234),)

    def diagnostics(self) -> WindowDiscoveryDiagnostics:
        return WindowDiscoveryDiagnostics(
            platform_name="Windows",
            total_handles=1,
            visible_handles=1,
            titled_handles=1,
            valid_rect_handles=1,
            returned_windows=1,
        )


def test_device_discovery_returns_detected_names_without_dummy() -> None:
    discovery = Discovery()

    result = discovery.detect(timeout_sec=1.0)

    assert result.serial_names() == ["COM1"]
    assert result.capture_names() == ["Camera1"]
    assert DUMMY_DEVICE_NAME not in result.serial_names()
    assert DUMMY_DEVICE_NAME not in result.capture_names()


def test_device_discovery_reports_timeout() -> None:
    discovery = Discovery()
    discovery.delay = 0.05

    result = discovery.detect(timeout_sec=0.0)

    assert result.timed_out is True
    assert result.serial_names() == []
    assert result.capture_names() == []


def test_device_discovery_reports_detection_errors() -> None:
    class FailingDiscovery(Discovery):
        def _detect_serial_devices(self) -> list[DeviceInfo]:
            raise RuntimeError("serial failed")

    result = FailingDiscovery().detect(timeout_sec=1.0)

    assert result.serial_names() == []
    assert result.capture_names() == ["Camera1"]
    assert result.errors == ("serial: RuntimeError: serial failed",)


def test_device_discovery_lists_capture_target_windows_separately() -> None:
    discovery = Discovery()
    discovery.window_locator = WindowLocator()

    windows = discovery.detect_window_sources(timeout_sec=1.0)

    assert windows == (
        WindowInfo("Viewer", "hwnd-1", CaptureRect(10, 20, 600, 720), 1234),
    )
    assert discovery.capture_names() == []


def test_device_discovery_exposes_window_source_diagnostics() -> None:
    discovery = Discovery()
    discovery.window_locator = WindowLocator()

    assert discovery.window_source_diagnostics() == (
        "platform=Windows total=1 visible=1 titled=1 rect=1 returned=1"
    )
