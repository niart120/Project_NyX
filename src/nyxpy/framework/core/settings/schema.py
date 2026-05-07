from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from nyxpy.framework.core.macro.exceptions import ConfigurationError

type SettingValue = str | int | float | bool | list[SettingValue] | dict[str, SettingValue] | None

_MISSING = object()


class SecretBoundaryError(ConfigurationError):
    def __init__(self, message: str = "secret boundary violation", **kwargs: object) -> None:
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_SECRET_BOUNDARY_INVALID")),
            component=str(kwargs.pop("component", "SecretBoundary")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


@dataclass(frozen=True)
class SettingField:
    name: str
    type_: type | tuple[type, ...]
    default: SettingValue
    secret: bool = False
    required: bool = False
    choices: tuple[SettingValue, ...] | None = None


@dataclass(frozen=True)
class SettingsSchema:
    fields: Mapping[str, SettingField]
    preserve_unknown: bool = True

    def validate(self, data: Mapping[str, Any]) -> dict[str, SettingValue]:
        result = _plain_mapping(data if self.preserve_unknown else {})
        source = _plain_mapping(data)
        for key, field in self.fields.items():
            value = _get_dotted(source, key, _MISSING)
            if value is _MISSING:
                if field.required and field.default is None:
                    raise _schema_error(
                        f"required setting is missing: {key}",
                        key=key,
                    )
                value = field.default
            validated = _validate_field(field, value)
            _set_dotted(result, key, validated)
        return result

    def defaults(self) -> dict[str, SettingValue]:
        result: dict[str, SettingValue] = {}
        for key, field in self.fields.items():
            _set_dotted(result, key, _copy_value(field.default))
        return result

    def mask(self, data: Mapping[str, Any]) -> dict[str, SettingValue]:
        result = _plain_mapping(data)
        for key, field in self.fields.items():
            if not field.secret or _get_dotted(result, key, _MISSING) is _MISSING:
                continue
            value = _get_dotted(result, key, "")
            _set_dotted(result, key, "***" if value not in ("", None) else "")
        return result


@dataclass(frozen=True)
class SecretsSnapshot:
    _data: Mapping[str, SettingValue]
    _schema: SettingsSchema

    def get(self, key: str, default: SettingValue = None) -> SettingValue:
        value = _get_dotted(self._data, key, _MISSING)
        return default if value is _MISSING else value

    def get_secret(self, key: str) -> str:
        field = self._schema.fields.get(key)
        if field is None or not field.secret:
            raise SecretBoundaryError(
                "requested key is not a secret",
                details={"key": key},
            )
        value = _get_dotted(self._data, key, "")
        return "" if value is None else str(value)

    def masked(self) -> Mapping[str, SettingValue]:
        return freeze_mapping(self._schema.mask(self._data))


def freeze_mapping(data: Mapping[str, Any]) -> Mapping[str, SettingValue]:
    return _freeze(_plain_mapping(data))


def dotted_get(data: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = _get_dotted(data, key, _MISSING)
    return default if value is _MISSING else value


def dotted_set(data: dict[str, Any], key: str, value: Any) -> None:
    _set_dotted(data, key, value)


def _validate_field(field: SettingField, value: Any) -> SettingValue:
    value = _plain_value(value)
    if not _matches_type(value, field.type_):
        raise _schema_error(
            f"invalid type for setting: {field.name}",
            key=field.name,
            expected=_type_name(field.type_),
            actual=type(value).__name__,
        )
    if field.choices is not None and value not in field.choices:
        raise _schema_error(
            f"invalid choice for setting: {field.name}",
            key=field.name,
        )
    if field.type_ is float and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    return value


def _matches_type(value: Any, expected: type | tuple[type, ...]) -> bool:
    expected_types = expected if isinstance(expected, tuple) else (expected,)
    if bool in expected_types:
        return isinstance(value, bool)
    if isinstance(value, bool) and (int in expected_types or float in expected_types):
        return False
    if float in expected_types and isinstance(value, int):
        return True
    return isinstance(value, expected_types)


def _schema_error(message: str, **details: SettingValue) -> ConfigurationError:
    return ConfigurationError(
        message,
        code="NYX_SETTINGS_SCHEMA_INVALID",
        component="SettingsSchema",
        details=dict(details),
    )


def _type_name(expected: type | tuple[type, ...]) -> str:
    if isinstance(expected, tuple):
        return " | ".join(t.__name__ for t in expected)
    return expected.__name__


def _plain_mapping(data: Mapping[str, Any]) -> dict[str, SettingValue]:
    plain = _plain_value(data)
    if not isinstance(plain, dict):
        raise _schema_error("settings root must be a mapping")
    return plain


def _plain_value(value: Any) -> SettingValue:
    unwrap = getattr(value, "unwrap", None)
    if callable(unwrap):
        value = unwrap()
    if isinstance(value, Mapping):
        return {str(k): _plain_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain_value(v) for v in value]
    return value


def _copy_value(value: SettingValue) -> SettingValue:
    return _plain_value(value)


def _get_dotted(data: Mapping[str, Any], key: str, default: Any = None) -> Any:
    if key in data:
        return data[key]
    current: Any = data
    for part in key.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def _set_dotted(data: dict[str, Any], key: str, value: Any) -> None:
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current[parts[-1]] = _copy_value(value)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(v) for v in value)
    return value
