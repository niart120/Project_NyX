from nyxpy.framework.core.hardware.device_discovery import (
    DUMMY_DEVICE_NAME,
    DeviceDiscoveryResult,
    DeviceInfo,
)
from nyxpy.framework.core.hardware.window_discovery import WindowInfo
from nyxpy.framework.core.runtime.device_selection import (
    ConnectionFallbackReason,
    ConnectionRequest,
    ConnectionResolveStatus,
    select_capture_target,
    select_serial_target,
    select_window_target,
)


def test_select_serial_target_returns_detected_identifier_match() -> None:
    result = DeviceDiscoveryResult(
        serial_devices=(
            DeviceInfo(kind="serial", name="USB Serial Device (COM1)", identifier="COM1"),
        )
    )

    selected = select_serial_target(
        ConnectionRequest(kind="serial", requested="COM1", allow_dummy=False),
        result,
    )

    assert selected.status == ConnectionResolveStatus.SELECTED
    assert selected.selected == result.serial_devices[0]


def test_select_serial_target_falls_back_to_dummy_when_saved_device_missing() -> None:
    selected = select_serial_target(
        ConnectionRequest(kind="serial", requested="COM9", allow_dummy=True),
        DeviceDiscoveryResult(),
    )

    assert selected.status == ConnectionResolveStatus.FALLBACK_DUMMY
    assert selected.fallback_reason == ConnectionFallbackReason.NOT_FOUND


def test_select_serial_target_rejects_missing_device_when_dummy_is_not_allowed() -> None:
    selected = select_serial_target(
        ConnectionRequest(kind="serial", requested="COM9", allow_dummy=False),
        DeviceDiscoveryResult(timed_out=True),
    )

    assert selected.status == ConnectionResolveStatus.ERROR
    assert selected.fallback_reason == ConnectionFallbackReason.DISCOVERY_TIMED_OUT


def test_select_serial_target_accepts_user_selected_dummy_when_allowed() -> None:
    selected = select_serial_target(
        ConnectionRequest(kind="serial", requested=DUMMY_DEVICE_NAME, allow_dummy=True),
        DeviceDiscoveryResult(),
    )

    assert selected.status == ConnectionResolveStatus.FALLBACK_DUMMY
    assert selected.fallback_reason == ConnectionFallbackReason.USER_SELECTED_DUMMY


def test_select_capture_target_matches_by_display_name_only() -> None:
    result = DeviceDiscoveryResult(
        capture_devices=(DeviceInfo(kind="capture", name="1: Capture Card", identifier=1),)
    )

    selected = select_capture_target(
        ConnectionRequest(kind="capture", requested="1: Capture Card", allow_dummy=False),
        result,
    )

    assert selected.status == ConnectionResolveStatus.SELECTED
    assert selected.selected == result.capture_devices[0]


def test_select_capture_target_does_not_treat_numeric_text_as_implicit_index() -> None:
    result = DeviceDiscoveryResult(
        capture_devices=(DeviceInfo(kind="capture", name="1: Capture Card", identifier=1),)
    )

    selected = select_capture_target(
        ConnectionRequest(kind="capture", requested="1", allow_dummy=True),
        result,
    )

    assert selected.status == ConnectionResolveStatus.FALLBACK_DUMMY
    assert selected.fallback_reason == ConnectionFallbackReason.NOT_FOUND


def test_select_window_target_matches_by_identifier_or_title() -> None:
    windows = (
        WindowInfo(title="Viewer", identifier="hwnd-1", rect=None),
        WindowInfo(title="Other", identifier="hwnd-2", rect=None),
    )

    by_identifier = select_window_target(
        ConnectionRequest(kind="window", requested="hwnd-1", allow_dummy=False),
        windows,
    )
    by_title = select_window_target(
        ConnectionRequest(kind="window", requested="Other", allow_dummy=False),
        windows,
    )

    assert by_identifier.selected == windows[0]
    assert by_title.selected == windows[1]
