"""NyX workspace の global settings store。"""

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
        "capture_source_type": SettingField(
            "capture_source_type",
            str,
            "camera",
            choices=("camera", "window", "capture"),
        ),
        "capture_provider": SettingField(
            "capture_provider",
            str,
            "ponkan",
            choices=("ponkan",),
        ),
        "capture_device_profile": SettingField(
            "capture_device_profile",
            str,
            "n3dsxl",
        ),
        "capture_window_title": SettingField("capture_window_title", str, ""),
        "capture_window_match_mode": SettingField(
            "capture_window_match_mode",
            str,
            "exact",
            choices=("exact", "contains"),
        ),
        "capture_window_identifier": SettingField("capture_window_identifier", str, ""),
        "capture_backend": SettingField(
            "capture_backend",
            str,
            "auto",
            choices=("auto", "mss", "windows_graphics_capture"),
        ),
        "capture_fps": SettingField("capture_fps", (float, type(None)), None),
        "capture_aspect_box_enabled": SettingField("capture_aspect_box_enabled", bool, False),
        "ponkan_backend": SettingField(
            "ponkan_backend",
            str,
            "auto",
            choices=("auto", "d3xx", "d3xx-native"),
        ),
        "ponkan_raw_slots": SettingField("ponkan_raw_slots", int, 2),
        "ponkan_output_queue_size": SettingField("ponkan_output_queue_size", int, 2),
        "ponkan_drop_policy": SettingField(
            "ponkan_drop_policy",
            str,
            "drop_oldest",
            choices=("drop_oldest", "drop_newest", "block"),
        ),
        "ponkan_poll_interval": SettingField("ponkan_poll_interval", float, 0.004),
        "ponkan_read_timeout": SettingField(
            "ponkan_read_timeout",
            (float, type(None)),
            1.0,
        ),
        "ponkan_collect_timing": SettingField("ponkan_collect_timing", bool, False),
        "n3dsxl_hd_aspect_box_enabled": SettingField(
            "n3dsxl_hd_aspect_box_enabled",
            bool,
            True,
        ),
        "preview_fps": SettingField("preview_fps", int, 60),
        "controller.backend": SettingField(
            "controller.backend",
            str,
            "serial",
            choices=("serial", "swbt"),
        ),
        "controller.serial.device": SettingField("controller.serial.device", str, ""),
        "controller.serial.protocol": SettingField("controller.serial.protocol", str, "CH552"),
        "controller.serial.baudrate": SettingField("controller.serial.baudrate", int, 9600),
        "controller.swbt.controller_type": SettingField(
            "controller.swbt.controller_type",
            str,
            "pro-controller",
            choices=("pro-controller", "joy-con-l", "joy-con-r"),
        ),
        "controller.swbt.adapter": SettingField(
            "controller.swbt.adapter",
            (str, type(None)),
            None,
        ),
        "controller.swbt.key_store_path": SettingField(
            "controller.swbt.key_store_path",
            (str, type(None)),
            None,
        ),
        "controller.swbt.connect_timeout_sec": SettingField(
            "controller.swbt.connect_timeout_sec",
            float,
            30.0,
        ),
        "controller.swbt.report_period_us": SettingField(
            "controller.swbt.report_period_us",
            (int, type(None)),
            8000,
        ),
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
        "logging.file_max_bytes": SettingField("logging.file_max_bytes", int, 10 * 1024 * 1024),
        "logging.file_backup_count": SettingField("logging.file_backup_count", int, 3),
        "logging.file_retention_days": SettingField("logging.file_retention_days", int, 14),
        "logging.run_retention_days": SettingField("logging.run_retention_days", int, 30),
        "logging.command_debug_enabled": SettingField(
            "logging.command_debug_enabled",
            bool,
            False,
        ),
        "gui.window_size_preset": SettingField("gui.window_size_preset", str, "full_hd"),
        "gui.preview_touch_enabled": SettingField("gui.preview_touch_enabled", bool, False),
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
        """設定 directory、schema、保存 file 名、load 厳格性を保持します。"""
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
            tmp_path.write_text(tomlkit.dumps(_drop_none(self.data)), encoding="utf-8")
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
        """既定 schema と `global.toml` を使う非 secret 設定 store を作成します。"""
        super().__init__(config_dir=config_dir, strict_load=False)


def _drop_none(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _drop_none(nested) for key, nested in value.items() if nested is not None}
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    return value
