"""接続要求と検出 snapshot から実際に使う device を選択します。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from nyxpy.framework.core.hardware.device_discovery import (
    DUMMY_DEVICE_NAME,
    DeviceDiscoveryResult,
    DeviceInfo,
)
from nyxpy.framework.core.hardware.window_discovery import WindowInfo

ConnectionKind = Literal["serial", "capture", "window"]
SelectableTarget = DeviceInfo | WindowInfo


class ConnectionResolveStatus(StrEnum):
    """接続要求の解決結果。"""

    SELECTED = "selected"
    FALLBACK_DUMMY = "fallback_dummy"
    ERROR = "error"


class ConnectionFallbackReason(StrEnum):
    """Dummy fallback または解決失敗の理由。"""

    NOT_SELECTED = "not_selected"
    USER_SELECTED_DUMMY = "user_selected_dummy"
    NOT_FOUND = "not_found"
    DISCOVERY_TIMED_OUT = "discovery_timed_out"


@dataclass(frozen=True)
class ConnectionRequest:
    """保存済み設定または UI 操作から作られる接続要求。"""

    kind: ConnectionKind
    requested: str | None
    allow_dummy: bool


@dataclass(frozen=True)
class ResolvedConnection:
    """接続要求の解決結果。"""

    status: ConnectionResolveStatus
    kind: ConnectionKind
    requested: str | None
    selected: SelectableTarget | None = None
    fallback_reason: ConnectionFallbackReason | None = None

    @property
    def uses_dummy(self) -> bool:
        """Dummy device を使う結果かどうかを返します。"""
        return self.status == ConnectionResolveStatus.FALLBACK_DUMMY


def select_serial_target(
    request: ConnectionRequest,
    result: DeviceDiscoveryResult,
) -> ResolvedConnection:
    """シリアル接続要求を検出 snapshot から解決します。"""
    return _select_device_target(
        request,
        devices=result.serial_devices,
        timed_out=result.timed_out,
        matcher=lambda device, requested: str(device.identifier) == requested,
    )


def select_capture_target(
    request: ConnectionRequest,
    result: DeviceDiscoveryResult,
) -> ResolvedConnection:
    """キャプチャ接続要求を検出 snapshot から解決します。"""
    return _select_device_target(
        request,
        devices=result.capture_devices,
        timed_out=result.timed_out,
        matcher=lambda device, requested: device.name == requested,
    )


def select_window_target(
    request: ConnectionRequest,
    windows: tuple[WindowInfo, ...],
) -> ResolvedConnection:
    """Window capture 接続要求を検出 snapshot から解決します。"""
    requested = _normalize_requested(request.requested)
    if requested is None:
        return _fallback_or_error(request, ConnectionFallbackReason.NOT_SELECTED)
    match = next(
        (
            window
            for window in windows
            if str(window.identifier) == requested or window.title == requested
        ),
        None,
    )
    if match is not None:
        return ResolvedConnection(
            status=ConnectionResolveStatus.SELECTED,
            kind=request.kind,
            requested=requested,
            selected=match,
        )
    return _fallback_or_error(request, ConnectionFallbackReason.NOT_FOUND)


def _select_device_target(
    request: ConnectionRequest,
    *,
    devices: tuple[DeviceInfo, ...],
    timed_out: bool,
    matcher,
) -> ResolvedConnection:
    requested = _normalize_requested(request.requested)
    if requested is None:
        return _fallback_or_error(request, ConnectionFallbackReason.NOT_SELECTED)
    if requested == DUMMY_DEVICE_NAME:
        return _fallback_or_error(request, ConnectionFallbackReason.USER_SELECTED_DUMMY)
    match = next((device for device in devices if matcher(device, requested)), None)
    if match is not None:
        return ResolvedConnection(
            status=ConnectionResolveStatus.SELECTED,
            kind=request.kind,
            requested=requested,
            selected=match,
        )
    reason = (
        ConnectionFallbackReason.DISCOVERY_TIMED_OUT
        if timed_out
        else ConnectionFallbackReason.NOT_FOUND
    )
    return _fallback_or_error(request, reason)


def _fallback_or_error(
    request: ConnectionRequest,
    reason: ConnectionFallbackReason,
) -> ResolvedConnection:
    requested = _normalize_requested(request.requested)
    if request.allow_dummy:
        return ResolvedConnection(
            status=ConnectionResolveStatus.FALLBACK_DUMMY,
            kind=request.kind,
            requested=requested,
            fallback_reason=reason,
        )
    return ResolvedConnection(
        status=ConnectionResolveStatus.ERROR,
        kind=request.kind,
        requested=requested,
        fallback_reason=reason,
    )


def _normalize_requested(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
