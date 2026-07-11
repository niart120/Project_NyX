from __future__ import annotations

import sys
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog

from nyxpy.framework.core.constants import Button, Hat
from nyxpy.framework.core.hardware.device_discovery import (
    DUMMY_DEVICE_NAME,
    DeviceDiscoveryResult,
    DeviceInfo,
    WindowDiscoveryResult,
)
from nyxpy.framework.core.hardware.window_discovery import WindowInfo
from nyxpy.framework.core.logger import LogSanitizer, LogSinkDispatcher
from nyxpy.framework.core.macro.exceptions import ErrorInfo, ErrorKind
from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.gui.app_services import SettingsApplyOutcome
from nyxpy.gui.layout import LEFT_PANE_CONTENT_MARGIN
from nyxpy.gui.main_window import MainWindow
from nyxpy.gui.panes.control_pane import RunUiState
from tests.support.fakes import FakeControllerOutputPort, FakeFullCapabilityController


class RecordingLogger:
    def __init__(self) -> None:
        self.user_events = []
        self.technical_events = []

    def bind_context(self, context):
        return self

    def user(self, level, message, *, component, event, code=None, extra=None):
        self.user_events.append((level, message, component, event, code, extra))

    def technical(self, level, message, *, component, event="log.message", extra=None, exc=None):
        self.technical_events.append((level, message, component, event, extra, exc))


class FakeLogging:
    def __init__(self, logger: RecordingLogger) -> None:
        self.logger = logger
        self.dispatcher = LogSinkDispatcher(LogSanitizer())
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeSettings:
    def __init__(self) -> None:
        self.data = {
            "preview_fps": 30,
            "runtime": {
                "gui_poll_interval_ms": 100,
                "gui_close_wait_timeout_sec": 1.25,
            },
            "gui": {
                "window_size_preset": "full_hd",
                "preview_touch_enabled": False,
            },
            "capture_device": "",
            "capture_source_type": "camera",
            "capture_window_title": "",
            "capture_window_identifier": "",
            "controller": {
                "backend": "serial",
                "serial": {
                    "device": "",
                    "protocol": "CH552",
                    "baudrate": 9600,
                },
                "swbt": {
                    "controller_type": "pro-controller",
                    "adapter": None,
                    "key_store_path": None,
                },
            },
            "capture_fps": None,
            "capture_provider": "ponkan",
            "capture_device_profile": "n3dsxl",
            "ponkan_backend": "auto",
            "ponkan_raw_slots": 2,
            "ponkan_output_queue_size": 2,
            "ponkan_drop_policy": "drop_oldest",
            "ponkan_poll_interval": 0.004,
            "ponkan_read_timeout": 1.0,
            "ponkan_collect_timing": False,
            "n3dsxl_hd_aspect_box_enabled": True,
        }

    def get(self, key: str, default=None):
        value = self.data
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def set(self, key: str, value):
        current = self.data
        parts = key.split(".")
        for part in parts[:-1]:
            nested = current.get(part)
            if not isinstance(nested, dict):
                nested = {}
                current[part] = nested
            current = nested
        current[parts[-1]] = value


class FakeSecrets:
    data = {}

    def get(self, key: str, default=None):
        return default


class FakeCatalog:
    def __init__(self) -> None:
        self.definitions = [
            SimpleNamespace(
                id="dummy-id",
                display_name="Dummy Macro",
                class_name="DummyMacro",
                macro_root=Path("macros") / "dummy",
                description="dummy desc",
                tags=("Tag1", "Tag2"),
            )
        ]
        self.reloads = 0

    def reload_macros(self) -> None:
        self.reloads += 1

    def list(self):
        return list(self.definitions)

    def get(self, macro_id: str):
        return next(definition for definition in self.definitions if definition.id == macro_id)


class FakeDiscovery:
    def __init__(self) -> None:
        self.detect_calls = 0
        self.window_detect_calls = 0
        self._last_result = DeviceDiscoveryResult(
            serial_devices=(
                DeviceInfo(kind="serial", name="USB Serial Device (COM1)", identifier="COM1"),
            ),
            capture_devices=(DeviceInfo(kind="capture", name="Camera1", identifier=1),),
        )
        self._last_window_sources = (WindowInfo(title="Viewer", identifier="hwnd-1", rect=None),)
        self.detected_window_sources = self._last_window_sources

    @property
    def last_result(self) -> DeviceDiscoveryResult:
        return self._last_result

    @property
    def last_window_sources(self) -> tuple[WindowInfo, ...]:
        return self._last_window_sources

    def detect(self, timeout_sec: float = 2.0) -> DeviceDiscoveryResult:
        self.detect_calls += 1
        return self._last_result

    def detect_window_sources_result(
        self,
        timeout_sec: float = 2.0,
    ) -> WindowDiscoveryResult:
        self.window_detect_calls += 1
        self._last_window_sources = self.detected_window_sources
        return WindowDiscoveryResult(window_sources=self.detected_window_sources)

    def serial_display_name(self, identifier: object) -> str:
        if str(identifier) == "COM1":
            return "USB Serial Device (COM1)"
        return str(identifier)


class FakeBuilder:
    def __init__(self, handle=None) -> None:
        self.handle = handle
        self.start = MagicMock(return_value=handle)
        self.manual_controller = FakeControllerOutputPort()

    def controller_output_for_manual_input(self):
        return self.manual_controller


class FakeServices:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = Path.cwd() if project_root is None else project_root
        self.logger = RecordingLogger()
        self.logging = FakeLogging(self.logger)
        self.global_settings = FakeSettings()
        self.secrets_settings = FakeSecrets()
        self.device_discovery = FakeDiscovery()
        self.macro_catalog = FakeCatalog()
        self.ponkan_capture_available = True
        self.builder = FakeBuilder()
        self.discarded_manual_controllers = []
        self.swbt_calls = []
        self.apply_calls = []
        self.next_apply_outcome = SettingsApplyOutcome(
            changed_keys=frozenset(),
            builder_replaced=False,
            frame_source_changed=False,
            preview_frame_source=None,
            manual_controller=None,
        )
        self.next_flush_outcome = None
        self.closed = False

    @property
    def close_wait_timeout_sec(self) -> float:
        return 1.25

    def create_runtime_builder(self):
        return self.builder

    def apply_settings(self, *, is_run_active: bool = False):
        self.apply_calls.append(is_run_active)
        return self.next_apply_outcome

    def flush_deferred_settings(self):
        return self.next_flush_outcome

    def discard_manual_controller(self, controller) -> None:
        self.discarded_manual_controllers.append(controller)
        if self.builder.manual_controller is controller:
            self.builder.manual_controller = FakeControllerOutputPort()

    def refresh_swbt_adapters(self):
        self.swbt_calls.append("refresh")
        return ()

    def pair_swbt(self):
        self.swbt_calls.append("pair")
        return SimpleNamespace(
            connected=True,
            controller_type="pro-controller",
            adapter="hci0",
            message="connected",
        )

    def reconnect_swbt(self):
        self.swbt_calls.append("reconnect")
        return SimpleNamespace(
            connected=True,
            controller_type="pro-controller",
            adapter="hci0",
            message="connected",
        )

    def disconnect_swbt(self):
        self.swbt_calls.append("disconnect")

    def swbt_status(self):
        return None

    def close(self) -> None:
        self.closed = True
        self.logging.close()


class FakeRunHandle:
    def __init__(self, result: RunResult | None = None, *, done: bool = False) -> None:
        self._result = result
        self._done = done
        self.cancelled = False
        self.wait_called_with = None

    @property
    def run_id(self) -> str:
        return "run-1"

    @property
    def cancellation_token(self):
        return None

    def cancel(self) -> None:
        self.cancelled = True

    def done(self) -> bool:
        return self._done

    def wait(self, timeout=None) -> bool:
        self.wait_called_with = timeout
        return self._done

    def result(self):
        if self._result is None:
            raise RuntimeError("no result")
        return self._result


@pytest.fixture
def services(tmp_path) -> FakeServices:
    return FakeServices(project_root=tmp_path)


@pytest.fixture
def window(qtbot, services: FakeServices) -> MainWindow:
    w = MainWindow(services=services)
    qtbot.addWidget(w)
    w.deferred_init()
    w.status_label.setText("準備完了")
    yield w
    w.preview_pane.timer.stop()


def test_main_window_accepts_injected_project_root(qtbot, tmp_path) -> None:
    services = FakeServices(project_root=tmp_path / "service-root")
    project_root = tmp_path / "explicit-root"

    w = MainWindow(services=services, project_root=project_root)
    qtbot.addWidget(w)

    assert w.project_root == project_root


def run_result(status: RunStatus, message: str = "") -> RunResult:
    from datetime import datetime

    now = datetime.now()
    error = (
        ErrorInfo(
            kind=ErrorKind.MACRO,
            code="NYX_MACRO_FAILED",
            message=message,
            component="test",
            exception_type="RuntimeError",
            recoverable=False,
        )
        if message
        else None
    )
    return RunResult(
        run_id="run-1",
        macro_id="dummy-id",
        macro_name="Dummy Macro",
        status=status,
        started_at=now,
        finished_at=now,
        error=error,
    )


def select_macro(window: MainWindow, macro_id: str = "dummy-id") -> None:
    item = window.macro_browser._find_tree_item(macro_id)
    assert item is not None
    window.macro_browser.explorer_tree.setCurrentItem(item)


def test_initial_ui_state(window: MainWindow):
    assert window.macro_browser.explorer_tree.topLevelItemCount() == 1
    assert window.macro_browser.explorer_tree.topLevelItem(0).text(0) == "Dummy Macro"
    assert window.status_label.text() == "準備完了"
    assert window.touch_panel_checkbox.text() == "タッチパネル"
    assert not window.touch_panel_checkbox.isChecked()
    assert not window.control_pane.run_btn.isEnabled()
    assert not window.control_pane.cancel_btn.isEnabled()
    assert window.control_pane.snapshot_btn.isEnabled()


def test_main_window_replaces_file_menu_with_connection_menu(window: MainWindow) -> None:
    top_level_menus = [action.text() for action in window.menuBar().actions()]

    assert "接続" in top_level_menus
    assert "File" not in top_level_menus
    assert all(action.text() != "Settings" for action in window.menuBar().actions())


def test_connection_menu_has_required_children(window: MainWindow) -> None:
    assert window.connection_menu is not None

    child_menus = [
        action.menu().title()
        for action in window.connection_menu.actions()
        if action.menu() is not None
    ]

    assert child_menus[:4] == ["キャプチャ入力", "コントローラー", "シリアルデバイス", "プロトコル"]


def test_capture_input_menu_nests_candidates_under_input_source(window: MainWindow) -> None:
    assert window.capture_source_type_menu is not None

    source_menus = [
        action.menu().title()
        for action in window.capture_source_type_menu.actions()
        if action.menu() is not None
    ]

    assert source_menus == ["カメラ", "ウィンドウ", "キャプチャ"]


def test_connection_menu_hides_capture_when_ponkan_unavailable(
    qtbot,
    services: FakeServices,
) -> None:
    services.ponkan_capture_available = False
    w = MainWindow(services=services)
    qtbot.addWidget(w)

    assert w.capture_source_type_menu is not None
    source_menus = [
        action.menu().title()
        for action in w.capture_source_type_menu.actions()
        if action.menu() is not None
    ]

    assert source_menus == ["カメラ", "ウィンドウ"]
    assert w.capture_source_menu is None
    w.preview_pane.timer.stop()


def test_connection_menu_shows_n3dsxl_action_under_capture_when_ponkan_available(
    window: MainWindow,
) -> None:
    assert window.capture_source_menu is not None

    assert [action.text() for action in window.capture_source_menu.actions()] == [
        "N3DSXL (ponkan-python)"
    ]
    assert all(action.menu() is None for action in window.capture_source_menu.actions())
    assert window.capture_provider_menu is None


def test_connection_menu_applies_fixed_ponkan_profile(window: MainWindow) -> None:
    assert window.capture_source_menu is not None
    action = next(
        action
        for action in window.capture_source_menu.actions()
        if action.text() == "N3DSXL (ponkan-python)"
    )

    action.trigger()

    assert window.global_settings.get("capture_source_type") == "capture"
    assert window.global_settings.get("capture_provider") == "ponkan"
    assert window.global_settings.get("capture_device_profile") == "n3dsxl"
    assert window.services.apply_calls[-1] is False


def test_connection_menu_removes_ponkan_backend_submenu(
    window: MainWindow,
) -> None:
    assert window.capture_input_menu is not None
    child_menus = [
        action.menu().title()
        for action in window.capture_input_menu.actions()
        if action.menu() is not None
    ]

    assert child_menus == ["入力ソース", "FPS"]
    assert window.capture_settings_menu is None
    assert window.ponkan_backend_menu is None


def test_connection_menu_disables_capture_fps_for_capture_source(window: MainWindow) -> None:
    window.global_settings.set("capture_source_type", "capture")
    window._refresh_connection_menu()

    assert window.capture_fps_menu is not None
    assert not window.capture_fps_menu.isEnabled()


def test_connection_menu_does_not_list_physical_ponkan_devices(window: MainWindow) -> None:
    assert window.capture_source_menu is not None

    actions = window.capture_source_menu.actions()

    assert len(actions) == 1
    assert actions[0].text() == "N3DSXL (ponkan-python)"


def test_connection_menu_does_not_import_ponkan_when_populating_capture_actions(
    window: MainWindow,
) -> None:
    sys.modules.pop("ponkan", None)

    window._refresh_connection_menu()

    assert "ponkan" not in sys.modules


def test_connection_menu_lists_snapshot_without_detecting(window: MainWindow) -> None:
    discovery = window.services.device_discovery
    assert isinstance(discovery, FakeDiscovery)
    discovery.detect_calls = 0
    discovery.window_detect_calls = 0

    window._refresh_connection_menu()

    assert discovery.detect_calls == 0
    assert discovery.window_detect_calls == 0
    assert window.capture_input_menu is not None
    assert window.serial_device_menu is not None
    assert window.camera_source_menu is not None
    assert "Camera1" in [action.text() for action in window.camera_source_menu.actions()]
    assert "USB Serial Device (COM1)" in [
        action.text() for action in window.serial_device_menu.actions()
    ]


def test_connection_menu_refresh_detects_window_sources_when_camera_is_active(
    window: MainWindow,
) -> None:
    discovery = window.services.device_discovery
    assert isinstance(discovery, FakeDiscovery)
    discovery._last_window_sources = ()
    discovery.detected_window_sources = (
        WindowInfo(title="Detected Viewer", identifier="hwnd-2", rect=None),
    )

    window.global_settings.set("capture_source_type", "camera")
    window._refresh_connection_menu(refresh_discovery=True)

    assert discovery.detect_calls == 1
    assert discovery.window_detect_calls == 1
    assert window.window_source_menu is not None
    assert "Detected Viewer" in [action.text() for action in window.window_source_menu.actions()]


def test_connection_menu_applies_capture_device_setting(window: MainWindow) -> None:
    assert window.camera_source_menu is not None
    action = next(
        action for action in window.camera_source_menu.actions() if action.text() == "Camera1"
    )

    action.trigger()

    assert window.global_settings.get("capture_device") == "Camera1"
    assert window.global_settings.get("capture_source_type") == "camera"
    assert window.services.apply_calls[-1] is False


def test_connection_menu_checks_explicit_dummy_actions(window: MainWindow) -> None:
    window.global_settings.set("capture_device", DUMMY_DEVICE_NAME)
    window.global_settings.set("controller.serial.device", DUMMY_DEVICE_NAME)

    window._refresh_connection_menu()

    assert window.camera_source_menu is not None
    capture_dummy = next(
        action
        for action in window.camera_source_menu.actions()
        if action.text() == DUMMY_DEVICE_NAME
    )
    assert capture_dummy.isChecked()
    assert window.serial_device_menu is not None
    serial_dummy = next(
        action
        for action in window.serial_device_menu.actions()
        if action.text() == DUMMY_DEVICE_NAME
    )
    assert serial_dummy.isChecked()


def test_connection_menu_applies_dummy_device_setting(window: MainWindow) -> None:
    assert window.camera_source_menu is not None
    capture_dummy = next(
        action
        for action in window.camera_source_menu.actions()
        if action.text() == DUMMY_DEVICE_NAME
    )

    capture_dummy.trigger()

    assert window.global_settings.get("capture_source_type") == "camera"
    assert window.global_settings.get("capture_device") == DUMMY_DEVICE_NAME
    assert window.serial_device_menu is not None
    serial_dummy = next(
        action
        for action in window.serial_device_menu.actions()
        if action.text() == DUMMY_DEVICE_NAME
    )

    serial_dummy.trigger()

    assert window.global_settings.get("controller.serial.device") == DUMMY_DEVICE_NAME


def test_connection_menu_shows_auto_fallback_without_checking_dummy(
    window: MainWindow,
) -> None:
    window.global_settings.set("capture_device", "Missing Camera")
    window.global_settings.set("controller.serial.device", "COM9")

    window._refresh_connection_menu()

    assert window.camera_source_menu is not None
    capture_actions = window.camera_source_menu.actions()
    capture_dummy = next(action for action in capture_actions if action.text() == DUMMY_DEVICE_NAME)
    assert not capture_dummy.isChecked()
    assert any(
        action.text() == "自動フォールバック中: Missing Camera 未検出" and not action.isEnabled()
        for action in capture_actions
    )
    assert window.serial_device_menu is not None
    serial_actions = window.serial_device_menu.actions()
    serial_dummy = next(action for action in serial_actions if action.text() == DUMMY_DEVICE_NAME)
    assert not serial_dummy.isChecked()
    assert any(
        action.text() == "自動フォールバック中: COM9 未検出" and not action.isEnabled()
        for action in serial_actions
    )


def test_connection_menu_shows_window_auto_fallback_status(
    window: MainWindow,
) -> None:
    window.global_settings.set("capture_window_identifier", "missing-hwnd")
    window.global_settings.set("capture_window_title", "Missing Viewer")

    window._refresh_connection_menu()

    assert window.window_source_menu is not None
    assert any(
        action.text() == "自動フォールバック中: missing-hwnd 未検出" and not action.isEnabled()
        for action in window.window_source_menu.actions()
    )


def test_connection_menu_applies_window_source_setting(window: MainWindow) -> None:
    assert window.window_source_menu is not None
    action = next(
        action for action in window.window_source_menu.actions() if "Viewer" in action.text()
    )

    action.trigger()

    assert window.global_settings.get("capture_source_type") == "window"
    assert window.global_settings.get("capture_window_title") == "Viewer"
    assert window.global_settings.get("capture_window_identifier") == "hwnd-1"


def test_connection_menu_preserves_inactive_source_settings(window: MainWindow) -> None:
    window.global_settings.set("capture_device", "Camera1")
    window.global_settings.set("capture_window_title", "Viewer")
    window.global_settings.set("capture_window_identifier", "hwnd-1")
    window.global_settings.set("ponkan_backend", "d3xx")
    assert window.capture_source_menu is not None
    action = next(
        action
        for action in window.capture_source_menu.actions()
        if action.text() == "N3DSXL (ponkan-python)"
    )

    action.trigger()

    assert window.global_settings.get("capture_device") == "Camera1"
    assert window.global_settings.get("capture_window_title") == "Viewer"
    assert window.global_settings.get("capture_window_identifier") == "hwnd-1"
    assert window.global_settings.get("ponkan_backend") == "d3xx"


def test_connection_menu_clamps_baudrate_when_protocol_changes(window: MainWindow) -> None:
    window.global_settings.set("controller.serial.baudrate", 115200)
    assert window.protocol_menu is not None
    action = next(action for action in window.protocol_menu.actions() if action.text() == "CH552")

    action.trigger()

    assert window.global_settings.get("controller.serial.protocol") == "CH552"
    assert window.global_settings.get("controller.serial.baudrate") == 9600


def test_main_window_wires_preview_touch_to_virtual_controller_model(window: MainWindow) -> None:
    controller = FakeFullCapabilityController()
    window.virtual_controller.model.set_controller(controller)
    window._sync_manual_input_state()
    window.touch_panel_checkbox.setChecked(True)

    window.preview_pane.touch_down_requested.emit(10, 20)
    window.preview_pane.touch_move_requested.emit(11, 21)
    window.preview_pane.touch_up_requested.emit()

    assert controller.events == [
        ("touch_down", (10, 20)),
        ("touch_down", (11, 21)),
        ("touch_up", None),
    ]


def test_main_window_initializes_touch_panel_checkbox_from_settings(
    qtbot,
    services: FakeServices,
) -> None:
    services.global_settings.set("gui.preview_touch_enabled", True)

    w = MainWindow(services=services)
    qtbot.addWidget(w)

    assert w.touch_panel_checkbox.isChecked()
    w.preview_pane.timer.stop()


def test_main_window_saves_touch_panel_checkbox_to_settings(window: MainWindow) -> None:
    window.status_label.setText("保持")

    window.touch_panel_checkbox.setChecked(True)
    assert window.global_settings.get("gui.preview_touch_enabled") is True
    assert window.status_label.text() == "保持"

    window.touch_panel_checkbox.setChecked(False)
    assert window.global_settings.get("gui.preview_touch_enabled") is False
    assert window.status_label.text() == "保持"


def test_main_window_ignores_preview_touch_when_touch_panel_is_disabled(
    window: MainWindow,
) -> None:
    controller = FakeFullCapabilityController()
    window.virtual_controller.model.set_controller(controller)

    window.preview_pane.touch_down_requested.emit(10, 20)
    window.preview_pane.touch_move_requested.emit(11, 21)
    window.preview_pane.touch_up_requested.emit()

    assert controller.events == []
    assert window.status_label.text() == "準備完了"


def test_main_window_ignores_preview_touch_when_controller_does_not_support_touch(
    window: MainWindow,
) -> None:
    controller = FakeControllerOutputPort()
    window.virtual_controller.model.set_controller(controller)
    window.touch_panel_checkbox.setChecked(True)

    window.preview_pane.touch_down_requested.emit(10, 20)
    window.preview_pane.touch_move_requested.emit(11, 21)
    window.preview_pane.touch_up_requested.emit()

    assert controller.events == []


def test_main_window_shows_touch_unsupported_status_on_each_preview_press(
    window: MainWindow,
) -> None:
    window.virtual_controller.model.set_controller(FakeControllerOutputPort())
    window.touch_panel_checkbox.setChecked(True)

    window.preview_pane.touch_down_requested.emit(10, 20)
    assert window.status_label.text() == "現在のプロトコルは 3DS タッチ入力に対応していません"
    window.status_label.setText("別メッセージ")
    window.preview_pane.touch_down_requested.emit(11, 21)

    assert window.status_label.text() == "現在のプロトコルは 3DS タッチ入力に対応していません"


def test_main_window_keeps_touch_panel_checkbox_enabled_for_non_touch_protocol(
    window: MainWindow,
) -> None:
    window.virtual_controller.model.set_controller(FakeControllerOutputPort())

    assert window.touch_panel_checkbox.isEnabled()
    window.touch_panel_checkbox.setChecked(True)

    assert window.touch_panel_checkbox.isChecked()


def test_main_window_applies_saved_window_size_preset(qtbot, services: FakeServices):
    services.global_settings.set("gui.window_size_preset", "hd")

    w = MainWindow(services=services)
    qtbot.addWidget(w)

    assert w.current_window_size_preset_key == "hd"
    assert w.minimumWidth() == 1280
    assert w.maximumWidth() == 1280
    assert w.minimumHeight() == 720
    assert w.maximumHeight() == 720
    w.preview_pane.timer.stop()


def test_window_size_menu_updates_settings(window: MainWindow, services: FakeServices):
    window.window_size_actions["wqhd"].trigger()

    assert services.global_settings.get("gui.window_size_preset") == "wqhd"
    assert window.current_window_size_preset_key == "wqhd"


def test_run_button_enabled_on_selection(window: MainWindow):
    select_macro(window)
    assert window.control_pane.run_btn.isEnabled()


def test_macro_search_is_not_rendered_in_initial_layout(window: MainWindow):
    assert not hasattr(window.macro_browser, "search_box")
    assert window.macro_browser.stack.currentWidget() is window.macro_browser.explorer_tree


def test_connection_status_is_not_rendered_in_macro_explorer(window: MainWindow):
    macro_panel_text = " ".join(
        item.text()
        for item in window.macro_browser.findChildren(type(window.macro_browser.reload_button))
    )
    assert "シリアル" not in macro_panel_text
    assert "映像" not in macro_panel_text


def test_status_bar_displays_capture_and_serial_state(qtbot, services: FakeServices):
    services.global_settings.set("capture_device", "Camera1")
    services.global_settings.set("controller.serial.device", "COM1")

    w = MainWindow(services=services)
    qtbot.addWidget(w)

    assert w.capture_status_label.text() == "映像: Camera1 接続中"
    assert w.serial_status_label.text() == "シリアル: USB Serial Device (COM1) 接続中"
    w.preview_pane.timer.stop()


def test_status_bar_does_not_mark_missing_saved_devices_as_connected(qtbot, services: FakeServices):
    services.global_settings.set("capture_device", "Missing Camera")
    services.global_settings.set("controller.serial.device", "COM9")

    w = MainWindow(services=services)
    qtbot.addWidget(w)

    assert w.capture_status_label.text() == "映像: Missing Camera 未検出 (ダミーデバイス使用中)"
    assert w.serial_status_label.text() == "シリアル: COM9 未検出 (ダミーデバイス使用中)"
    w.preview_pane.timer.stop()


def test_status_bar_resolves_window_status_by_title_when_identifier_is_stale(
    qtbot, services: FakeServices
):
    services.global_settings.set("capture_source_type", "window")
    services.global_settings.set("capture_window_title", "Viewer")
    services.global_settings.set("capture_window_identifier", "stale-hwnd")

    w = MainWindow(services=services)
    qtbot.addWidget(w)

    assert w.capture_status_label.text() == "映像: Viewer 接続中"
    w.preview_pane.timer.stop()


def test_status_bar_displays_capture_profile_state(qtbot, services: FakeServices):
    services.global_settings.set("capture_source_type", "capture")
    services.global_settings.set("controller.serial.device", "COM1")

    w = MainWindow(services=services)
    qtbot.addWidget(w)

    assert w.capture_status_label.text() == "映像: キャプチャ (N3DSXL) 接続中"
    assert w.serial_status_label.text() == "シリアル: USB Serial Device (COM1) 接続中"
    w.preview_pane.timer.stop()


def test_layout_horizontal_surplus_is_side_panel_width(window: MainWindow):
    window.apply_window_size_preset("hd")

    assert window.left_center_container.maximumWidth() == 1016
    assert window.left_center_container.layout().columnMinimumWidth(0) == 240
    assert window.left_center_container.layout().columnMinimumWidth(1) == 768
    assert window.preview_pane.maximumWidth() == 768
    assert window.tool_log_pane.maximumWidth() == 240
    assert window.centralWidget().layout().spacing() == 8


def test_bottom_macro_log_does_not_span_under_controller(window: MainWindow):
    window.apply_window_size_preset("full_hd")

    assert window.macro_log_pane.parent() is window.left_center_container
    assert window.macro_log_pane.maximumWidth() == 1280
    margins = window.macro_log_pane.layout().contentsMargins()
    assert (margins.left(), margins.right()) == (0, 0)
    assert (
        window.virtual_controller_panel.maximumHeight()
        > window.current_layout_metrics.center_height
    )


def test_controller_pane_has_title_label(window: MainWindow):
    assert window.controller_title_label.text() == "コントローラー"
    assert window.controller_title_label.indent() == LEFT_PANE_CONTENT_MARGIN
    assert window.controller_title_label.font().bold()
    assert window.macro_browser.title_label.font().bold()
    assert window.macro_log_pane.title_label.font().bold()
    assert window.tool_log_pane.title_label.font().bold()
    assert window.macro_log_pane.view.font().fixedPitch()
    assert window.tool_log_pane.view.font().fixedPitch()
    assert window.controller_title_label.height() == window.macro_log_pane.title_label.height()
    assert window.controller_title_label.height() == window.tool_log_pane.title_label.height()


def test_title_bar_actions_are_right_aligned(window: MainWindow):
    assert (
        window.virtual_controller_panel.title_layout.itemAt(0).widget()
        is window.controller_title_label
    )
    assert window.virtual_controller_panel.title_layout.itemAt(1).spacerItem() is not None
    assert (
        window.virtual_controller_panel.title_layout.itemAt(2).widget()
        is window.touch_panel_checkbox
    )

    for pane in (window.macro_log_pane, window.tool_log_pane):
        assert pane.control_layout.itemAt(0).widget() is pane.title_label
        assert pane.control_layout.itemAt(1).spacerItem() is not None
        assert pane.control_layout.itemAt(2).widget() is pane.auto_scroll_checkbox
        assert pane.control_layout.itemAt(3).widget() is pane.debug_checkbox
        assert pane.control_layout.itemAt(4).widget() is pane.clear_button


def test_left_column_content_edges_align(window: MainWindow, qtbot):
    window.show()
    qtbot.waitUntil(lambda: window.macro_browser.explorer_tree.width() > 0, timeout=1000)

    assert window.macro_browser.layout().contentsMargins().left() == LEFT_PANE_CONTENT_MARGIN
    assert window.control_pane.layout().contentsMargins().left() == LEFT_PANE_CONTENT_MARGIN
    macro_left = window.macro_browser.explorer_tree.mapTo(window, QPoint(0, 0)).x()
    macro_right = window.macro_browser.explorer_tree.mapTo(
        window,
        QPoint(window.macro_browser.explorer_tree.width(), 0),
    ).x()
    run_left = window.control_pane.run_btn.mapTo(window, QPoint(0, 0)).x()
    settings_right = window.control_pane.settings_btn.mapTo(
        window,
        QPoint(window.control_pane.settings_btn.width(), 0),
    ).x()
    assert run_left == macro_left
    assert settings_right == macro_right


def test_vertical_surplus_is_allocated_to_lists_and_logs(window: MainWindow):
    window.apply_window_size_preset("full_hd")

    margins = window.centralWidget().layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (10, 0, 10, 0)
    assert window.macro_explorer_panel.minimumHeight() == window.preview_pane.maximumHeight()
    assert window.macro_explorer_panel.maximumHeight() == window.preview_pane.maximumHeight()
    grid = window.left_center_container.layout()
    assert grid.itemAtPosition(1, 0).widget() is window.virtual_controller_panel
    assert grid.itemAtPosition(1, 1).widget() is window.macro_log_pane
    assert (
        window.left_center_container.maximumHeight() > window.current_layout_metrics.center_height
    )
    assert window.macro_log_pane.maximumHeight() > window.current_layout_metrics.center_height
    assert window.tool_log_pane.maximumHeight() > window.current_layout_metrics.center_height
    assert (
        window.macro_explorer_panel.minimumHeight()
        == window.current_layout_metrics.macro_explorer_height
    )
    assert (
        window.macro_log_pane.minimumHeight()
        == window.current_layout_metrics.bottom_macro_log_min_height
    )


def test_main_window_applies_virtual_controller_preset_metrics(window: MainWindow):
    window.apply_window_size_preset("four_k")

    assert window.virtual_controller.maximumWidth() == 538
    assert window.virtual_controller.maximumHeight() == 320
    assert window.virtual_controller.btn_a.width() == 37
    window.virtual_controller_panel.apply_layout_size(538, 420)
    assert window.virtual_controller.maximumHeight() == 420
    assert window.virtual_controller.btn_a.width() > 37

    window.apply_window_size_preset("hd")

    assert window.virtual_controller.maximumWidth() == 240
    assert window.virtual_controller.maximumHeight() == 120
    assert window.virtual_controller.btn_a.width() == 14


def test_virtual_controller_relayouts_after_initial_geometry(qtbot, services: FakeServices):
    services.global_settings.set("gui.window_size_preset", "full_hd")
    w = MainWindow(services=services)
    qtbot.addWidget(w)
    try:
        w.show()

        qtbot.waitUntil(
            lambda: (
                w.virtual_controller.maximumHeight()
                == w.virtual_controller_panel.height() - w.controller_title_label.height()
            ),
            timeout=1000,
        )

        assert w.virtual_controller.maximumWidth() == w.virtual_controller_panel.width()
    finally:
        w.preview_pane.timer.stop()


def test_macro_explorer_footer_disables_settings_while_running(window: MainWindow):
    window.control_pane.set_run_state(RunUiState.RUNNING)

    assert not window.control_pane.settings_btn.isEnabled()


def test_macro_explorer_footer_disables_snapshot_while_running(window: MainWindow):
    window.control_pane.set_run_state(RunUiState.RUNNING)

    assert not window.control_pane.snapshot_btn.isEnabled()


@pytest.mark.parametrize("preset_key", ["hd", "full_hd", "wqhd", "four_k"])
def test_macro_explorer_footer_uses_2x2_grid_for_all_presets(window: MainWindow, preset_key: str):
    window.apply_window_size_preset(preset_key)

    assert window.control_pane._layout.itemAtPosition(0, 0).widget() is window.control_pane.run_btn
    assert (
        window.control_pane._layout.itemAtPosition(0, 1).widget() is window.control_pane.cancel_btn
    )
    assert (
        window.control_pane._layout.itemAtPosition(1, 0).widget()
        is window.control_pane.snapshot_btn
    )
    assert (
        window.control_pane._layout.itemAtPosition(1, 1).widget()
        is window.control_pane.settings_btn
    )
    assert window.control_pane._layout.itemAtPosition(0, 2) is None


def test_macro_explorer_footer_unifies_control_button_height(window: MainWindow):
    buttons = [
        window.control_pane.run_btn,
        window.control_pane.cancel_btn,
        window.control_pane.snapshot_btn,
        window.control_pane.settings_btn,
    ]

    assert {button.minimumHeight() for button in buttons} == {34}
    assert {button.maximumHeight() for button in buttons} == {34}
    assert window.control_pane.run_btn.mainButton.maximumHeight() == 34
    assert window.control_pane.run_btn.dropdownButton.maximumHeight() == 34


def test_main_window_uses_selected_macro_id(qtbot, window: MainWindow, services: FakeServices):
    handle = FakeRunHandle()
    services.builder = FakeBuilder(handle)
    select_macro(window)

    window._start_macro({"count": 1})
    qtbot.waitUntil(lambda: window.run_handle is handle)

    assert window.run_handle is handle
    request = services.builder.start.call_args.args[0]
    assert request.macro_id == "dummy-id"
    assert request.entrypoint == "gui"
    assert request.exec_args == {"count": 1}
    assert window.control_pane.cancel_btn.isEnabled()


def test_main_window_start_logs_start_exception(qtbot, window: MainWindow, services: FakeServices):
    services.builder.start.side_effect = RuntimeError("start failed")
    select_macro(window)

    window._start_macro({"count": 1})
    qtbot.waitUntil(
        lambda: (
            bool(services.logger.technical_events)
            and services.logger.technical_events[-1][3] == "runtime.start_failed"
        )
    )

    assert window.run_handle is None
    assert window.status_label.text() == "エラー: マクロを開始できません"
    assert services.logger.technical_events[-1][3] == "runtime.start_failed"
    assert window.control_pane.run_btn.isEnabled()


def test_macro_start_closes_manual_port_before_runtime(
    qtbot, window: MainWindow, services: FakeServices
):
    handle = FakeRunHandle()
    manual = FakeControllerOutputPort()
    window.virtual_controller.model.set_controller(manual)
    select_macro(window)

    def start(_request):
        assert manual.closed is True
        return handle

    services.builder.start.side_effect = start

    window._start_macro({})
    qtbot.waitUntil(lambda: window.run_handle is handle)

    assert window.run_handle is handle
    assert manual.events == [("release", ()), ("close", None)]
    assert window.virtual_controller.model.controller is None
    assert window.virtual_controller.model.manual_input_enabled is False
    assert services.discarded_manual_controllers == [manual]


def test_macro_start_clears_manual_controller_visual_state(
    qtbot, window: MainWindow, services: FakeServices
):
    handle = FakeRunHandle()
    manual = FakeControllerOutputPort()
    window.virtual_controller.model.set_controller(manual)
    window.virtual_controller.model.pressed_buttons.add(Button.A)
    window.virtual_controller.model.current_hat = Hat.UP
    select_macro(window)
    services.builder.start.return_value = handle

    window._start_macro({})
    qtbot.waitUntil(lambda: window.run_handle is handle)

    assert window.virtual_controller.model.pressed_buttons == set()
    assert window.virtual_controller.model.current_hat == Hat.CENTER


def test_macro_start_discards_builder_cached_manual_controller(
    qtbot, window: MainWindow, services: FakeServices
):
    handle = FakeRunHandle()
    manual = services.builder.manual_controller
    window.virtual_controller.model.set_controller(manual)
    select_macro(window)
    services.builder.start.return_value = handle

    window._start_macro({})
    qtbot.waitUntil(lambda: window.run_handle is handle)

    assert services.discarded_manual_controllers == [manual]
    assert services.builder.manual_controller is not manual


def test_pair_success_sets_manual_controller(window: MainWindow, services: FakeServices):
    services.global_settings.set("controller.backend", "swbt")
    old_manual = FakeControllerOutputPort()
    window.virtual_controller.model.set_controller(old_manual)

    status = window._pair_swbt_controller()

    assert status.connected is True
    assert services.swbt_calls == ["pair"]
    assert old_manual.events == [("release", ()), ("close", None)]
    assert window.virtual_controller.model.controller is services.builder.manual_controller
    assert window.virtual_controller.model.manual_input_enabled is True


def test_reconnect_success_sets_manual_controller(window: MainWindow, services: FakeServices):
    services.global_settings.set("controller.backend", "swbt")

    window._reconnect_swbt_controller()

    assert services.swbt_calls == ["reconnect"]
    assert window.virtual_controller.model.controller is services.builder.manual_controller


def test_disconnect_releases_and_clears_manual_controller(
    window: MainWindow, services: FakeServices
):
    services.global_settings.set("controller.backend", "swbt")
    manual = FakeControllerOutputPort()
    window.virtual_controller.model.set_controller(manual)

    window._disconnect_swbt_controller()

    assert services.swbt_calls == ["disconnect"]
    assert manual.events == [("release", ()), ("close", None)]
    assert window.virtual_controller.model.controller is None


def test_async_disconnect_succeeds_when_detached_controller_close_fails(
    qtbot, window: MainWindow, services: FakeServices
) -> None:
    class FailingCloseController(FakeControllerOutputPort):
        def close(self) -> None:
            self.events.append(("close", None))
            raise RuntimeError("manual close failed")

    services.global_settings.set("controller.backend", "swbt")
    manual = FailingCloseController()
    window.virtual_controller.model.set_controller(manual)
    succeeded: list[object] = []
    failed: list[BaseException] = []

    window._disconnect_swbt_controller_async(succeeded.append, failed.append)

    qtbot.waitUntil(lambda: succeeded == [None])
    assert failed == []
    assert services.swbt_calls == ["disconnect"]
    assert manual.events == [("release", ()), ("close", None)]
    assert window.virtual_controller.model.controller is None
    assert window.status_label.text() == "swbt を切断しました"
    assert services.logger.technical_events[-1][0] == "WARNING"
    assert services.logger.technical_events[-1][3] == "swbt.manual_controller_release_retried"
    assert isinstance(services.logger.technical_events[-1][5], RuntimeError)


def test_async_disconnect_groups_controller_and_factory_failures(
    qtbot, window: MainWindow, services: FakeServices
) -> None:
    class FailingCloseController(FakeControllerOutputPort):
        def close(self) -> None:
            raise RuntimeError("manual close failed")

    def fail_disconnect() -> None:
        services.swbt_calls.append("disconnect")
        raise RuntimeError("factory disconnect failed")

    services.global_settings.set("controller.backend", "swbt")
    services.disconnect_swbt = fail_disconnect
    window.virtual_controller.model.set_controller(FailingCloseController())
    succeeded: list[object] = []
    failed: list[BaseException] = []

    window._disconnect_swbt_controller_async(succeeded.append, failed.append)

    qtbot.waitUntil(lambda: bool(failed))
    assert succeeded == []
    assert services.swbt_calls == ["disconnect"]
    assert isinstance(failed[0], ExceptionGroup)
    assert [str(error) for error in failed[0].exceptions] == [
        "manual close failed",
        "factory disconnect failed",
    ]
    assert window._swbt_lifecycle_busy is False
    assert window.status_label.text() == "エラー: swbt を切断できません"
    assert services.logger.technical_events[-1][3] == "swbt.lifecycle_failed"


def test_runtime_finish_does_not_auto_reconnect(window: MainWindow, services: FakeServices):
    services.global_settings.set("controller.backend", "swbt")
    window.virtual_controller.set_manual_input_enabled(False)

    window.on_finished("完了")

    assert services.swbt_calls == []
    assert window.virtual_controller.model.manual_input_enabled is False


def test_pair_and_close_wait_for_background_operation(qtbot, services: FakeServices) -> None:
    started = Event()
    release = Event()

    def pair():
        started.set()
        release.wait(2.0)
        return SimpleNamespace(
            connected=True,
            controller_type="pro-controller",
            adapter="hci0",
            message="connected",
        )

    services.pair_swbt = pair
    services.global_settings.set("controller.backend", "swbt")
    services.global_settings.set("controller.swbt.adapter", "hci0")
    window = MainWindow(services=services)
    qtbot.addWidget(window)
    window.deferred_init()

    window._pair_swbt_controller_async()
    qtbot.waitUntil(started.is_set)
    assert window._swbt_lifecycle_busy is True

    close_event = QCloseEvent()
    window.closeEvent(close_event)
    assert close_event.isAccepted() is False
    assert services.closed is False

    release.set()
    qtbot.waitUntil(lambda: services.closed)


def test_manual_send_failure_is_visible_and_closes_port_in_worker(
    qtbot, window: MainWindow
) -> None:
    class FailingController(FakeControllerOutputPort):
        def press(self, keys) -> None:
            raise RuntimeError("link lost")

    controller = FailingController()
    window.virtual_controller.model.set_controller(controller)
    window._sync_manual_input_state()

    window.virtual_controller.model.button_press(Button.A)

    assert window.virtual_controller.model.controller is None
    assert window.virtual_controller.model.manual_input_enabled is False
    assert "Reconnect" in window.status_label.text()
    qtbot.waitUntil(lambda: controller.closed)


def test_serial_manual_controller_is_restored_after_run(qtbot, window: MainWindow, services):
    manual = services.builder.manual_controller
    window.virtual_controller.model.set_controller(None)
    window.run_handle = FakeRunHandle(run_result(RunStatus.SUCCESS), done=True)

    window._poll_run_handle()

    qtbot.waitUntil(lambda: window.virtual_controller.model.controller is manual)
    assert window.virtual_controller.model.manual_input_enabled is True


def test_swbt_manual_controller_is_restored_after_cancelled_run(
    qtbot, window: MainWindow, services: FakeServices
) -> None:
    manual = services.builder.manual_controller
    services.global_settings.set("controller.backend", "swbt")
    window.virtual_controller.model.set_controller(None)
    window.run_handle = FakeRunHandle(run_result(RunStatus.CANCELLED), done=True)

    window._poll_run_handle()

    qtbot.waitUntil(lambda: window.virtual_controller.model.controller is manual)
    assert window.virtual_controller.model.manual_input_enabled is True
    assert window.status_label.text() == "中断"


def test_deferred_settings_failure_still_restores_serial_manual_controller(
    qtbot, window: MainWindow, services: FakeServices
) -> None:
    manual = services.builder.manual_controller

    def fail_flush_deferred_settings():
        raise RuntimeError("deferred apply failed")

    services.flush_deferred_settings = fail_flush_deferred_settings
    window.virtual_controller.model.set_controller(None)
    window.run_handle = FakeRunHandle(run_result(RunStatus.SUCCESS), done=True)

    window._poll_run_handle()

    qtbot.waitUntil(lambda: window.virtual_controller.model.controller is manual)
    assert window.virtual_controller.model.manual_input_enabled is True
    assert window.status_label.text() == ("実行後の設定を反映できません: deferred apply failed")
    assert services.logger.technical_events[-1][3] == "configuration.deferred_apply_failed"


def test_stale_serial_manual_restore_is_discarded_and_closed_in_worker(
    qtbot, window: MainWindow, services: FakeServices
) -> None:
    started = Event()
    release = Event()
    controller = FakeControllerOutputPort()

    class BlockingBuilder:
        manual_controller = controller

        def controller_output_for_manual_input(self):
            started.set()
            release.wait(2.0)
            return controller

    services.builder = BlockingBuilder()
    window.virtual_controller.model.set_controller(None)

    window._restore_manual_controller()
    qtbot.waitUntil(started.is_set)
    assert window._manual_controller_restoring is True

    window._apply_connection_settings({"controller.backend": "swbt"})
    assert services.global_settings.get("controller.backend") == "serial"
    assert "変更できません" in window.status_label.text()

    services.global_settings.set("controller.backend", "swbt")
    release.set()

    qtbot.waitUntil(lambda: controller.closed)
    assert services.discarded_manual_controllers == [controller]
    assert controller.events == [("release", ()), ("close", None)]
    assert window.virtual_controller.model.controller is None
    assert window._manual_controller_restoring is False


def test_swbt_lifecycle_rejected_while_macro_running(window: MainWindow, services: FakeServices):
    services.global_settings.set("controller.backend", "swbt")
    window.run_handle = FakeRunHandle(done=False)

    with pytest.raises(RuntimeError):
        window._pair_swbt_controller()

    assert services.swbt_calls == []


def test_execute_macro_with_params_logs_parse_exception(
    window: MainWindow, services: FakeServices, monkeypatch
):
    class FakeParamEdit:
        def text(self):
            return "broken"

    class FakeDialog:
        def __init__(self, parent):
            self.param_edit = FakeParamEdit()

        def exec(self):
            return QDialog.Accepted

    def fail_parse(params):
        raise ValueError("invalid params")

    monkeypatch.setattr("nyxpy.gui.main_window.MacroParamsDialog", FakeDialog)
    monkeypatch.setattr("nyxpy.gui.main_window.parse_define_args", fail_parse)
    select_macro(window)

    window.execute_macro_with_params()

    assert window.status_label.text() == "パラメータを解析できません"
    assert services.logger.technical_events[-1][3] == "macro.params_invalid"
    services.builder.start.assert_not_called()


def test_main_window_cancel_enters_cancelling_state(window: MainWindow):
    handle = FakeRunHandle(done=False)
    window.run_handle = handle
    select_macro(window)
    window.control_pane.set_run_state(RunUiState.RUNNING)

    window.cancel_macro()

    assert handle.cancelled is True
    assert window.status_label.text() == "中断要求中"
    assert not window.control_pane.run_btn.isEnabled()
    assert not window.control_pane.cancel_btn.isEnabled()


def test_main_window_poll_updates_status_from_run_result(window: MainWindow):
    window.run_handle = FakeRunHandle(run_result(RunStatus.SUCCESS), done=True)
    select_macro(window)
    window.control_pane.set_run_state(RunUiState.RUNNING)

    window._poll_run_handle()

    assert window.status_label.text() == "完了"
    assert window.run_handle is None
    assert window.last_run_result.status is RunStatus.SUCCESS
    assert window.control_pane.run_btn.isEnabled()


def test_main_window_poll_logs_result_exception(window: MainWindow, services: FakeServices):
    window.run_handle = FakeRunHandle(done=True)
    window.on_finished = lambda status: window.status_label.setText(status)

    window._poll_run_handle()

    assert window.status_label.text() == "エラー: 実行結果を取得できません"
    assert services.logger.technical_events
    assert services.logger.technical_events[-1][3] == "runtime.result_failed"


@pytest.mark.parametrize(
    ("result", "expected_status"),
    [
        (run_result(RunStatus.CANCELLED), "中断"),
        (run_result(RunStatus.FAILED, "fail"), "エラー: fail"),
    ],
)
def test_main_window_formats_non_success_run_results(
    window: MainWindow, result: RunResult, expected_status: str
):
    assert window._format_run_result(result) == expected_status


def test_apply_settings_defers_builder_swap_during_run(window: MainWindow, services: FakeServices):
    window.run_handle = FakeRunHandle(done=False)
    services.next_apply_outcome = SettingsApplyOutcome(
        changed_keys=frozenset({"capture_device"}),
        builder_replaced=False,
        frame_source_changed=False,
        preview_frame_source=None,
        manual_controller=None,
        deferred=True,
    )

    window.apply_app_settings()

    assert services.apply_calls[-1] is True
    assert window.status_label.text() == "設定変更は実行完了後に反映されます"


def test_apply_settings_logs_apply_exception(window: MainWindow, services: FakeServices):
    def fail_apply(*, is_run_active: bool = False):
        services.apply_calls.append(is_run_active)
        raise RuntimeError("settings failed")

    services.apply_settings = fail_apply

    window.apply_app_settings()

    assert window.status_label.text() == "設定を反映できません: settings failed"
    assert services.logger.technical_events[-1][3] == "configuration.apply_failed"


def test_apply_settings_pauses_only_for_active_capture_change(
    window: MainWindow, services: FakeServices
):
    frame_source = object()
    services.next_apply_outcome = SettingsApplyOutcome(
        changed_keys=frozenset({"capture_device"}),
        builder_replaced=True,
        frame_source_changed=True,
        preview_frame_source=frame_source,
        manual_controller=None,
    )
    window.preview_pane.pause = MagicMock()
    window.preview_pane.set_frame_source = MagicMock()
    window.preview_pane.resume = MagicMock()
    window.virtual_controller.model.set_controller = MagicMock()

    window.apply_app_settings()

    window.preview_pane.pause.assert_called_once_with()
    window.preview_pane.set_frame_source.assert_called_once_with(frame_source)
    window.preview_pane.resume.assert_called_once_with()
    window.virtual_controller.model.set_controller.assert_not_called()


def test_apply_settings_updates_ports_without_pause_when_capture_unchanged(
    window: MainWindow, services: FakeServices
):
    services.next_apply_outcome = SettingsApplyOutcome(
        changed_keys=frozenset({"controller.serial.device"}),
        builder_replaced=True,
        frame_source_changed=False,
        preview_frame_source=None,
        manual_controller=object(),
    )
    window.preview_pane.pause = MagicMock()
    window.preview_pane.set_frame_source = MagicMock()
    window.preview_pane.resume = MagicMock()

    window.apply_app_settings()

    window.preview_pane.set_frame_source.assert_not_called()
    window.preview_pane.pause.assert_not_called()
    window.preview_pane.resume.assert_not_called()


def test_apply_settings_reports_preview_connection_failure(
    window: MainWindow, services: FakeServices
):
    error = RuntimeError("window capture failed to start")
    services.next_apply_outcome = SettingsApplyOutcome(
        changed_keys=frozenset({"capture_window_title"}),
        builder_replaced=True,
        frame_source_changed=True,
        preview_frame_source=None,
        manual_controller=None,
        preview_error=error,
    )
    window.preview_pane.pause = MagicMock()
    window.preview_pane.set_frame_source = MagicMock()
    window.preview_pane.resume = MagicMock()

    window.apply_app_settings()

    window.preview_pane.pause.assert_called_once_with()
    window.preview_pane.set_frame_source.assert_called_once_with(None)
    window.preview_pane.resume.assert_not_called()
    assert window.capture_status_label.text() == "映像: 接続失敗 (window capture failed to start)"


def test_apply_settings_reports_manual_controller_failure(
    window: MainWindow, services: FakeServices
):
    error = RuntimeError("serial device not found")
    services.next_apply_outcome = SettingsApplyOutcome(
        changed_keys=frozenset({"controller.serial.device"}),
        builder_replaced=True,
        frame_source_changed=False,
        preview_frame_source=object(),
        manual_controller=None,
        manual_controller_error=error,
    )
    window.virtual_controller.model.set_controller = MagicMock()

    window.apply_app_settings()

    window.virtual_controller.model.set_controller.assert_called_once_with(None)
    assert window.serial_status_label.text() == "シリアル: 接続失敗 (serial device not found)"


def test_close_cancels_and_waits_with_configured_timeout(
    window: MainWindow, services: FakeServices
):
    handle = FakeRunHandle(done=False)
    window.run_handle = handle

    window.closeEvent(QCloseEvent())

    assert handle.cancelled is True
    assert handle.wait_called_with == 1.25
    assert services.closed is True
    assert services.logging.closed is True


def test_gui_does_not_import_removed_runtime_apis():
    source = (Path("src") / "nyxpy" / "gui" / "main_window.py").read_text(encoding="utf-8")

    assert "MacroExecutor" not in source
    assert "DefaultCommand" not in source
    assert "LogManager" not in source
    assert "set_running" not in source
