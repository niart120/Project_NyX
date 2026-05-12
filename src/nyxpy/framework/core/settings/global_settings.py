from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from threading import RLock
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.settings.schema import (
    SecretBoundaryError,
    SettingField,
    SettingsSchema,
    SettingValue,
    dotted_get,
    dotted_set,
    freeze_mapping,
)

GLOBAL_SETTINGS_SCHEMA = SettingsSchema(
    fields={
        "capture_device": SettingField("capture_device", str, ""),
        "serial_device": SettingField("serial_device", str, ""),
        "serial_baud": SettingField("serial_baud", int, 9600),
        "serial_protocol": SettingField("serial_protocol", str, "CH552"),
        "runtime.allow_dummy": SettingField("runtime.allow_dummy", bool, False),
        "runtime.frame_ready_timeout_sec": SettingField(
            "runtime.frame_ready_timeout_sec", float, 3.0
        ),
        "logging.file_level": SettingField(
            "logging.file_level",
            str,
            "DEBUG",
            choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        ),
        "logging.gui_level": SettingField(
            "logging.gui_level",
            str,
            "INFO",
            choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        ),
    }
)


class SettingsStore:
    """Schema-validated store for non-secret global settings."""

    schema: SettingsSchema

    def __init__(
        self,
        config_dir: Path,
        *,
        schema: SettingsSchema = GLOBAL_SETTINGS_SCHEMA,
        filename: str = "global.toml",
        strict_load: bool = True,
    ) -> None:
        if any(field.secret for field in schema.fields.values()):
            raise SecretBoundaryError("SettingsStore schema must not contain secret fields")
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.config_dir / filename
        self.schema = schema
        self.strict_load = strict_load
        self._lock = RLock()
        self.data: dict[str, SettingValue] = {}
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                if self.config_path.exists():
                    loaded = tomlkit.loads(self.config_path.read_text(encoding="utf-8"))
                    self.data = self.schema.validate(loaded)
                else:
                    self.data = self.schema.defaults()
                    self.save()
            except TOMLKitError as exc:
                if self.strict_load:
                    raise ConfigurationError(
                        "failed to parse settings file",
                        code="NYX_SETTINGS_PARSE_FAILED",
                        component=type(self).__name__,
                        details={
                            "path": self.config_path.name,
                            "exception_type": type(exc).__name__,
                        },
                        cause=exc,
                    ) from exc
                self.data = self.schema.defaults()
            except ConfigurationError:
                if self.strict_load:
                    raise
                self.data = self.schema.defaults()

    def save(self) -> None:
        with self._lock:
            self.data = self.schema.validate(self.data)
            tmp_path = self.config_path.with_suffix(f"{self.config_path.suffix}.tmp")
            tmp_path.write_text(tomlkit.dumps(self.data), encoding="utf-8")
            tmp_path.replace(self.config_path)

    def snapshot(self) -> Mapping[str, SettingValue]:
        with self._lock:
            return freeze_mapping(self.data)

    def validate(self) -> None:
        with self._lock:
            self.data = self.schema.validate(self.data)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return dotted_get(self.data, key, default)

    def set(self, key: str, value: SettingValue) -> None:
        with self._lock:
            dotted_set(self.data, key, value)
            self.save()


class GlobalSettings(SettingsStore):
    """Schema-fixed store for non-secret global settings."""

    def __init__(self, config_dir: Path) -> None:
        super().__init__(config_dir=config_dir, strict_load=False)
