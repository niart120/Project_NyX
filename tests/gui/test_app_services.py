from types import MethodType

from nyxpy.framework.core.hardware.device_discovery import (
    DeviceDiscoveryResult,
    DeviceInfo,
    WindowDiscoveryResult,
)
from nyxpy.framework.core.hardware.window_discovery import WindowInfo
from nyxpy.gui.app_services import GuiAppServices


class FakeSettings:
    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class FakeLogger:
    def __init__(self) -> None:
        self.technical_events = []

    def user(self, *args, **kwargs):
        pass

    def technical(self, *args, **kwargs):
        self.technical_events.append((args, kwargs))


class FakeDiscovery:
    def __init__(
        self,
        *,
        serial=(),
        capture=(),
        windows=(),
        window_discovery_failed: bool = False,
    ) -> None:
        self.serial_devices = tuple(
            DeviceInfo(kind="serial", name=name, identifier=name) for name in serial
        )
        self.capture_devices = tuple(
            DeviceInfo(kind="capture", name=name, identifier=index)
            for index, name in enumerate(capture)
        )
        self.windows = tuple(windows)
        self.window_discovery_failed = window_discovery_failed
        self.detect_calls = 0
        self.window_detect_calls = 0

    def detect(self, timeout_sec=2.0) -> DeviceDiscoveryResult:
        self.detect_calls += 1
        return DeviceDiscoveryResult(
            serial_devices=self.serial_devices,
            capture_devices=self.capture_devices,
        )

    def detect_window_sources(self, timeout_sec=2.0):
        self.window_detect_calls += 1
        return self.windows

    def detect_window_sources_result(self, timeout_sec=2.0):
        self.window_detect_calls += 1
        if self.window_discovery_failed:
            return WindowDiscoveryResult(failed=True)
        return WindowDiscoveryResult(window_sources=self.windows)


class RaisingWindowDiscovery(FakeDiscovery):
    def detect_window_sources_result(self, timeout_sec=2.0):
        self.window_detect_calls += 1
        raise OSError("window discovery failed")


class FakeBuilder:
    def __init__(self) -> None:
        self.preview = object()
        self.controller = object()
        self.preview_error: Exception | None = None
        self.controller_error: Exception | None = None

    def frame_source_for_preview(self):
        if self.preview_error is not None:
            raise self.preview_error
        return self.preview

    def controller_output_for_manual_input(self):
        if self.controller_error is not None:
            raise self.controller_error
        return self.controller


def make_services(settings, *, previous_builder_settings=None, device_discovery=None):
    services = object.__new__(GuiAppServices)
    services.global_settings = FakeSettings(settings)
    services.secrets_settings = FakeSettings({})
    services.logger = FakeLogger()
    services.device_discovery = device_discovery or FakeDiscovery(
        serial=("COM1",),
        capture=("Camera1",),
        windows=(WindowInfo("Viewer", "hwnd-1", None),),
    )
    services.runtime_builder = FakeBuilder()
    services._last_settings = dict(settings)
    services._last_secrets = {}
    services._builder_settings = previous_builder_settings or dict(settings)
    services._builder_secrets = {}
    services._active_frame_source_key = (
        "camera",
        "Camera1",
        None,
        False,
    )
    services._pending_settings_apply = False

    def replace_runtime_builder(self):
        self.runtime_builder = FakeBuilder()
        from nyxpy.gui.app_services import _frame_source_key

        self._active_frame_source_key = _frame_source_key(self.global_settings.data)

    services._replace_runtime_builder = MethodType(replace_runtime_builder, services)
    return services


def test_app_services_rebuilds_builder_when_frame_source_key_changes() -> None:
    settings = {
        "capture_source_type": "window",
        "capture_device": "Camera1",
        "capture_window_title": "Viewer",
        "capture_window_match_mode": "exact",
        "capture_backend": "mss",
    }
    services = make_services(settings)
    services._builder_settings = {"capture_source_type": "camera", "capture_device": "Camera1"}

    outcome = services.apply_settings(is_run_active=False)

    assert outcome.builder_replaced is True
    assert outcome.frame_source_changed is True
    assert outcome.preview_frame_source is services.runtime_builder.preview


def test_app_services_does_not_rebuild_for_unrelated_setting() -> None:
    settings = {
        "capture_source_type": "camera",
        "capture_device": "Camera1",
        "serial_baud": 115200,
    }
    services = make_services(
        settings,
        previous_builder_settings={
            "capture_source_type": "camera",
            "capture_device": "Camera1",
            "serial_baud": 9600,
        },
    )

    outcome = services.apply_settings(is_run_active=False)

    assert outcome.builder_replaced is True
    assert outcome.frame_source_changed is False


def test_app_services_ignores_camera_device_change_while_window_source_is_active() -> None:
    settings = {
        "capture_source_type": "window",
        "capture_device": "Camera2",
        "capture_window_title": "Viewer",
        "capture_window_identifier": "",
        "capture_window_match_mode": "contains",
        "capture_backend": "mss",
    }
    services = make_services(
        settings,
        previous_builder_settings={
            **settings,
            "capture_device": "Camera1",
        },
    )
    services._active_frame_source_key = (
        "window",
        "Viewer",
        None,
        "contains",
        "mss",
        None,
        False,
    )

    outcome = services.apply_settings(is_run_active=False)

    assert outcome.builder_replaced is True
    assert outcome.frame_source_changed is False


def test_app_services_ignores_window_title_change_while_camera_source_is_active() -> None:
    settings = {
        "capture_source_type": "camera",
        "capture_device": "Camera1",
        "capture_window_title": "Viewer",
    }
    services = make_services(
        settings,
        previous_builder_settings={
            **settings,
            "capture_window_title": "Old Viewer",
        },
    )

    outcome = services.apply_settings(is_run_active=False)

    assert outcome.builder_replaced is True
    assert outcome.frame_source_changed is False


def test_app_services_does_not_rebuild_for_gui_only_setting() -> None:
    settings = {
        "capture_source_type": "window",
        "capture_window_title": "Viewer",
        "capture_window_match_mode": "contains",
        "capture_backend": "mss",
        "preview_fps": 30,
        "gui": {"window_size_preset": "wqhd"},
    }
    services = make_services(
        settings,
        previous_builder_settings={
            **settings,
            "preview_fps": 60,
            "gui": {"window_size_preset": "full_hd"},
        },
    )
    previous_builder = services.runtime_builder

    outcome = services.apply_settings(is_run_active=False)

    assert outcome.builder_replaced is False
    assert services.runtime_builder is previous_builder


def test_app_services_reports_preview_start_failure_without_failing_settings() -> None:
    settings = {
        "capture_source_type": "window",
        "capture_window_title": "Missing Viewer",
        "capture_window_match_mode": "contains",
        "capture_backend": "mss",
    }
    services = make_services(
        settings,
        previous_builder_settings={"capture_source_type": "camera", "capture_device": "Camera1"},
        device_discovery=FakeDiscovery(windows=(WindowInfo("Missing Viewer", "hwnd-2", None),)),
    )

    def replace_runtime_builder(self):
        self.runtime_builder = FakeBuilder()
        self.runtime_builder.preview_error = RuntimeError("window capture failed to start")
        from nyxpy.gui.app_services import _frame_source_key

        self._active_frame_source_key = _frame_source_key(self.global_settings.data)

    services._replace_runtime_builder = MethodType(replace_runtime_builder, services)

    outcome = services.apply_settings(is_run_active=False)

    assert outcome.builder_replaced is True
    assert outcome.preview_frame_source is None
    assert str(outcome.preview_error) == "window capture failed to start"
    assert outcome.manual_controller is services.runtime_builder.controller
    assert services.logger.technical_events[-1][1]["event"] == "configuration.preview_failed"


def test_app_services_discards_unavailable_serial_setting() -> None:
    settings = {
        "capture_source_type": "camera",
        "capture_device": "Camera1",
        "serial_device": "COM9",
    }
    services = make_services(settings, device_discovery=FakeDiscovery(capture=("Camera1",)))

    outcome = services.apply_settings(is_run_active=False)

    assert services.global_settings.get("serial_device") == ""
    assert "serial_device" in outcome.changed_keys
    assert outcome.builder_replaced is True


def test_app_services_discards_unavailable_camera_setting() -> None:
    settings = {
        "capture_source_type": "camera",
        "capture_device": "Missing Camera",
        "serial_device": "COM1",
    }
    services = make_services(settings, device_discovery=FakeDiscovery(serial=("COM1",)))

    outcome = services.apply_settings(is_run_active=False)

    assert services.global_settings.get("capture_device") == ""
    assert "capture_device" in outcome.changed_keys
    assert outcome.builder_replaced is True


def test_app_services_discards_unavailable_window_setting() -> None:
    settings = {
        "capture_source_type": "window",
        "capture_window_title": "Closed Viewer",
        "capture_window_identifier": "hwnd-old",
        "capture_window_match_mode": "exact",
        "serial_device": "COM1",
    }
    services = make_services(settings, device_discovery=FakeDiscovery(serial=("COM1",)))

    outcome = services.apply_settings(is_run_active=False)

    assert services.global_settings.get("capture_window_title") == ""
    assert services.global_settings.get("capture_window_identifier") == ""
    assert "capture_window_title" in outcome.changed_keys
    assert "capture_window_identifier" in outcome.changed_keys


def test_app_services_keeps_identifier_only_window_setting_when_window_exists() -> None:
    settings = {
        "capture_source_type": "window",
        "capture_window_title": "",
        "capture_window_identifier": "hwnd-1",
        "capture_window_match_mode": "exact",
        "serial_device": "COM1",
    }
    services = make_services(
        settings,
        device_discovery=FakeDiscovery(
            serial=("COM1",),
            windows=(WindowInfo("Viewer", "hwnd-1", None),),
        ),
    )

    services.apply_settings(is_run_active=False)

    assert services.global_settings.get("capture_window_title") == ""
    assert services.global_settings.get("capture_window_identifier") == "hwnd-1"


def test_app_services_keeps_window_setting_when_window_discovery_failed() -> None:
    settings = {
        "capture_source_type": "window",
        "capture_window_title": "Viewer",
        "capture_window_identifier": "hwnd-1",
        "capture_window_match_mode": "exact",
        "serial_device": "COM1",
    }
    services = make_services(
        settings,
        device_discovery=FakeDiscovery(
            serial=("COM1",),
            window_discovery_failed=True,
        ),
    )

    services.apply_settings(is_run_active=False)

    assert services.global_settings.get("capture_window_title") == "Viewer"
    assert services.global_settings.get("capture_window_identifier") == "hwnd-1"


def test_app_services_keeps_window_setting_when_window_discovery_raises() -> None:
    settings = {
        "capture_source_type": "window",
        "capture_window_title": "Viewer",
        "capture_window_identifier": "hwnd-1",
        "capture_window_match_mode": "exact",
        "serial_device": "COM1",
    }
    services = make_services(
        settings,
        device_discovery=RaisingWindowDiscovery(serial=("COM1",)),
    )

    services.apply_settings(is_run_active=False)

    assert services.global_settings.get("capture_window_title") == "Viewer"
    assert services.global_settings.get("capture_window_identifier") == "hwnd-1"
