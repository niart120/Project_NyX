import io
import json
from pathlib import Path

import pytest

import nyxpy.cli.swbt_cli as swbt_cli
from nyxpy.__main__ import parse_arguments
from nyxpy.cli.swbt_cli import cli_main
from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig
from nyxpy.framework.core.hardware.swbt.diagnostics import LoggerDiagnosticsWriter
from nyxpy.framework.core.hardware.swbt.discovery import SwbtAdapterView
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.settings.global_settings import SettingsStore
from tests.support.fakes import FakeLoggerPort


class Discovery:
    def __init__(self, adapters: tuple[SwbtAdapterView, ...]) -> None:
        self.adapters = adapters
        self.calls = 0

    def list_adapters(self) -> tuple[SwbtAdapterView, ...]:
        self.calls += 1
        return self.adapters


class RecordingFactory:
    def __init__(self) -> None:
        self.calls = []
        self.closed = False

    def pair(self, config: SwbtControllerConfig, *, timeout_sec: float) -> None:
        self.calls.append(("pair", config, timeout_sec))

    def reconnect(self, config: SwbtControllerConfig, *, timeout_sec: float) -> None:
        self.calls.append(("reconnect", config, timeout_sec))

    def disconnect(self, config: SwbtControllerConfig) -> None:
        self.calls.append(("disconnect", config, None))

    def close(self) -> None:
        self.closed = True


def adapter_view(
    name: str = "usb:0",
    aliases: tuple[str, ...] = ("hci0",),
) -> SwbtAdapterView:
    return SwbtAdapterView(
        name=name,
        aliases=aliases,
        display_name=f"{name} - ASUS USB-BT500",
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


def test_swbt_pair_cli_calls_factory_pair(tmp_path: Path) -> None:
    factory = RecordingFactory()
    discovery = Discovery((adapter_view(),))
    stdout = io.StringIO()
    args = type(
        "Args",
        (),
        {
            "swbt_command": "pair",
            "adapter": "usb:0",
            "controller_type": "pro-controller",
            "key_store": tmp_path / "bond.json",
            "timeout": 5.0,
        },
    )()

    exit_code = cli_main(
        args,
        discovery_service=discovery,
        controller_factory=factory,
        project_root=tmp_path,
        stdout=stdout,
    )

    assert exit_code == 0
    assert factory.closed is True
    assert factory.calls[0][0] == "pair"
    assert factory.calls[0][1].adapter == "usb:0"
    assert factory.calls[0][1].key_store_path == tmp_path / "bond.json"
    assert factory.calls[0][2] == 5.0
    assert stdout.getvalue().strip() == "swbt pair completed."


def test_swbt_reconnect_cli_calls_factory_reconnect(tmp_path: Path) -> None:
    factory = RecordingFactory()
    discovery = Discovery((adapter_view(),))
    args = type(
        "Args",
        (),
        {
            "swbt_command": "reconnect",
            "adapter": "usb:0",
            "controller_type": "pro-controller",
            "key_store": None,
            "timeout": 6.0,
        },
    )()

    assert (
        cli_main(
            args,
            discovery_service=discovery,
            controller_factory=factory,
            project_root=tmp_path,
        )
        == 0
    )

    assert factory.closed is True
    assert factory.calls[0][0] == "reconnect"
    assert factory.calls[0][2] == 6.0


def test_swbt_lifecycle_cli_canonicalizes_adapter_alias(tmp_path: Path) -> None:
    factory = RecordingFactory()
    discovery = Discovery((adapter_view(),))
    args = type(
        "Args",
        (),
        {
            "swbt_command": "pair",
            "adapter": "hci0",
            "controller_type": "pro-controller",
            "key_store": None,
            "timeout": None,
        },
    )()

    assert (
        cli_main(
            args,
            discovery_service=discovery,
            controller_factory=factory,
            project_root=tmp_path,
        )
        == 0
    )

    assert factory.calls[0][1].adapter == "usb:0"


def test_swbt_lifecycle_cli_injects_diagnostics_and_closes_logging(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured = {}
    logger = FakeLoggerPort()

    class RecordingLogging:
        def __init__(self) -> None:
            self.logger = logger
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class ProductionFactory(RecordingFactory):
        def __init__(self, *, diagnostics_writer) -> None:
            super().__init__()
            captured["diagnostics_writer"] = diagnostics_writer
            captured["factory"] = self

    logging = RecordingLogging()

    def create_logging(*, base_dir: Path):
        captured["base_dir"] = base_dir
        return logging

    monkeypatch.setattr(swbt_cli, "create_default_logging", create_logging)
    monkeypatch.setattr(swbt_cli, "SwbtControllerOutputPortFactory", ProductionFactory)
    args = type(
        "Args",
        (),
        {
            "swbt_command": "pair",
            "adapter": "usb:0",
            "controller_type": "pro-controller",
            "key_store": None,
            "timeout": None,
        },
    )()

    assert (
        cli_main(
            args,
            discovery_service=Discovery((adapter_view(),)),
            project_root=tmp_path,
            stdout=io.StringIO(),
        )
        == 0
    )

    writer = captured["diagnostics_writer"]
    assert isinstance(writer, LoggerDiagnosticsWriter)
    assert writer._logger is logger
    assert captured["base_dir"] == tmp_path / "logs"
    assert captured["factory"].closed
    assert logging.closed


def test_swbt_lifecycle_cli_rejects_unselected_missing_and_ambiguous_adapter(
    tmp_path: Path,
) -> None:
    args = type(
        "Args",
        (),
        {
            "swbt_command": "pair",
            "adapter": None,
            "controller_type": "pro-controller",
            "key_store": None,
            "timeout": None,
        },
    )()
    discovery = Discovery((adapter_view(),))

    with pytest.raises(ConfigurationError) as unselected_error:
        cli_main(
            args,
            discovery_service=discovery,
            controller_factory=RecordingFactory(),
            project_root=tmp_path,
        )
    assert unselected_error.value.code == "NYX_SWBT_ADAPTER_NOT_SELECTED"
    assert discovery.calls == 0

    args.adapter = "missing"
    with pytest.raises(ConfigurationError) as missing_error:
        cli_main(
            args,
            discovery_service=Discovery((adapter_view(),)),
            controller_factory=RecordingFactory(),
            project_root=tmp_path,
        )
    assert missing_error.value.code == "NYX_SWBT_ADAPTER_NOT_FOUND"

    args.adapter = "hci0"
    with pytest.raises(ConfigurationError) as ambiguous_error:
        cli_main(
            args,
            discovery_service=Discovery((adapter_view(), adapter_view("usb:1"))),
            controller_factory=RecordingFactory(),
            project_root=tmp_path,
        )
    assert ambiguous_error.value.code == "NYX_SWBT_ADAPTER_AMBIGUOUS"


def test_swbt_disconnect_command_is_not_exposed() -> None:
    with pytest.raises(SystemExit):
        parse_arguments(["swbt", "disconnect"])


def test_swbt_cli_overrides_do_not_mutate_settings(tmp_path: Path) -> None:
    settings = SettingsStore(config_dir=tmp_path / ".nyxpy", strict_load=False)
    settings.set("controller.swbt.adapter", "settings-adapter")
    settings.set("controller.swbt.controller_type", "joy-con-r")
    factory = RecordingFactory()
    args = type(
        "Args",
        (),
        {
            "swbt_command": "pair",
            "adapter": "usb:0",
            "controller_type": "pro-controller",
            "key_store": None,
            "timeout": 2.0,
        },
    )()

    assert (
        cli_main(
            args,
            discovery_service=Discovery((adapter_view(),)),
            controller_factory=factory,
            settings_store=settings,
            project_root=tmp_path,
        )
        == 0
    )

    assert factory.calls[0][1].adapter == "usb:0"
    assert factory.calls[0][1].model.settings_value == "pro-controller"
    assert settings.get("controller.swbt.adapter") == "settings-adapter"
    assert settings.get("controller.swbt.controller_type") == "joy-con-r"
