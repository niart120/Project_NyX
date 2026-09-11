from types import SimpleNamespace

from nyxpy.framework.core.hardware.ponkan_discovery import (
    list_ponkan_capture_devices,
)


def test_ponkan_capture_listing_maps_upstream_result() -> None:
    calls = {}

    def lister(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            profile_id="n3dsxl",
            backend_preference="auto",
            resolved_backend="d3xx-native",
            backend_status="available",
            reason="available",
            remediation=None,
            devices=(
                SimpleNamespace(
                    id="d3xx:ABC",
                    display_name="new 3DS XL",
                    profile_id="n3dsxl",
                    model="new_3ds_xl",
                    backend="d3xx-native",
                    backend_preference="auto",
                    vendor_id=0x0403,
                    product_id=0x601F,
                    serial_number="ABC",
                    product_string="N3DSXL",
                    product_string_status="accepted",
                    connection_status="available",
                    id_stability="stable",
                    reason="available",
                    remediation=None,
                ),
            ),
        )

    snapshot = list_ponkan_capture_devices(lister=lister)

    assert calls == {"profile": "n3dsxl", "backend": "auto", "include_rejected": False}
    assert snapshot.backend_status == "available"
    assert snapshot.reason == "available"
    assert snapshot.devices[0].id == "d3xx:ABC"
    assert snapshot.devices[0].connection_status == "available"


def test_ponkan_capture_listing_reports_upstream_error() -> None:
    class CaptureError(Exception):
        reason = "missing_runtime"
        remediation = "Install D3XX runtime."

    snapshot = list_ponkan_capture_devices(
        lister=lambda **_kwargs: (_ for _ in ()).throw(CaptureError("missing runtime"))
    )

    assert snapshot.backend_status == "unavailable"
    assert snapshot.reason == "missing_runtime"
    assert snapshot.remediation == "Install D3XX runtime."
    assert snapshot.errors == ("ponkan: CaptureError: missing runtime",)
