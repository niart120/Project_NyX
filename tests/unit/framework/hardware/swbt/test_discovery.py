from dataclasses import dataclass

import pytest

from nyxpy.framework.core.hardware.swbt.discovery import (
    SwbtAdapterDiscoveryService,
    SwbtAdapterView,
    resolve_adapter,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class DiscoveryFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class AdapterInfo:
    name: str
    aliases: tuple[str, ...] = ()
    vendor_id: int | None = None
    product_id: int | None = None
    manufacturer: str | None = None
    product: str | None = None
    serial_number: str | None = None
    bus_number: int | None = None
    device_address: int | None = None
    port_numbers: tuple[int, ...] = ()
    is_bluetooth_hci: bool = True


def test_adapter_discovery_returns_view_without_opening_controller() -> None:
    calls: list[str] = []

    def list_adapters():
        calls.append("list_adapters")
        return (
            AdapterInfo(
                name="usb:0",
                aliases=("hci0",),
                vendor_id=0x0B05,
                product_id=0x190E,
                manufacturer="ASUS",
                product="USB-BT500",
                serial_number="abc",
                bus_number=1,
                device_address=2,
                port_numbers=(3,),
            ),
        )

    service = SwbtAdapterDiscoveryService(
        list_adapters=list_adapters,
        discovery_error_types=(DiscoveryFailed,),
    )

    adapters = service.list_adapters()

    assert calls == ["list_adapters"]
    assert adapters == (
        SwbtAdapterView(
            name="usb:0",
            aliases=("hci0",),
            display_name="usb:0 - ASUS USB-BT500 (VID:PID 0b05:190e)",
            vendor_id=0x0B05,
            product_id=0x190E,
            manufacturer="ASUS",
            product="USB-BT500",
            serial_number="abc",
            bus_number=1,
            device_address=2,
            port_numbers=(3,),
            is_bluetooth_hci=True,
        ),
    )


def test_adapter_discovery_maps_swbt_errors() -> None:
    def list_adapters():
        raise DiscoveryFailed("usb error")

    service = SwbtAdapterDiscoveryService(
        list_adapters=list_adapters,
        discovery_error_types=(DiscoveryFailed,),
    )

    with pytest.raises(ConfigurationError) as exc_info:
        service.list_adapters()

    assert exc_info.value.code == "NYX_SWBT_ADAPTER_DISCOVERY_FAILED"


def test_resolve_adapter_uses_aliases_and_rejects_ambiguous() -> None:
    first = SwbtAdapterView(
        name="usb:0",
        aliases=("primary",),
        display_name="usb:0",
        vendor_id=None,
        product_id=None,
        manufacturer=None,
        product=None,
        serial_number=None,
        bus_number=None,
        device_address=None,
        port_numbers=(),
        is_bluetooth_hci=True,
    )
    second = SwbtAdapterView(
        name="usb:1",
        aliases=("primary",),
        display_name="usb:1",
        vendor_id=None,
        product_id=None,
        manufacturer=None,
        product=None,
        serial_number=None,
        bus_number=None,
        device_address=None,
        port_numbers=(),
        is_bluetooth_hci=True,
    )

    assert resolve_adapter("usb:0", (first,)).name == "usb:0"
    assert resolve_adapter("primary", (first,)).name == "usb:0"

    with pytest.raises(ConfigurationError) as exc_info:
        resolve_adapter("primary", (first, second))
    assert exc_info.value.code == "NYX_SWBT_ADAPTER_AMBIGUOUS"

    with pytest.raises(ConfigurationError) as not_selected:
        resolve_adapter("", (first,))
    assert not_selected.value.code == "NYX_SWBT_ADAPTER_NOT_SELECTED"

    with pytest.raises(ConfigurationError) as not_found:
        resolve_adapter("missing", (first,))
    assert not_found.value.code == "NYX_SWBT_ADAPTER_NOT_FOUND"
