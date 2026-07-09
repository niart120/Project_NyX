"""controller backend settings の正規化 helper。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from nyxpy.framework.core.hardware.swbt.config import (
    SwbtControllerConfig,
    resolve_controller_model,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.settings.schema import dotted_get, dotted_set

_LEGACY_SERIAL_KEYS = ("serial_device", "serial_baud", "serial_protocol")


class ControllerBackend(StrEnum):
    """Project NyX が扱う controller 出力 backend。"""

    SERIAL = "serial"
    SWBT = "swbt"


@dataclass(frozen=True, slots=True)
class SerialControllerConfig:
    """serial backend 用 controller 設定。"""

    device: str | None
    protocol: str = "CH552"
    baudrate: int = 9600


type ControllerConfig = SerialControllerConfig | SwbtControllerConfig


def controller_config_from_settings(
    settings: Mapping[str, Any],
    *,
    workspace_root: Path | None = None,
) -> ControllerConfig:
    """`controller.*` settings から controller backend 設定を作る。"""
    _reject_legacy_serial_keys(settings)
    backend = parse_controller_backend(dotted_get(settings, "controller.backend", "serial"))
    if backend is ControllerBackend.SERIAL:
        return SerialControllerConfig(
            device=_optional_name(dotted_get(settings, "controller.serial.device", None)),
            protocol=str(dotted_get(settings, "controller.serial.protocol", "CH552") or "CH552"),
            baudrate=_positive_int(
                dotted_get(settings, "controller.serial.baudrate", 9600),
                key="controller.serial.baudrate",
            ),
        )

    model = resolve_controller_model(
        str(dotted_get(settings, "controller.swbt.controller_type", "pro-controller"))
    )
    key_store = _key_store_path(
        dotted_get(settings, "controller.swbt.key_store_path", None),
        default=model.default_key_store_path(_default_swbt_key_store_dir(workspace_root)),
    )
    return SwbtControllerConfig(
        model=model,
        adapter=_optional_name(dotted_get(settings, "controller.swbt.adapter", None)),
        key_store_path=key_store,
        connect_timeout_sec=_positive_float(
            dotted_get(settings, "controller.swbt.connect_timeout_sec", 30.0),
            key="controller.swbt.connect_timeout_sec",
        ),
        report_period_us=_optional_positive_int(
            dotted_get(settings, "controller.swbt.report_period_us", 8000),
            key="controller.swbt.report_period_us",
        ),
    )


def controller_config_from_overrides(
    settings: Mapping[str, Any],
    *,
    workspace_root: Path | None = None,
    backend: str | ControllerBackend | None = None,
    serial_device: str | None = None,
    serial_protocol: str | None = None,
    serial_baudrate: int | None = None,
    swbt_adapter: str | None = None,
    swbt_controller_type: str | None = None,
    swbt_key_store_path: Path | str | None = None,
    swbt_connect_timeout_sec: float | None = None,
) -> ControllerConfig:
    """Settings の copy に CLI override を重ねて ControllerConfig を作る。"""
    data = _settings_copy(settings)
    if backend is not None:
        dotted_set(data, "controller.backend", str(backend))
    if serial_device is not None:
        dotted_set(data, "controller.serial.device", serial_device)
    if serial_protocol is not None:
        dotted_set(data, "controller.serial.protocol", serial_protocol)
    if serial_baudrate is not None:
        dotted_set(data, "controller.serial.baudrate", serial_baudrate)
    if swbt_adapter is not None:
        dotted_set(data, "controller.swbt.adapter", swbt_adapter)
    if swbt_controller_type is not None:
        dotted_set(data, "controller.swbt.controller_type", swbt_controller_type)
    if swbt_key_store_path is not None:
        dotted_set(data, "controller.swbt.key_store_path", str(swbt_key_store_path))
    if swbt_connect_timeout_sec is not None:
        dotted_set(data, "controller.swbt.connect_timeout_sec", swbt_connect_timeout_sec)
    return controller_config_from_settings(data, workspace_root=workspace_root)


def parse_controller_backend(value: object) -> ControllerBackend:
    """Settings / CLI 入力を backend enum に正規化する。"""
    try:
        return ControllerBackend(str(value or "serial"))
    except ValueError as exc:
        raise ConfigurationError(
            f"unsupported controller backend: {value}",
            code="NYX_CONTROLLER_BACKEND_UNSUPPORTED",
            component="ControllerConfig",
            details={"backend": str(value)},
            cause=exc,
        ) from exc


def _reject_legacy_serial_keys(settings: Mapping[str, Any]) -> None:
    legacy_keys = [key for key in _LEGACY_SERIAL_KEYS if key in settings]
    if not legacy_keys:
        return
    raise ConfigurationError(
        "legacy serial settings are not supported by controller.* config",
        code="NYX_CONTROLLER_LEGACY_SERIAL_SETTINGS_UNSUPPORTED",
        component="ControllerConfig",
        details={"keys": list(legacy_keys)},
    )


def _default_swbt_key_store_dir(workspace_root: Path | None) -> Path:
    if workspace_root is None:
        return Path(".nyxpy") / "swbt"
    return Path(workspace_root) / ".nyxpy" / "swbt"


def _key_store_path(value: object, *, default: Path) -> Path:
    if value in (None, ""):
        return default
    return Path(str(value))


def _optional_name(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_int(value: object, *, key: str) -> int:
    result = int(str(value).strip())
    if result <= 0:
        raise _invalid_positive(key)
    return result


def _optional_positive_int(value: object, *, key: str) -> int | None:
    if value in (None, ""):
        return None
    return _positive_int(value, key=key)


def _positive_float(value: object, *, key: str) -> float:
    result = float(str(value).strip())
    if result <= 0:
        raise _invalid_positive(key)
    return result


def _invalid_positive(key: str) -> ConfigurationError:
    return ConfigurationError(
        f"{key} must be greater than 0",
        code="NYX_CONTROLLER_CONFIG_INVALID",
        component="ControllerConfig",
        details={"key": key},
    )


def _settings_copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _settings_copy(nested) for key, nested in value.items()}
    if isinstance(value, list | tuple):
        return [_settings_copy(item) for item in value]
    return value
