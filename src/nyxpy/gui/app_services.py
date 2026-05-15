from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nyxpy.framework.core.api.notification_handler import create_notification_handler_from_settings
from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.io.device_factories import (
    ControllerOutputPortFactory,
    FrameSourcePortFactory,
)
from nyxpy.framework.core.io.ports import ControllerOutputPort, FrameSourcePort
from nyxpy.framework.core.logger import create_default_logging
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.runtime.builder import (
    MacroRuntimeBuilder,
    create_device_runtime_builder,
)
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings
from nyxpy.gui.macro_catalog import MacroCatalog


@dataclass(frozen=True)
class SettingsApplyOutcome:
    changed_keys: frozenset[str]
    builder_replaced: bool
    frame_source_changed: bool
    preview_frame_source: FrameSourcePort | None
    manual_controller: ControllerOutputPort | None
    preview_error: BaseException | None = None
    manual_controller_error: BaseException | None = None
    deferred: bool = False


FRAME_SOURCE_SETTING_KEYS = frozenset(
    {
        "capture_source_type",
        "capture_device",
        "capture_window_title",
        "capture_window_identifier",
        "capture_window_match_mode",
        "capture_backend",
        "capture_region",
        "capture_region.left",
        "capture_region.top",
        "capture_region.width",
        "capture_region.height",
        "capture_fps",
        "capture_aspect_box_enabled",
    }
)

CONTROLLER_SETTING_KEYS = frozenset(
    {
        "serial_device",
        "serial_baud",
        "serial_protocol",
    }
)

RUNTIME_BUILDER_SETTING_KEYS = FRAME_SOURCE_SETTING_KEYS | CONTROLLER_SETTING_KEYS | frozenset(
    {
        "runtime.allow_dummy",
    }
)


class GuiAppServices:
    def __init__(self, *, project_root: Path) -> None:
        self.project_root = Path(project_root)
        config_dir = self.project_root / ".nyxpy"
        self.logging = create_default_logging(
            base_dir=self.project_root / "logs",
            console_enabled=False,
        )
        self.logger = self.logging.logger
        self.global_settings = GlobalSettings(config_dir=config_dir)
        self.secrets_settings = SecretsSettings(config_dir=config_dir)
        self.device_discovery = DeviceDiscoveryService(logger=self.logger)
        self.registry = MacroRegistry(project_root=self.project_root)
        self.macro_catalog = MacroCatalog(self.registry)
        self.runtime_builder: MacroRuntimeBuilder | None = None
        self._last_settings: dict[str, Any] | None = None
        self._last_secrets: dict[str, Any] | None = None
        self._builder_settings: dict[str, Any] | None = None
        self._builder_secrets: dict[str, Any] | None = None
        self._active_frame_source_key: tuple[object, ...] | None = None
        self._pending_settings_apply = False
        self._closed = False

    @property
    def close_wait_timeout_sec(self) -> float:
        value = self.global_settings.get("runtime.gui_close_wait_timeout_sec", 5.0)
        try:
            return float(value)
        except (TypeError, ValueError):
            self.logger.technical(
                "WARNING",
                "GUI close wait timeout setting is invalid.",
                component="GuiAppServices",
                event="configuration.invalid",
                extra={"value": str(value)},
            )
            return 5.0

    def create_runtime_builder(self) -> MacroRuntimeBuilder:
        if self.runtime_builder is None:
            self.apply_settings(is_run_active=False)
        if self.runtime_builder is None:
            self._replace_runtime_builder()
        assert self.runtime_builder is not None
        return self.runtime_builder

    def apply_settings(self, *, is_run_active: bool = False) -> SettingsApplyOutcome:
        current_settings = deepcopy(self.global_settings.data)
        current_secrets = deepcopy(self.secrets_settings.data)
        changed_keys = _changed_keys(self._last_settings, current_settings) | _changed_keys(
            self._last_secrets, current_secrets
        )
        if self._last_settings is not None or self._last_secrets is not None:
            self._log_setting_changes(changed_keys)

        builder_changed_keys = (
            _changed_keys(self._builder_settings, current_settings) & RUNTIME_BUILDER_SETTING_KEYS
        ) | _changed_keys(self._builder_secrets, current_secrets)
        builder_needs_update = self.runtime_builder is None or bool(builder_changed_keys)
        if builder_needs_update and is_run_active:
            self._pending_settings_apply = True
            self._last_settings = current_settings
            self._last_secrets = current_secrets
            return SettingsApplyOutcome(
                changed_keys=frozenset(changed_keys),
                builder_replaced=False,
                frame_source_changed=False,
                preview_frame_source=None,
                manual_controller=None,
                deferred=True,
            )

        previous_builder_exists = self.runtime_builder is not None
        previous_frame_source_key = self._active_frame_source_key
        preview_frame_source: FrameSourcePort | None = None
        manual_controller: ControllerOutputPort | None = None
        preview_error: BaseException | None = None
        manual_controller_error: BaseException | None = None
        builder_replaced = False

        if builder_needs_update:
            self._replace_runtime_builder()
            builder_replaced = True
            try:
                preview_frame_source = self.runtime_builder.frame_source_for_preview()
            except Exception as exc:
                preview_error = exc
                self.logger.technical(
                    "WARNING",
                    "GUI preview frame source startup failed.",
                    component="GuiAppServices",
                    event="configuration.preview_failed",
                    exc=exc,
                )
            try:
                manual_controller = self.runtime_builder.controller_output_for_manual_input()
            except Exception as exc:
                manual_controller_error = exc
                self.logger.technical(
                    "WARNING",
                    "GUI manual controller startup failed.",
                    component="GuiAppServices",
                    event="configuration.controller_failed",
                    exc=exc,
                )

        self._last_settings = current_settings
        self._last_secrets = current_secrets
        self._builder_settings = current_settings
        self._builder_secrets = current_secrets
        self._pending_settings_apply = False
        frame_source_changed = (
            previous_builder_exists
            and previous_frame_source_key != self._active_frame_source_key
            and bool(FRAME_SOURCE_SETTING_KEYS & builder_changed_keys)
        )
        return SettingsApplyOutcome(
            changed_keys=frozenset(changed_keys),
            builder_replaced=builder_replaced,
            frame_source_changed=frame_source_changed,
            preview_frame_source=preview_frame_source,
            manual_controller=manual_controller,
            preview_error=preview_error,
            manual_controller_error=manual_controller_error,
        )

    def flush_deferred_settings(self) -> SettingsApplyOutcome | None:
        if not self._pending_settings_apply:
            return None
        return self.apply_settings(is_run_active=False)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._shutdown_runtime_builder()
        try:
            self.logging.close()
        except Exception as exc:
            self.logger.technical(
                "WARNING",
                "Logging close failed.",
                component="GuiAppServices",
                event="resource.cleanup_failed",
                exc=exc,
            )

    def _replace_runtime_builder(self) -> None:
        previous_builder = self.runtime_builder
        protocol = ProtocolFactory.create_protocol(
            self.global_settings.get("serial_protocol", "CH552")
        )
        controller_factory = ControllerOutputPortFactory(
            discovery=self.device_discovery,
            protocol=protocol,
        )
        frame_factory = FrameSourcePortFactory(
            discovery=self.device_discovery,
            logger=self.logger,
        )
        notification_handler = create_notification_handler_from_settings(
            self.secrets_settings.snapshot(),
            logger=self.logger,
        )
        self.runtime_builder = create_device_runtime_builder(
            project_root=self.project_root,
            registry=self.registry,
            device_discovery=self.device_discovery,
            controller_output_factory=controller_factory,
            frame_source_factory=frame_factory,
            serial_name=self.global_settings.get("serial_device"),
            capture_name=self.global_settings.get("capture_device"),
            baudrate=self.global_settings.get("serial_baud", 9600),
            protocol=protocol,
            notification_handler=notification_handler,
            logger=self.logger,
            settings=self.global_settings.data,
            lifetime_allow_dummy=True,
        )
        self._active_frame_source_key = _frame_source_key(self.global_settings.data)
        if previous_builder is not None:
            self._shutdown_builder(previous_builder)

    def _shutdown_runtime_builder(self) -> None:
        if self.runtime_builder is None:
            return
        builder = self.runtime_builder
        self.runtime_builder = None
        self._shutdown_builder(builder)

    def _shutdown_builder(self, builder: MacroRuntimeBuilder) -> None:
        try:
            builder.shutdown()
        except Exception as exc:
            self.logger.technical(
                "WARNING",
                "Runtime builder cleanup failed.",
                component="GuiAppServices",
                event="resource.cleanup_failed",
                exc=exc,
            )

    def _log_setting_changes(self, changed_keys: set[str]) -> None:
        if {"serial_device", "serial_baud"} & changed_keys:
            self.logger.user(
                "INFO",
                f"シリアルデバイス設定を更新しました: {self.global_settings.get('serial_device')} ({self.global_settings.get('serial_baud', 9600)} bps)",
                component="GuiAppServices",
                event="configuration.changed",
            )
        if FRAME_SOURCE_SETTING_KEYS & changed_keys:
            self.logger.user(
                "INFO",
                f"キャプチャ入力設定を更新しました: {self.global_settings.get('capture_source_type', 'camera')}",
                component="GuiAppServices",
                event="configuration.changed",
            )
        if "serial_protocol" in changed_keys:
            ProtocolFactory.create_protocol(self.global_settings.get("serial_protocol", "CH552"))
            self.logger.user(
                "INFO",
                f"コントローラープロトコルを切り替えました: {self.global_settings.get('serial_protocol', 'CH552')}",
                component="GuiAppServices",
                event="configuration.changed",
            )
        if {
            "notification.discord.enabled",
            "notification.bluesky.enabled",
        } & changed_keys:
            enabled_services = []
            if self.secrets_settings.get("notification.discord.enabled", False):
                enabled_services.append("Discord")
            if self.secrets_settings.get("notification.bluesky.enabled", False):
                enabled_services.append("Bluesky")
            if enabled_services:
                message = f"通知設定が変更されました。有効なサービス: {', '.join(enabled_services)}"
            else:
                message = "通知設定が変更されました。全てのサービスが無効です。"
            self.logger.user(
                "INFO",
                message,
                component="GuiAppServices",
                event="configuration.changed",
            )


def _changed_keys(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> set[str]:
    if previous is None:
        return set(_flatten_keys(current))
    keys = set(_flatten_keys(previous)) | set(_flatten_keys(current))
    return {key for key in keys if _dotted_get(previous, key) != _dotted_get(current, key)}


def _flatten_keys(mapping: Mapping[str, Any], prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in mapping.items():
        dotted_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            keys.update(_flatten_keys(value, dotted_key))
        else:
            keys.add(dotted_key)
    return keys


def _dotted_get(mapping: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value: Any = mapping
    for part in key.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return default
        value = value[part]
    return value


def _normalize_name(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _frame_source_key(settings: Mapping[str, Any]) -> tuple[object, ...]:
    source_type = _dotted_get(settings, "capture_source_type", "camera")
    capture_fps = _dotted_get(settings, "capture_fps")
    aspect_box_enabled = _dotted_get(settings, "capture_aspect_box_enabled", False)
    if source_type == "camera":
        return (
            "camera",
            _normalize_name(_dotted_get(settings, "capture_device", "")),
            capture_fps,
            aspect_box_enabled,
        )
    if source_type == "window":
        return (
            "window",
            _normalize_name(_dotted_get(settings, "capture_window_title", "")),
            _normalize_name(_dotted_get(settings, "capture_window_identifier", "")),
            _dotted_get(settings, "capture_window_match_mode", "exact"),
            _dotted_get(settings, "capture_backend", "auto"),
            capture_fps,
            aspect_box_enabled,
        )
    region = _dotted_get(settings, "capture_region") or {}
    if not isinstance(region, Mapping):
        region = {}
    return (
        source_type,
        _dotted_get(settings, "capture_backend", "auto"),
        region.get("left"),
        region.get("top"),
        region.get("width"),
        region.get("height"),
        capture_fps,
        aspect_box_enabled,
    )
