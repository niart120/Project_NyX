from types import MethodType

from nyxpy.gui.app_services import GuiAppServices


class FakeSettings:
    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        return self.data.get(key, default)


class FakeLogger:
    def user(self, *args, **kwargs):
        pass

    def technical(self, *args, **kwargs):
        pass


class FakeBuilder:
    def __init__(self) -> None:
        self.preview = object()
        self.controller = object()

    def frame_source_for_preview(self):
        return self.preview

    def controller_output_for_manual_input(self):
        return self.controller


def make_services(settings, *, previous_builder_settings=None):
    services = object.__new__(GuiAppServices)
    services.global_settings = FakeSettings(settings)
    services.secrets_settings = FakeSettings({})
    services.logger = FakeLogger()
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
