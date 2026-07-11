from threading import Event

import pytest
from PySide6.QtWidgets import QFormLayout, QLabel

from nyxpy.framework.core.hardware.capture_source import CaptureRect
from nyxpy.framework.core.hardware.device_discovery import DeviceInfo
from nyxpy.framework.core.hardware.swbt.discovery import SwbtAdapterView
from nyxpy.framework.core.hardware.window_discovery import WindowInfo
from nyxpy.gui.dialogs.settings.device_tab import DeviceSettingsTab


class FakeSettings:
    def __init__(self):
        self.data = {
            "capture_device": "Camera1",
            "capture_source_type": "camera",
            "capture_window_title": "",
            "capture_window_match_mode": "exact",
            "capture_window_identifier": "",
            "capture_backend": "auto",
            "capture_fps": None,
            "capture_aspect_box_enabled": False,
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
            "preview_fps": 60,
            "controller.backend": "serial",
            "controller.serial.device": "COM1",
            "controller.serial.protocol": "CH552",
            "controller.serial.baudrate": 9600,
            "controller.swbt.controller_type": "pro-controller",
            "controller.swbt.adapter": None,
            "controller.swbt.key_store_path": None,
            "gui.window_size_preset": "full_hd",
        }

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class FakeDiscovery:
    def detect(self, timeout_sec=2.0):
        return self

    @property
    def serial_devices(self):
        return (DeviceInfo(kind="serial", name="USB Serial Device (COM1)", identifier="COM1"),)

    def capture_names(self):
        return ["Camera1"]

    def serial_names(self):
        return ["COM1"]

    def detect_window_sources(self, timeout_sec=2.0):
        return (WindowInfo("Viewer", "hwnd-1", CaptureRect(10, 20, 600, 720)),)


class EmptyDiscovery:
    def detect(self, timeout_sec=2.0):
        return self

    @property
    def serial_devices(self):
        return ()

    def capture_names(self):
        return []

    def detect_window_sources(self, timeout_sec=2.0):
        return ()


class FakeSwbtAdapterProvider:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> tuple[SwbtAdapterView, ...]:
        self.calls += 1
        return (
            SwbtAdapterView(
                name="hci0",
                aliases=("usb-1",),
                display_name="hci0 - Nintendo Adapter",
                vendor_id=0x057E,
                product_id=0x2009,
                manufacturer="Nintendo",
                product="Adapter",
                serial_number=None,
                bus_number=1,
                device_address=2,
                port_numbers=(1,),
                is_bluetooth_hci=True,
            ),
        )


@pytest.fixture(autouse=True)
def _default_ponkan_available(monkeypatch):
    monkeypatch.setattr(
        "nyxpy.gui.dialogs.settings.device_tab.is_ponkan_capture_available",
        lambda: True,
    )


def test_device_tab_protocol_options_include_3ds(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    options = [tab.ser_protocol.itemText(i) for i in range(tab.ser_protocol.count())]
    assert "3DS" in options


def test_device_tab_uses_consistent_controller_terms(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    labels = set(_label_texts(tab.controller_group))

    assert tab.ser_group.title() == "serial"
    assert tab.swbt_group.title() == "swbt"
    assert [
        tab.controller_backend.itemText(index) for index in range(tab.controller_backend.count())
    ] == ["serial", "swbt"]
    assert labels >= {
        "方式:",
        "デバイス:",
        "プロトコル:",
        "ボーレート:",
        "タイプ:",
        "キーストア:",
        "接続:",
        "状態:",
    }
    assert labels.isdisjoint(
        {
            "Backend:",
            "Device:",
            "Protocol:",
            "Baud Rate:",
            "Controller:",
            "Adapter:",
            "Key Store:",
            "Connection:",
            "Status:",
        }
    )


def test_device_tab_orders_swbt_fields_like_controller_menu(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    form = tab.swbt_group.layout().itemAt(0).layout()

    assert isinstance(form, QFormLayout)
    assert [
        form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget().text()
        for row in range(form.rowCount())
    ] == ["デバイス:", "タイプ:", "キーストア:", "接続:", "状態:"]


def test_device_tab_selects_3ds_default_baudrate(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    tab.ser_protocol.setCurrentText("3DS")

    assert tab.ser_baud.currentText() == "115200"


def test_device_settings_tab_shows_simple_capture_option_when_ponkan_available(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert [
        tab.capture_source_type.itemData(i) for i in range(tab.capture_source_type.count())
    ] == [
        "camera",
        "window",
        "capture",
    ]
    assert [
        tab.capture_source_type.itemText(i) for i in range(tab.capture_source_type.count())
    ] == [
        "カメラ",
        "ウィンドウ",
        "キャプチャ",
    ]


def test_device_settings_tab_hides_capture_option_when_ponkan_unavailable(qtbot):
    settings = FakeSettings()
    settings.data["capture_source_type"] = "capture"
    tab = DeviceSettingsTab(
        settings,
        None,
        device_discovery=FakeDiscovery(),
        ponkan_capture_available=False,
    )
    qtbot.addWidget(tab)

    assert [
        tab.capture_source_type.itemData(i) for i in range(tab.capture_source_type.count())
    ] == [
        "camera",
        "window",
    ]
    assert tab.capture_source_type.currentData() == "camera"


def test_device_settings_tab_applies_window_capture_settings(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    _set_capture_source(tab, "window")
    tab.window_source.setCurrentIndex(0)
    tab.window_match_mode.setCurrentText("contains")
    tab.capture_backend.setCurrentText("mss")
    tab.apply()

    assert settings.data["capture_source_type"] == "window"
    assert settings.data["capture_window_title"] == "Viewer"
    assert settings.data["capture_window_identifier"] == "hwnd-1"
    assert settings.data["capture_window_match_mode"] == "contains"
    assert settings.data["capture_backend"] == "mss"


def test_device_settings_tab_uses_framework_window_candidates_in_combo(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    data = tab.window_source.itemData(0)

    assert tab.window_source.isEditable()
    assert tab.window_source.itemText(0) == "Viewer"
    assert data == {"title": "Viewer", "identifier": "hwnd-1"}


def test_device_settings_tab_saves_custom_window_title_without_identifier(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    _set_capture_source(tab, "window")
    tab.window_source.setEditText("View")
    tab.window_match_mode.setCurrentText("contains")
    tab.apply()

    assert settings.data["capture_window_title"] == "View"
    assert settings.data["capture_window_identifier"] == ""
    assert settings.data["capture_window_match_mode"] == "contains"


def test_device_settings_tab_places_letterbox_on_source_row(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert tab.aspect_box_enabled.parent() is tab.source_row
    assert "Aspect Box:" not in _label_texts(tab.cap_group)

    tab.aspect_box_enabled.setChecked(True)
    tab.apply()

    assert settings.data["capture_aspect_box_enabled"] is True


def test_device_settings_tab_shows_only_hd_aspect_for_capture(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)
    advanced_labels = {
        "Capture Provider:",
        "Device Profile:",
        "Ponkan Backend:",
        "Raw Slots:",
        "Output Queue Size:",
        "Drop Policy:",
        "Poll Interval:",
        "Read Timeout:",
        "Collect Timing:",
    }

    assert not tab.cap_device.isHidden()
    assert tab.window_row.isHidden()
    assert advanced_labels.isdisjoint(_label_texts(tab.cap_group))

    _set_capture_source(tab, "window")
    assert tab.camera_row.isHidden()
    assert not tab.window_row.isHidden()
    assert not tab.window_match_mode.isHidden()
    assert not tab.capture_backend.isHidden()
    assert tab.n3dsxl_hd_aspect_box_enabled.isHidden()

    _set_capture_source(tab, "camera")
    assert not tab.cap_device.isHidden()
    assert tab.window_row.isHidden()
    assert tab.n3dsxl_hd_aspect_box_enabled.isHidden()

    _set_capture_source(tab, "capture")
    assert tab.camera_row.isHidden()
    assert tab.window_row.isHidden()
    assert tab.window_match_mode.isHidden()
    assert tab.capture_backend.isHidden()
    assert tab.capture_fps.isHidden()
    assert tab.aspect_box_enabled.isHidden()
    assert not tab.n3dsxl_hd_aspect_box_enabled.isHidden()
    assert not tab.n3dsxl_hd_aspect_box_enabled_label.isHidden()
    assert advanced_labels.isdisjoint(_label_texts(tab.cap_group))


def test_device_settings_tab_applies_fixed_ponkan_capture_settings(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    _set_capture_source(tab, "capture")
    tab.n3dsxl_hd_aspect_box_enabled.setChecked(False)
    tab.apply()

    assert settings.data["capture_source_type"] == "capture"
    assert settings.data["capture_provider"] == "ponkan"
    assert settings.data["capture_device_profile"] == "n3dsxl"
    assert settings.data["n3dsxl_hd_aspect_box_enabled"] is False


def test_device_settings_tab_does_not_overwrite_hidden_ponkan_settings(qtbot):
    settings = FakeSettings()
    settings.data["ponkan_backend"] = "d3xx-native"
    settings.data["ponkan_raw_slots"] = 3
    settings.data["ponkan_output_queue_size"] = 4
    settings.data["ponkan_drop_policy"] = "block"
    settings.data["ponkan_poll_interval"] = 0.01
    settings.data["ponkan_read_timeout"] = 0.5
    settings.data["ponkan_collect_timing"] = True
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    _set_capture_source(tab, "capture")
    tab.apply()

    assert settings.data["ponkan_backend"] == "d3xx-native"
    assert settings.data["ponkan_raw_slots"] == 3
    assert settings.data["ponkan_output_queue_size"] == 4
    assert settings.data["ponkan_drop_policy"] == "block"
    assert settings.data["ponkan_poll_interval"] == 0.01
    assert settings.data["ponkan_read_timeout"] == 0.5
    assert settings.data["ponkan_collect_timing"] is True


def test_device_settings_tab_preserves_inactive_source_settings_for_capture(qtbot):
    settings = FakeSettings()
    settings.data["capture_device"] = "Camera1"
    settings.data["capture_window_title"] = "Viewer"
    settings.data["capture_window_identifier"] = "hwnd-1"
    settings.data["capture_backend"] = "mss"
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    _set_capture_source(tab, "capture")
    tab.cap_device.clear()
    tab.window_source.setEditText("")
    tab.apply()

    assert settings.data["capture_device"] == "Camera1"
    assert settings.data["capture_window_title"] == "Viewer"
    assert settings.data["capture_window_identifier"] == "hwnd-1"
    assert settings.data["capture_backend"] == "mss"


def test_device_settings_tab_saves_serial_identifier(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert tab.ser_device.currentText() == "USB Serial Device (COM1)"
    tab.apply()

    assert settings.data["controller.serial.device"] == "COM1"


def test_device_tab_switches_serial_and_swbt_field_visibility(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert not tab.ser_group.isHidden()
    assert tab.ser_group.isEnabled()
    assert tab.swbt_group.isHidden()

    tab.controller_backend.setCurrentIndex(tab.controller_backend.findData("swbt"))

    assert tab.ser_group.isHidden()
    assert not tab.swbt_group.isHidden()
    assert tab.swbt_group.isEnabled()


def test_device_tab_uses_supported_controller_models_for_choices(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert [
        tab.swbt_controller_type.itemData(i) for i in range(tab.swbt_controller_type.count())
    ] == ["pro-controller", "joy-con-l", "joy-con-r"]


def test_refresh_adapters_does_not_pair_or_reconnect(qtbot):
    settings = FakeSettings()
    adapter_provider = FakeSwbtAdapterProvider()
    calls: list[str] = []
    tab = DeviceSettingsTab(
        settings,
        None,
        device_discovery=FakeDiscovery(),
        swbt_adapter_provider=adapter_provider,
        swbt_pair=lambda _success, _failure: calls.append("pair"),
        swbt_reconnect=lambda _success, _failure: calls.append("reconnect"),
    )
    qtbot.addWidget(tab)
    settings_before = dict(settings.data)

    qtbot.waitUntil(lambda: adapter_provider.calls == 1 and not tab._swbt_busy)
    tab.refresh_swbt_adapters()
    qtbot.waitUntil(lambda: adapter_provider.calls == 2 and not tab._swbt_busy)

    assert adapter_provider.calls == 2
    assert calls == []
    assert settings.data == settings_before
    assert tab.swbt_adapter.currentIndex() == -1
    assert tab.swbt_adapter.currentText() == ""


def test_device_settings_tab_applies_swbt_settings(qtbot):
    settings = FakeSettings()
    adapter_provider = FakeSwbtAdapterProvider()
    tab = DeviceSettingsTab(
        settings,
        None,
        device_discovery=FakeDiscovery(),
        swbt_adapter_provider=adapter_provider,
    )
    qtbot.addWidget(tab)
    qtbot.waitUntil(lambda: adapter_provider.calls == 1 and not tab._swbt_busy)

    tab.controller_backend.setCurrentIndex(tab.controller_backend.findData("swbt"))
    tab.swbt_controller_type.setCurrentIndex(tab.swbt_controller_type.findData("joy-con-l"))
    tab.swbt_adapter.setCurrentIndex(tab.swbt_adapter.findData("hci0"))
    tab.swbt_key_store.setEditText(".nyxpy/swbt/joy-con-l-bond.json")
    tab.apply()

    assert settings.data["controller.backend"] == "swbt"
    assert settings.data["controller.swbt.controller_type"] == "joy-con-l"
    assert settings.data["controller.swbt.adapter"] == "hci0"
    assert settings.data["controller.swbt.key_store_path"] == ".nyxpy/swbt/joy-con-l-bond.json"


def test_key_store_lists_model_defaults_and_selects_current_model_default(qtbot) -> None:
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert tab.swbt_key_store.currentText() == ".nyxpy/swbt/pro-controller-bond.json"
    assert {tab.swbt_key_store.itemText(index) for index in range(tab.swbt_key_store.count())} >= {
        ".nyxpy/swbt/pro-controller-bond.json",
        ".nyxpy/swbt/joy-con-l-bond.json",
        ".nyxpy/swbt/joy-con-r-bond.json",
    }


def test_key_store_model_change_updates_default_but_preserves_custom_path(qtbot) -> None:
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    tab.swbt_controller_type.setCurrentIndex(tab.swbt_controller_type.findData("joy-con-l"))
    assert tab.swbt_key_store.currentText() == ".nyxpy/swbt/joy-con-l-bond.json"

    tab.swbt_key_store.setEditText("keys/custom.json")
    tab.swbt_controller_type.setCurrentIndex(tab.swbt_controller_type.findData("joy-con-r"))
    assert tab.swbt_key_store.currentText() == "keys/custom.json"


def test_key_store_lists_existing_workspace_json_files(qtbot, tmp_path) -> None:
    class SettingsWithConfigDir(FakeSettings):
        config_dir = tmp_path / ".nyxpy"

    key_store_dir = SettingsWithConfigDir.config_dir / "swbt"
    key_store_dir.mkdir(parents=True)
    (key_store_dir / "paired-switch.json").write_text("{}", encoding="utf-8")
    (key_store_dir / "ignore.txt").write_text("", encoding="utf-8")

    tab = DeviceSettingsTab(SettingsWithConfigDir(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    choices = [tab.swbt_key_store.itemText(index) for index in range(tab.swbt_key_store.count())]
    assert ".nyxpy/swbt/paired-switch.json" in choices
    assert ".nyxpy/swbt/ignore.txt" not in choices


def test_device_tab_preserves_edited_adapter_text(qtbot) -> None:
    settings = FakeSettings()
    provider = FakeSwbtAdapterProvider()
    tab = DeviceSettingsTab(
        settings,
        None,
        device_discovery=FakeDiscovery(),
        swbt_adapter_provider=provider,
    )
    qtbot.addWidget(tab)
    qtbot.waitUntil(lambda: provider.calls == 1 and not tab._swbt_busy)
    tab.controller_backend.setCurrentIndex(tab.controller_backend.findData("swbt"))
    tab.swbt_adapter.setEditText("custom-adapter")

    tab.apply()

    assert settings.data["controller.swbt.adapter"] == "custom-adapter"


def test_pair_status_replaces_alias_with_canonical_adapter(qtbot) -> None:
    settings = FakeSettings()

    def pair(succeeded, _failed) -> None:
        succeeded(
            type(
                "Status",
                (),
                {
                    "connected": True,
                    "message": "connected",
                    "controller_type": "pro-controller",
                    "adapter": "hci0",
                },
            )()
        )

    tab = DeviceSettingsTab(
        settings,
        None,
        device_discovery=FakeDiscovery(),
        swbt_pair=pair,
    )
    qtbot.addWidget(tab)
    tab.controller_backend.setCurrentIndex(tab.controller_backend.findData("swbt"))
    tab.swbt_adapter.setEditText("usb-1")

    tab._pair_swbt()
    tab.apply()

    assert tab.swbt_adapter.currentText() == "hci0"
    assert settings.data["controller.swbt.adapter"] == "hci0"


def test_pair_button_becomes_cancel_and_invokes_pair_cancellation(qtbot) -> None:
    cancelled = Event()
    callbacks = {}

    def pair(_succeeded, failed):
        callbacks["failed"] = failed
        return cancelled.set

    tab = DeviceSettingsTab(
        FakeSettings(),
        None,
        device_discovery=FakeDiscovery(),
        swbt_pair=pair,
    )
    qtbot.addWidget(tab)
    tab.controller_backend.setCurrentIndex(tab.controller_backend.findData("swbt"))
    tab.swbt_adapter.setEditText("usb-1")

    tab.swbt_pair_btn.click()
    assert tab.swbt_pair_btn.text() == "Cancel"
    assert tab.swbt_pair_btn.isEnabled()

    tab.swbt_pair_btn.click()
    assert cancelled.is_set()
    assert tab.swbt_pair_btn.text() == "Cancelling..."
    assert not tab.swbt_pair_btn.isEnabled()

    callbacks["failed"](
        ExceptionGroup(
            "pair cleanup",
            [
                type(
                    "PairCancelled",
                    (RuntimeError,),
                    {"code": "NYX_SWBT_PAIR_CANCELLED"},
                )()
            ],
        )
    )

    assert tab.swbt_status_label.text() == "ペアリングをキャンセルしました"
    assert tab.swbt_pair_btn.text() == "Pair"


def test_reconnect_button_becomes_cancel_and_restores_after_nested_cancellation(qtbot) -> None:
    cancelled = Event()
    callbacks = {}

    def reconnect(_succeeded, failed):
        callbacks["failed"] = failed
        return cancelled.set

    tab = DeviceSettingsTab(
        FakeSettings(),
        None,
        device_discovery=FakeDiscovery(),
        swbt_reconnect=reconnect,
    )
    qtbot.addWidget(tab)
    tab.controller_backend.setCurrentIndex(tab.controller_backend.findData("swbt"))
    tab.swbt_adapter.setEditText("usb-1")

    tab.swbt_reconnect_btn.click()
    assert tab.swbt_reconnect_btn.text() == "Cancel"
    assert tab.swbt_reconnect_btn.isEnabled()
    assert not tab.swbt_pair_btn.isEnabled()

    tab.swbt_reconnect_btn.click()
    assert cancelled.is_set()
    assert tab.swbt_reconnect_btn.text() == "Cancelling..."
    assert not tab.swbt_reconnect_btn.isEnabled()

    callbacks["failed"](
        ExceptionGroup(
            "reconnect cleanup",
            [
                type(
                    "ReconnectCancelled",
                    (RuntimeError,),
                    {"code": "NYX_SWBT_RECONNECT_CANCELLED"},
                )()
            ],
        )
    )

    assert tab.swbt_status_label.text() == "再接続をキャンセルしました"
    assert tab.swbt_reconnect_btn.text() == "Reconnect"


def test_adapter_refresh_resolves_saved_alias_without_auto_selecting_other(qtbot) -> None:
    settings = FakeSettings()
    settings.data["controller.swbt.adapter"] = "usb-1"
    provider = FakeSwbtAdapterProvider()
    tab = DeviceSettingsTab(
        settings,
        None,
        device_discovery=FakeDiscovery(),
        swbt_adapter_provider=provider,
    )
    qtbot.addWidget(tab)

    qtbot.waitUntil(lambda: provider.calls == 1 and not tab._swbt_busy)

    assert tab.swbt_adapter.currentData() == "hci0"


def test_adapter_refresh_callback_is_safe_after_tab_deletion(qtbot) -> None:
    started = Event()
    release = Event()
    finished = Event()

    def provider():
        started.set()
        release.wait(2.0)
        finished.set()
        return ()

    tab = DeviceSettingsTab(
        FakeSettings(),
        None,
        device_discovery=FakeDiscovery(),
        swbt_adapter_provider=provider,
    )
    qtbot.addWidget(tab)
    qtbot.waitUntil(started.is_set)

    tab.deleteLater()
    qtbot.wait(0)
    release.set()
    qtbot.waitUntil(finished.is_set)


def test_device_settings_tab_does_not_list_stale_serial_setting(qtbot):
    settings = FakeSettings()
    settings.data["controller.serial.device"] = "COM9"
    tab = DeviceSettingsTab(settings, None, device_discovery=EmptyDiscovery())
    qtbot.addWidget(tab)

    assert tab.ser_device.findText("COM9") < 0
    assert tab.ser_device.count() == 0


def test_device_settings_tab_does_not_list_stale_window_setting(qtbot):
    settings = FakeSettings()
    settings.data["capture_window_title"] = "Disconnected Viewer"
    settings.data["capture_window_identifier"] = "hwnd-old"
    tab = DeviceSettingsTab(settings, None, device_discovery=EmptyDiscovery())
    qtbot.addWidget(tab)

    assert tab.window_source.findText("Disconnected Viewer") < 0
    assert tab.window_source.count() == 0


def test_device_settings_tab_updates_window_size_preset(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    tab.window_size_preset.setCurrentIndex(tab.window_size_preset.findData("four_k"))
    tab.apply()

    assert settings.data["gui.window_size_preset"] == "four_k"


def test_device_settings_tab_places_preview_fps_in_appearance_group(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert "Preview FPS:" not in _label_texts(tab.cap_group)
    assert "Preview FPS:" in _label_texts(tab.appearance_group)


def _label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def _set_capture_source(tab: DeviceSettingsTab, source_type: str) -> None:
    index = tab.capture_source_type.findData(source_type)
    assert index >= 0
    tab.capture_source_type.setCurrentIndex(index)
