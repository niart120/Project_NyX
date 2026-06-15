"""Adapter for ponkan-python capture device discovery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, cast


class _UpstreamCaptureDevice(Protocol):
    id: str
    display_name: str
    profile_id: str
    model: str
    backend: str
    backend_preference: str
    vendor_id: int | None
    product_id: int | None
    serial_number: str | None
    product_string: str | None
    product_string_status: str
    connection_status: str
    id_stability: str
    reason: str
    remediation: str | None


class _UpstreamCaptureDiscovery(Protocol):
    profile_id: str
    backend_preference: str
    resolved_backend: str
    backend_status: str
    reason: str
    remediation: str | None
    devices: tuple[_UpstreamCaptureDevice, ...]


type PonkanListCaptureDevices = Callable[..., object]


@dataclass(frozen=True)
class PonkanCaptureDeviceDescriptor:
    """NyX-owned snapshot of one ponkan capture device descriptor."""

    id: str
    display_name: str
    profile_id: str
    model: str
    backend: str
    backend_preference: str
    vendor_id: int | None
    product_id: int | None
    serial_number: str | None
    product_string: str | None
    product_string_status: str
    connection_status: str
    id_stability: str
    reason: str = "available"
    remediation: str | None = None


@dataclass(frozen=True)
class PonkanCaptureDiscoverySnapshot:
    """NyX-owned snapshot of ponkan capture discovery status."""

    profile_id: str = "n3dsxl"
    backend_preference: str = "auto"
    resolved_backend: str = ""
    backend_status: str = "unavailable"
    reason: str = "missing_package"
    remediation: str | None = None
    devices: tuple[PonkanCaptureDeviceDescriptor, ...] = ()
    timed_out: bool = False
    errors: tuple[str, ...] = ()


def list_ponkan_capture_devices(
    *,
    profile: str = "n3dsxl",
    backend: str = "auto",
    include_rejected: bool = False,
    lister: PonkanListCaptureDevices | None = None,
) -> PonkanCaptureDiscoverySnapshot:
    """List ponkan capture devices without exposing ponkan objects to callers."""
    if lister is None:
        try:
            ponkan = import_module("ponkan")
        except ImportError as exc:
            return PonkanCaptureDiscoverySnapshot(
                profile_id=profile,
                backend_preference=backend,
                reason="missing_package",
                remediation="Install the ponkan optional dependency for NyX.",
                errors=(f"ponkan: {type(exc).__name__}: {exc}",),
            )
        try:
            lister = cast(PonkanListCaptureDevices, getattr(ponkan, "list_capture_devices"))
        except AttributeError as exc:
            return PonkanCaptureDiscoverySnapshot(
                profile_id=profile,
                backend_preference=backend,
                reason="missing_package",
                remediation="Install ponkan-python 0.2.0 or later.",
                errors=(f"ponkan: {type(exc).__name__}: {exc}",),
            )

    try:
        discovery = lister(profile=profile, backend=backend, include_rejected=include_rejected)
    except Exception as exc:
        return PonkanCaptureDiscoverySnapshot(
            profile_id=profile,
            backend_preference=backend,
            backend_status="unavailable",
            reason=_error_reason(exc),
            remediation=_optional_text(getattr(exc, "remediation", None)),
            errors=(f"ponkan: {type(exc).__name__}: {exc}",),
        )

    return _snapshot_from_upstream(cast(_UpstreamCaptureDiscovery, discovery))


def _snapshot_from_upstream(
    discovery: _UpstreamCaptureDiscovery,
) -> PonkanCaptureDiscoverySnapshot:
    return PonkanCaptureDiscoverySnapshot(
        profile_id=str(discovery.profile_id),
        backend_preference=str(discovery.backend_preference),
        resolved_backend=str(discovery.resolved_backend),
        backend_status=str(discovery.backend_status),
        reason=str(discovery.reason),
        remediation=_optional_text(discovery.remediation),
        devices=tuple(_descriptor_from_upstream(device) for device in discovery.devices),
    )


def _descriptor_from_upstream(
    device: _UpstreamCaptureDevice,
) -> PonkanCaptureDeviceDescriptor:
    return PonkanCaptureDeviceDescriptor(
        id=str(device.id),
        display_name=str(device.display_name),
        profile_id=str(device.profile_id),
        model=str(device.model),
        backend=str(device.backend),
        backend_preference=str(device.backend_preference),
        vendor_id=device.vendor_id,
        product_id=device.product_id,
        serial_number=_optional_text(device.serial_number),
        product_string=_optional_text(device.product_string),
        product_string_status=str(device.product_string_status),
        connection_status=str(device.connection_status),
        id_stability=str(device.id_stability),
        reason=str(device.reason),
        remediation=_optional_text(device.remediation),
    )


def _error_reason(exc: Exception) -> str:
    reason = getattr(exc, "reason", None)
    return str(reason) if reason else "unknown"


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
