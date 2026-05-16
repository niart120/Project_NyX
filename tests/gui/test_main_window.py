from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog

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
            "serial_device": "",
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


class FakeBuilder:
    def __init__(self, handle=None) -> None:
        self.handle = handle
        self.start = MagicMock(return_value=handle)


class FakeServices:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = Path.cwd() if project_root is None else project_root
        self.logger = RecordingLogger()
        self.logging = FakeLogging(self.logger)
        self.global_settings = FakeSettings()
        self.secrets_settings = FakeSecrets()
        self.device_discovery = object()
        self.macro_catalog = FakeCatalog()
        self.builder = FakeBuilder()
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


def test_initial_ui_state(window: MainWindow):
    assert window.macro_browser.table.rowCount() == 1
    assert window.macro_browser.table.item(0, 0).text() == "Dummy Macro"
    assert window.status_label.text() == "準備完了"
    assert window.touch_panel_checkbox.text() == "タッチパネル"
    assert not window.touch_panel_checkbox.isChecked()
    assert not window.control_pane.run_btn.isEnabled()
    assert not window.control_pane.cancel_btn.isEnabled()
    assert window.control_pane.snapshot_btn.isEnabled()


def test_main_window_wires_preview_touch_to_virtual_controller_model(window: MainWindow) -> None:
    controller = FakeFullCapabilityController()
    window.virtual_controller.model.set_controller(controller)
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
    window.macro_browser.table.selectRow(0)
    assert window.control_pane.run_btn.isEnabled()


def test_macro_search_is_not_rendered_in_initial_layout(window: MainWindow):
    assert not hasattr(window.macro_browser, "search_box")


def test_connection_status_is_not_rendered_in_macro_explorer(window: MainWindow):
    macro_panel_text = " ".join(
        item.text()
        for item in window.macro_browser.findChildren(type(window.macro_browser.reload_button))
    )
    assert "シリアル" not in macro_panel_text
    assert "映像" not in macro_panel_text


def test_status_bar_displays_capture_and_serial_state(qtbot, services: FakeServices):
    services.global_settings.set("capture_device", "USB Video Device")
    services.global_settings.set("serial_device", "COM6")

    w = MainWindow(services=services)
    qtbot.addWidget(w)

    assert w.capture_status_label.text() == "映像: USB Video Device 接続中"
    assert w.serial_status_label.text() == "シリアル: COM6 接続中"
    w.preview_pane.timer.stop()


def test_layout_horizontal_surplus_is_side_panel_width(window: MainWindow):
    window.apply_window_size_preset("hd")

    assert window.left_center_container.maximumWidth() == 952
    assert window.left_center_container.layout().columnMinimumWidth(0) == 304
    assert window.left_center_container.layout().columnMinimumWidth(1) == 640
    assert window.preview_pane.maximumWidth() == 640
    assert window.tool_log_pane.maximumWidth() == 304
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


def test_left_column_content_edges_align(window: MainWindow, qtbot):
    window.show()
    qtbot.waitUntil(lambda: window.macro_browser.table.width() > 0, timeout=1000)

    assert window.macro_browser.layout().contentsMargins().left() == LEFT_PANE_CONTENT_MARGIN
    assert window.control_pane.layout().contentsMargins().left() == LEFT_PANE_CONTENT_MARGIN
    assert (
        window.control_pane.run_btn.geometry().left()
        == window.macro_browser.table.geometry().left()
    )
    assert (
        window.control_pane.settings_btn.geometry().right()
        == window.macro_browser.table.geometry().right()
    )


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

    assert window.virtual_controller.maximumWidth() == 304
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


def test_main_window_uses_selected_macro_id(window: MainWindow, services: FakeServices):
    handle = FakeRunHandle()
    services.builder = FakeBuilder(handle)
    window.macro_browser.table.selectRow(0)

    window._start_macro({"count": 1})

    assert window.run_handle is handle
    request = services.builder.start.call_args.args[0]
    assert request.macro_id == "dummy-id"
    assert request.entrypoint == "gui"
    assert request.exec_args == {"count": 1}
    assert window.control_pane.cancel_btn.isEnabled()


def test_main_window_start_logs_start_exception(window: MainWindow, services: FakeServices):
    services.builder.start.side_effect = RuntimeError("start failed")
    window.macro_browser.table.selectRow(0)

    window._start_macro({"count": 1})

    assert window.run_handle is None
    assert window.status_label.text() == "エラー: マクロを開始できません"
    assert services.logger.technical_events[-1][3] == "runtime.start_failed"
    assert window.control_pane.run_btn.isEnabled()


def test_execute_macro_with_params_logs_parse_exception(
    window: MainWindow, services: FakeServices, monkeypatch
):
    class FakeParamEdit:
        def text(self):
            return "broken"

    class FakeDialog:
        def __init__(self, parent, macro_name):
            self.param_edit = FakeParamEdit()

        def exec(self):
            return QDialog.Accepted

    def fail_parse(params):
        raise ValueError("invalid params")

    monkeypatch.setattr("nyxpy.gui.main_window.MacroParamsDialog", FakeDialog)
    monkeypatch.setattr("nyxpy.gui.main_window.parse_define_args", fail_parse)
    window.macro_browser.table.selectRow(0)

    window.execute_macro_with_params()

    assert window.status_label.text() == "パラメータを解析できません"
    assert services.logger.technical_events[-1][3] == "macro.params_invalid"
    services.builder.start.assert_not_called()


def test_main_window_cancel_enters_cancelling_state(window: MainWindow):
    handle = FakeRunHandle(done=False)
    window.run_handle = handle
    window.macro_browser.table.selectRow(0)
    window.control_pane.set_run_state(RunUiState.RUNNING)

    window.cancel_macro()

    assert handle.cancelled is True
    assert window.status_label.text() == "中断要求中"
    assert not window.control_pane.run_btn.isEnabled()
    assert not window.control_pane.cancel_btn.isEnabled()


def test_main_window_poll_updates_status_from_run_result(window: MainWindow):
    window.run_handle = FakeRunHandle(run_result(RunStatus.SUCCESS), done=True)
    window.macro_browser.table.selectRow(0)
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
    controller = object()
    services.next_apply_outcome = SettingsApplyOutcome(
        changed_keys=frozenset({"capture_device"}),
        builder_replaced=True,
        frame_source_changed=True,
        preview_frame_source=frame_source,
        manual_controller=controller,
    )
    window.preview_pane.pause = MagicMock()
    window.preview_pane.set_frame_source = MagicMock()
    window.preview_pane.resume = MagicMock()
    window.virtual_controller.model.set_controller = MagicMock()

    window.apply_app_settings()

    window.preview_pane.pause.assert_called_once_with()
    window.preview_pane.set_frame_source.assert_called_once_with(frame_source)
    window.preview_pane.resume.assert_called_once_with()
    window.virtual_controller.model.set_controller.assert_called_once_with(controller)


def test_apply_settings_updates_ports_without_pause_when_capture_unchanged(
    window: MainWindow, services: FakeServices
):
    services.next_apply_outcome = SettingsApplyOutcome(
        changed_keys=frozenset({"serial_device"}),
        builder_replaced=True,
        frame_source_changed=False,
        preview_frame_source=object(),
        manual_controller=object(),
    )
    window.preview_pane.pause = MagicMock()
    window.preview_pane.resume = MagicMock()

    window.apply_app_settings()

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
        manual_controller=object(),
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
        changed_keys=frozenset({"serial_device"}),
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
