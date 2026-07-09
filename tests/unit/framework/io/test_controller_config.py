from pathlib import Path

import pytest

from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, SwbtControllerType
from nyxpy.framework.core.io.controller_config import (
    ControllerBackend,
    SerialControllerConfig,
    controller_config_from_overrides,
    controller_config_from_settings,
    parse_controller_backend,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


def test_serial_controller_config_from_controller_schema() -> None:
    config = controller_config_from_settings(
        {
            "controller": {
                "backend": "serial",
                "serial": {
                    "device": "COM3",
                    "protocol": "3DS",
                    "baudrate": 115200,
                },
            }
        }
    )

    assert config == SerialControllerConfig(device="COM3", protocol="3DS", baudrate=115200)


def test_controller_config_rejects_legacy_serial_flat_keys() -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        controller_config_from_settings(
            {
                "serial_device": "COM3",
                "serial_baud": 9600,
                "serial_protocol": "CH552",
            }
        )

    assert exc_info.value.code == "NYX_CONTROLLER_LEGACY_SERIAL_SETTINGS_UNSUPPORTED"


def test_swbt_controller_config_resolves_model_and_default_key_store(tmp_path: Path) -> None:
    config = controller_config_from_settings(
        {
            "controller": {
                "backend": "swbt",
                "swbt": {
                    "controller_type": "joy-con-l",
                    "adapter": "",
                    "connect_timeout_sec": 12,
                    "report_period_us": None,
                },
            }
        },
        workspace_root=tmp_path,
    )

    assert isinstance(config, SwbtControllerConfig)
    assert config.model.controller_type is SwbtControllerType.JOY_CON_L
    assert config.adapter is None
    assert config.key_store_path == tmp_path / ".nyxpy" / "swbt" / "joy-con-l-bond.json"
    assert config.connect_timeout_sec == 12.0
    assert config.report_period_us is None


def test_swbt_controller_config_does_not_keep_controller_type_string() -> None:
    config = controller_config_from_settings(
        {
            "controller": {
                "backend": "swbt",
                "swbt": {
                    "controller_type": "pro-controller",
                    "adapter": "usb:0",
                    "key_store_path": ".nyxpy/swbt/pro.json",
                },
            }
        }
    )

    assert isinstance(config, SwbtControllerConfig)
    assert not hasattr(config, "controller_type")
    assert config.model.controller_type is SwbtControllerType.PRO_CONTROLLER
    assert config.adapter == "usb:0"
    assert config.key_store_path == Path(".nyxpy/swbt/pro.json")


def test_controller_config_overrides_do_not_mutate_settings(tmp_path: Path) -> None:
    settings = {
        "controller": {
            "backend": "serial",
            "swbt": {
                "controller_type": "joy-con-r",
                "adapter": "settings-adapter",
            },
        }
    }

    config = controller_config_from_overrides(
        settings,
        workspace_root=tmp_path,
        backend="swbt",
        swbt_controller_type="pro-controller",
        swbt_adapter="usb:0",
        swbt_connect_timeout_sec=5.0,
    )

    assert isinstance(config, SwbtControllerConfig)
    assert config.model.controller_type is SwbtControllerType.PRO_CONTROLLER
    assert config.adapter == "usb:0"
    assert config.connect_timeout_sec == 5.0
    assert settings["controller"]["backend"] == "serial"
    assert settings["controller"]["swbt"]["controller_type"] == "joy-con-r"
    assert settings["controller"]["swbt"]["adapter"] == "settings-adapter"


def test_controller_config_rejects_invalid_backend_and_non_positive_values() -> None:
    with pytest.raises(ConfigurationError) as backend_error:
        parse_controller_backend("bluetooth")
    assert backend_error.value.code == "NYX_CONTROLLER_BACKEND_UNSUPPORTED"

    assert parse_controller_backend(None) is ControllerBackend.SERIAL

    with pytest.raises(ConfigurationError) as timeout_error:
        controller_config_from_settings(
            {
                "controller": {
                    "backend": "swbt",
                    "swbt": {
                        "connect_timeout_sec": 0,
                    },
                }
            }
        )
    assert timeout_error.value.code == "NYX_CONTROLLER_CONFIG_INVALID"
