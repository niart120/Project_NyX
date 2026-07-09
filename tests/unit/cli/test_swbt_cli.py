import io
import json

from nyxpy.cli.swbt_cli import cli_main
from nyxpy.framework.core.hardware.swbt.discovery import SwbtAdapterView


class Discovery:
    def __init__(self, adapters: tuple[SwbtAdapterView, ...]) -> None:
        self.adapters = adapters
        self.calls = 0

    def list_adapters(self) -> tuple[SwbtAdapterView, ...]:
        self.calls += 1
        return self.adapters


def adapter_view() -> SwbtAdapterView:
    return SwbtAdapterView(
        name="usb:0",
        aliases=("hci0",),
        display_name="usb:0 - ASUS USB-BT500",
        vendor_id=0x0B05,
        product_id=0x190E,
        manufacturer="ASUS",
        product="USB-BT500",
        serial_number=None,
        bus_number=1,
        device_address=2,
        port_numbers=(3,),
        is_bluetooth_hci=True,
    )


def test_swbt_adapters_cli_prints_json_without_changing_settings() -> None:
    discovery = Discovery((adapter_view(),))
    stdout = io.StringIO()
    args = type("Args", (), {"swbt_command": "adapters", "json": True})()

    exit_code = cli_main(args, discovery_service=discovery, stdout=stdout)

    assert exit_code == 0
    assert discovery.calls == 1
    payload = json.loads(stdout.getvalue())
    assert payload[0]["name"] == "usb:0"
    assert payload[0]["aliases"] == ["hci0"]


def test_swbt_adapters_cli_prints_empty_result() -> None:
    discovery = Discovery(())
    stdout = io.StringIO()
    args = type("Args", (), {"swbt_command": "adapters", "json": False})()

    assert cli_main(args, discovery_service=discovery, stdout=stdout) == 0

    assert stdout.getvalue().strip() == "No swbt USB Bluetooth adapter found."
