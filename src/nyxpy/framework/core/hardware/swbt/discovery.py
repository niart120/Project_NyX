"""swbt USB Bluetooth adapter discovery。"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from nyxpy.framework.core.hardware.swbt.errors import (
    adapter_discovery_failed,
    swbt_configuration_error,
)


@dataclass(frozen=True, slots=True)
class SwbtAdapterView:
    """CLI / GUI に出す swbt adapter 表示 DTO。"""

    name: str
    aliases: tuple[str, ...]
    display_name: str
    vendor_id: int | None
    product_id: int | None
    manufacturer: str | None
    product: str | None
    serial_number: str | None
    bus_number: int | None
    device_address: int | None
    port_numbers: tuple[int, ...]
    is_bluetooth_hci: bool

    @classmethod
    def from_adapter_info(cls, adapter: object) -> "SwbtAdapterView":
        """swbt.AdapterInfo 互換 object から DTO を作る。"""
        name = str(getattr(adapter, "name"))
        manufacturer = _optional_str(getattr(adapter, "manufacturer", None))
        product = _optional_str(getattr(adapter, "product", None))
        vendor_id = _optional_int(getattr(adapter, "vendor_id", None))
        product_id = _optional_int(getattr(adapter, "product_id", None))
        return cls(
            name=name,
            aliases=tuple(str(alias) for alias in getattr(adapter, "aliases", ())),
            display_name=_display_name(name, manufacturer, product, vendor_id, product_id),
            vendor_id=vendor_id,
            product_id=product_id,
            manufacturer=manufacturer,
            product=product,
            serial_number=_optional_str(getattr(adapter, "serial_number", None)),
            bus_number=_optional_int(getattr(adapter, "bus_number", None)),
            device_address=_optional_int(getattr(adapter, "device_address", None)),
            port_numbers=tuple(int(port) for port in getattr(adapter, "port_numbers", ())),
            is_bluetooth_hci=bool(getattr(adapter, "is_bluetooth_hci", False)),
        )


class SwbtAdapterDiscoveryService:
    """swbt.list_adapters() を NyX DTO と例外へ変換する service。"""

    def __init__(
        self,
        *,
        list_adapters: Callable[[], Iterable[object]] | None = None,
        discovery_error_types: tuple[type[BaseException], ...] | None = None,
    ) -> None:
        """Adapter 列挙関数を保持する。未指定時は swbt root module を遅延 import する。"""
        self._list_adapters = list_adapters
        self._discovery_error_types = discovery_error_types

    def list_adapters(self) -> tuple[SwbtAdapterView, ...]:
        """Adapter 候補だけを列挙し、controller open や接続操作は行わない。"""
        list_adapters, error_types = self._adapter_api()
        try:
            adapters = tuple(list_adapters())
        except error_types as exc:
            raise adapter_discovery_failed(exc) from exc
        return tuple(SwbtAdapterView.from_adapter_info(adapter) for adapter in adapters)

    def _adapter_api(
        self,
    ) -> tuple[Callable[[], Iterable[object]], tuple[type[BaseException], ...]]:
        if self._list_adapters is not None:
            return self._list_adapters, self._discovery_error_types or (Exception,)

        from swbt import AdapterDiscoveryError, list_adapters

        return list_adapters, (AdapterDiscoveryError,)


def resolve_adapter(
    selected: str | None,
    adapters: Iterable[SwbtAdapterView],
) -> SwbtAdapterView:
    """ユーザ指定 adapter 名または alias を一意の adapter view に解決する。"""
    name = (selected or "").strip()
    adapter_tuple = tuple(adapters)
    if not name:
        raise swbt_configuration_error(
            "swbt adapter is not selected",
            code="NYX_SWBT_ADAPTER_NOT_SELECTED",
            component="SwbtAdapterDiscoveryService",
        )

    matches = [
        adapter for adapter in adapter_tuple if adapter.name == name or name in adapter.aliases
    ]
    if not matches:
        raise swbt_configuration_error(
            f"swbt adapter not found: {name}",
            code="NYX_SWBT_ADAPTER_NOT_FOUND",
            component="SwbtAdapterDiscoveryService",
        )
    if len(matches) > 1:
        raise swbt_configuration_error(
            f"swbt adapter is ambiguous: {name}",
            code="NYX_SWBT_ADAPTER_AMBIGUOUS",
            component="SwbtAdapterDiscoveryService",
        )
    return matches[0]


def _display_name(
    name: str,
    manufacturer: str | None,
    product: str | None,
    vendor_id: int | None,
    product_id: int | None,
) -> str:
    label = " ".join(part for part in (manufacturer, product) if part).strip() or name
    if vendor_id is None or product_id is None:
        return f"{name} - {label}"
    return f"{name} - {label} (VID:PID {vendor_id:04x}:{product_id:04x})"


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(str(value))
