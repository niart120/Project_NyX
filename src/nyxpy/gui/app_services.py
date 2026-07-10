"""GUI 起動時に共有する application service。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from nyxpy.framework.core.hardware.capture_source import WindowCaptureSourceConfig
from nyxpy.framework.core.hardware.device_discovery import (
    DUMMY_DEVICE_NAME,
    DeviceDiscoveryResult,
    DeviceDiscoveryService,
    WindowDiscoveryResult,
)
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig
from nyxpy.framework.core.hardware.swbt.diagnostics import LoggerDiagnosticsWriter
from nyxpy.framework.core.hardware.swbt.discovery import (
    SwbtAdapterDiscoveryService,
    SwbtAdapterView,
    resolve_adapter,
)
from nyxpy.framework.core.hardware.swbt.factory import SwbtControllerOutputPortFactory
from nyxpy.framework.core.hardware.swbt.session import is_swbt_status_connected
from nyxpy.framework.core.hardware.window_discovery import WindowInfo, resolve_window
from nyxpy.framework.core.io.controller_config import controller_config_from_settings
from nyxpy.framework.core.io.device_factories import (
    FrameSourcePortFactory,
)
from nyxpy.framework.core.io.ports import ControllerOutputPort, FrameSourcePort
from nyxpy.framework.core.logger import create_default_logging
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.notifications.notification_handler import (
    create_notification_handler_from_settings,
)
from nyxpy.framework.core.runtime.builder import (
    MacroRuntimeBuilder,
    create_device_runtime_builder,
)
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings
from nyxpy.gui.capture_availability import is_ponkan_capture_available
from nyxpy.gui.macro_catalog import MacroCatalog


@dataclass(frozen=True)
class SettingsApplyOutcome:
    """設定反映後の変更範囲と再接続結果。"""

    changed_keys: frozenset[str]
    builder_replaced: bool
    frame_source_changed: bool
    preview_frame_source: FrameSourcePort | None
    manual_controller: ControllerOutputPort | None
    preview_error: BaseException | None = None
    manual_controller_error: BaseException | None = None
    deferred: bool = False


@dataclass(frozen=True, slots=True)
class SwbtControllerStatusView:
    """GUI 表示用の swbt controller status。"""

    connected: bool
    controller_type: str
    adapter: str
    message: str


PONKAN_FRAME_SOURCE_SETTING_KEYS = frozenset(
    {
        "capture_provider",
        "capture_device_profile",
        "ponkan_backend",
        "ponkan_raw_slots",
        "ponkan_output_queue_size",
        "ponkan_drop_policy",
        "ponkan_poll_interval",
        "ponkan_read_timeout",
        "ponkan_collect_timing",
        "n3dsxl_hd_aspect_box_enabled",
    }
)

FRAME_SOURCE_SETTING_KEYS = (
    frozenset(
        {
            "capture_source_type",
            "capture_device",
            "capture_window_title",
            "capture_window_identifier",
            "capture_window_match_mode",
            "capture_backend",
            "capture_fps",
            "capture_aspect_box_enabled",
        }
    )
    | PONKAN_FRAME_SOURCE_SETTING_KEYS
)

CONTROLLER_SETTING_KEYS = frozenset(
    {
        "controller.backend",
        "controller.serial.device",
        "controller.serial.baudrate",
        "controller.serial.protocol",
        "controller.swbt.adapter",
        "controller.swbt.controller_type",
        "controller.swbt.key_store_path",
        "controller.swbt.connect_timeout_sec",
        "controller.swbt.report_period_us",
    }
)

RUNTIME_BUILDER_SETTING_KEYS = (
    FRAME_SOURCE_SETTING_KEYS
    | CONTROLLER_SETTING_KEYS
    | frozenset(
        {
            "runtime.allow_dummy",
            "logging.command_debug_enabled",
        }
    )
)


class GuiAppServices:
    """GUI が共有する registry、runtime builder、settings、logging を管理します。"""

    def __init__(self, *, project_root: Path) -> None:
        """Project root から設定、ログ、macro catalog、runtime builder を構築します。"""
        self.project_root = Path(project_root)
        config_dir = self.project_root / ".nyxpy"
        self.global_settings = GlobalSettings(config_dir=config_dir)
        self.secrets_settings = SecretsSettings(config_dir=config_dir)
        self.logging = create_default_logging(
            base_dir=self.project_root / "logs",
            console_enabled=False,
            file_level=str(self.global_settings.get("logging.file_level", "DEBUG")),
            file_max_bytes=int(
                self.global_settings.get("logging.file_max_bytes", 10 * 1024 * 1024)
            ),
            file_backup_count=int(self.global_settings.get("logging.file_backup_count", 3)),
            file_retention_days=int(self.global_settings.get("logging.file_retention_days", 14)),
            run_retention_days=int(self.global_settings.get("logging.run_retention_days", 30)),
        )
        self.logger = self.logging.logger
        self.device_discovery = DeviceDiscoveryService(logger=self.logger)
        self.swbt_adapter_discovery = SwbtAdapterDiscoveryService()
        self.swbt_controller_factory = SwbtControllerOutputPortFactory(
            diagnostics_writer=LoggerDiagnosticsWriter(self.logger)
        )
        self.ponkan_capture_available = is_ponkan_capture_available()
        self.registry = MacroRegistry(project_root=self.project_root)
        self.macro_catalog = MacroCatalog(self.registry)
        self.runtime_builder: MacroRuntimeBuilder | None = None
        self._last_settings: dict[str, Any] | None = None
        self._last_secrets: dict[str, Any] | None = None
        self._builder_settings: dict[str, Any] | None = None
        self._builder_secrets: dict[str, Any] | None = None
        self._active_frame_source_key: tuple[object, ...] | None = None
        self._active_swbt_config: SwbtControllerConfig | None = None
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

    def discard_manual_controller(self, controller: ControllerOutputPort | None) -> None:
        """GUI が解放した manual controller を runtime builder cache から外す。"""
        if self.runtime_builder is not None:
            self.runtime_builder.discard_manual_controller(controller)

    def apply_settings(self, *, is_run_active: bool = False) -> SettingsApplyOutcome:
        self._discard_unavailable_connection_settings()
        current_settings = deepcopy(self.global_settings.data)
        current_secrets = deepcopy(self.secrets_settings.data)
        changed_keys = _changed_keys(self._last_settings, current_settings) | _changed_keys(
            self._last_secrets, current_secrets
        )
        if self._last_settings is not None or self._last_secrets is not None:
            self._log_setting_changes(changed_keys)
            self._apply_logging_settings(changed_keys)

        builder_changed_keys = (
            _changed_keys(self._builder_settings, current_settings) & RUNTIME_BUILDER_SETTING_KEYS
        ) | _changed_keys(self._builder_secrets, current_secrets)
        builder_needs_update = self.runtime_builder is None or bool(builder_changed_keys)
        frame_source_needs_update = self.runtime_builder is None or bool(
            FRAME_SOURCE_SETTING_KEYS & builder_changed_keys
        )
        manual_controller_needs_update = self.runtime_builder is None or bool(
            CONTROLLER_SETTING_KEYS & builder_changed_keys
        )
        controller_config_changed = bool(CONTROLLER_SETTING_KEYS & builder_changed_keys)
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
            self._replace_runtime_builder(
                keep_preview_frame_source=not frame_source_needs_update,
                keep_manual_controller=not manual_controller_needs_update,
            )
            builder_replaced = True
            if controller_config_changed:
                self._active_swbt_config = None
            builder = self.runtime_builder
            if builder is None:
                raise RuntimeError("runtime builder was not created")
            if frame_source_needs_update:
                try:
                    preview_frame_source = builder.frame_source_for_preview()
                except Exception as exc:
                    preview_error = exc
                    self.logger.technical(
                        "WARNING",
                        "GUI preview frame source startup failed.",
                        component="GuiAppServices",
                        event="configuration.preview_failed",
                        exc=exc,
                    )
            if manual_controller_needs_update and not _uses_swbt_controller(current_settings):
                try:
                    manual_controller = builder.controller_output_for_manual_input()
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
            self.swbt_controller_factory.close()
        except Exception as exc:
            self.logger.technical(
                "WARNING",
                "swbt controller factory cleanup failed.",
                component="GuiAppServices",
                event="resource.cleanup_failed",
                exc=exc,
            )
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

    def _replace_runtime_builder(
        self,
        *,
        keep_preview_frame_source: bool = False,
        keep_manual_controller: bool = False,
    ) -> None:
        previous_builder = self.runtime_builder
        controller_config = controller_config_from_settings(
            self.global_settings.data,
            workspace_root=self.project_root,
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
            controller_config=controller_config,
            swbt_controller_factory=self.swbt_controller_factory,
            frame_source_factory=frame_factory,
            capture_name=self.global_settings.get("capture_device"),
            notification_handler=notification_handler,
            logger=self.logger,
            settings=self.global_settings.data,
            lifetime_allow_dummy=True,
        )
        self._active_frame_source_key = _frame_source_key(self.global_settings.data)
        if previous_builder is not None:
            _transfer_lifetime_resources(
                previous_builder,
                self.runtime_builder,
                keep_preview_frame_source=keep_preview_frame_source,
                keep_manual_controller=keep_manual_controller,
            )
            self._shutdown_builder(previous_builder)

    def refresh_swbt_adapters(self) -> tuple[SwbtAdapterView, ...]:
        """Swbt adapter 候補を列挙する。pair / reconnect は行わない。"""
        try:
            return self.swbt_adapter_discovery.list_adapters()
        except Exception as exc:
            self.logger.technical(
                "WARNING",
                "swbt adapter refresh failed.",
                component="GuiAppServices",
                event="swbt.adapter_refresh_failed",
                exc=exc,
            )
            raise

    def pair_swbt(self) -> SwbtControllerStatusView:
        """現在設定で swbt pairing を明示実行する。"""
        return self.pair_swbt_prepared(self.canonicalize_swbt_adapter())

    def pair_swbt_prepared(
        self,
        config: SwbtControllerConfig,
    ) -> SwbtControllerStatusView:
        """列挙済みcanonical configでpairingを1回だけ実行する。"""
        try:
            self.swbt_controller_factory.pair(
                config,
                timeout_sec=config.connect_timeout_sec,
            )
            view = self._connected_swbt_status(config, operation="pair")
        except Exception:
            self._active_swbt_config = None
            raise
        self._active_swbt_config = config
        return view

    def reconnect_swbt(self) -> SwbtControllerStatusView:
        """現在設定で swbt reconnect を明示実行する。"""
        return self.reconnect_swbt_prepared(self.canonicalize_swbt_adapter())

    def reconnect_swbt_prepared(
        self,
        config: SwbtControllerConfig,
    ) -> SwbtControllerStatusView:
        """列挙済みcanonical configでreconnectを1回だけ実行する。"""
        try:
            self.swbt_controller_factory.reconnect(
                config,
                timeout_sec=config.connect_timeout_sec,
            )
            view = self._connected_swbt_status(config, operation="reconnect")
        except Exception:
            self._active_swbt_config = None
            raise
        self._active_swbt_config = config
        return view

    def disconnect_swbt(self) -> None:
        """Factory-managed swbt session を閉じる。"""
        config = self._active_swbt_config or self._swbt_controller_config()
        self.swbt_controller_factory.disconnect(config)
        self._active_swbt_config = None

    def swbt_status(self) -> SwbtControllerStatusView | None:
        """Factory-managed swbt session の状態を GUI DTO として返す。"""
        config = self._active_swbt_config or self._swbt_controller_config()
        status = self.swbt_controller_factory.status(config)
        if status is None:
            return None
        return _swbt_status_view(config, status)

    def canonicalize_swbt_adapter(self) -> SwbtControllerConfig:
        """現在の adapter name/alias を列挙結果の canonical name へ正規化する。"""
        config = self._swbt_controller_config()
        resolved = resolve_adapter(config.adapter, self.refresh_swbt_adapters())
        if resolved.name == config.adapter:
            return config
        self.global_settings.set("controller.swbt.adapter", resolved.name)
        return replace(config, adapter=resolved.name)

    def _connected_swbt_status(
        self,
        config: SwbtControllerConfig,
        *,
        operation: str,
    ) -> SwbtControllerStatusView:
        status = self.swbt_controller_factory.status(config)
        if status is None:
            raise RuntimeError(f"swbt {operation} completed without a factory status")
        view = _swbt_status_view(config, status)
        if not view.connected:
            raise RuntimeError(f"swbt {operation} did not connect: {view.message}")
        return view

    def _swbt_controller_config(self) -> SwbtControllerConfig:
        config = controller_config_from_settings(
            self.global_settings.data,
            workspace_root=self.project_root,
        )
        if not isinstance(config, SwbtControllerConfig):
            raise ConfigurationError(
                "swbt backend is not selected",
                code="NYX_SWBT_BACKEND_NOT_SELECTED",
                component="GuiAppServices",
            )
        return config

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

    def _discard_unavailable_connection_settings(self) -> None:
        discarded_keys: list[str] = []
        source_type = str(self.global_settings.get("capture_source_type", "camera") or "camera")
        if source_type == "capture" and not self._is_ponkan_capture_available():
            self.global_settings.set("capture_source_type", "camera")
            self.logger.user(
                "INFO",
                "ponkan-python が未導入のためキャプチャ入力をカメラへ戻しました。",
                component="GuiAppServices",
                event="configuration.connection_discarded",
                extra={
                    "keys": "capture_source_type",
                    "reason": "ponkan_unavailable",
                },
            )

        discovery = getattr(self, "device_discovery", None)
        detect = getattr(discovery, "detect", None)
        if not callable(detect):
            return
        result = detect(timeout_sec=2.0)
        if not isinstance(result, DeviceDiscoveryResult):
            return

        serial_device = str(self.global_settings.get("controller.serial.device", "") or "").strip()
        if (
            serial_device
            and serial_device != DUMMY_DEVICE_NAME
            and not result.timed_out
            and not _has_discovery_error(result, "serial")
            and not _serial_exists(result, serial_device)
        ):
            self.global_settings.set("controller.serial.device", "")
            discarded_keys.append("controller.serial.device")

        if source_type == "window":
            discarded_keys.extend(self._discard_unavailable_window_settings())
        elif source_type == "camera":
            capture_device = str(self.global_settings.get("capture_device", "") or "").strip()
            if (
                capture_device
                and capture_device != DUMMY_DEVICE_NAME
                and not result.timed_out
                and not _has_discovery_error(result, "capture")
                and not _capture_exists(result, capture_device)
            ):
                self.global_settings.set("capture_device", "")
                discarded_keys.append("capture_device")

        if discarded_keys:
            self.logger.user(
                "INFO",
                f"利用できない接続設定を破棄しました: {', '.join(discarded_keys)}",
                component="GuiAppServices",
                event="configuration.connection_discarded",
                extra={"keys": ", ".join(discarded_keys)},
            )

    def _is_ponkan_capture_available(self) -> bool:
        value = getattr(self, "ponkan_capture_available", None)
        if value is None:
            return is_ponkan_capture_available()
        return bool(value)

    def _discard_unavailable_window_settings(self) -> list[str]:
        title = str(self.global_settings.get("capture_window_title", "") or "").strip()
        identifier = str(self.global_settings.get("capture_window_identifier", "") or "").strip()
        if not title and not identifier:
            return []
        windows_result = self._detect_window_sources_for_stale_check()
        if windows_result is None or windows_result.failed:
            return []
        windows = windows_result.window_sources
        if _window_exists(
            windows,
            title=title,
            identifier=identifier,
            match_mode=str(
                self.global_settings.get("capture_window_match_mode", "exact") or "exact"
            ),
        ):
            return []
        discarded_keys: list[str] = []
        if title:
            self.global_settings.set("capture_window_title", "")
            discarded_keys.append("capture_window_title")
        if identifier:
            self.global_settings.set("capture_window_identifier", "")
            discarded_keys.append("capture_window_identifier")
        return discarded_keys

    def _detect_window_sources_for_stale_check(self) -> WindowDiscoveryResult | None:
        detect_with_result = getattr(self.device_discovery, "detect_window_sources_result", None)
        if callable(detect_with_result):
            try:
                return detect_with_result(timeout_sec=2.0)
            except Exception as exc:
                self.logger.technical(
                    "WARNING",
                    "Window source discovery failed while checking stale settings.",
                    component="GuiAppServices",
                    event="configuration.connection_discovery_failed",
                    exc=exc,
                )
                return WindowDiscoveryResult(failed=True)
        detect_windows = getattr(self.device_discovery, "detect_window_sources", None)
        if not callable(detect_windows):
            return None
        try:
            windows = detect_windows(timeout_sec=2.0)
        except Exception as exc:
            self.logger.technical(
                "WARNING",
                "Window source discovery failed while checking stale settings.",
                component="GuiAppServices",
                event="configuration.connection_discovery_failed",
                exc=exc,
            )
            return WindowDiscoveryResult(failed=True)
        return WindowDiscoveryResult(window_sources=windows)

    def _log_setting_changes(self, changed_keys: set[str]) -> None:
        if {"controller.serial.device", "controller.serial.baudrate"} & changed_keys:
            serial_identifier = str(self.global_settings.get("controller.serial.device", "") or "")
            discovery = getattr(self, "device_discovery", None)
            display_name = getattr(discovery, "serial_display_name", None)
            serial_display = (
                str(display_name(serial_identifier))
                if callable(display_name)
                else serial_identifier
            )
            self.logger.user(
                "INFO",
                f"シリアルデバイス設定を更新しました: {serial_display} ({self.global_settings.get('controller.serial.baudrate', 9600)} bps)",
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
        if "controller.serial.protocol" in changed_keys:
            ProtocolFactory.create_protocol(
                self.global_settings.get("controller.serial.protocol", "CH552")
            )
            self.logger.user(
                "INFO",
                f"コントローラープロトコルを切り替えました: {self.global_settings.get('controller.serial.protocol', 'CH552')}",
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

    def _apply_logging_settings(self, changed_keys: set[str]) -> None:
        if "logging.file_level" in changed_keys:
            self.logging.set_file_level(
                str(self.global_settings.get("logging.file_level", "DEBUG"))
            )


def _changed_keys(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> set[str]:
    if previous is None:
        return set(_flatten_keys(current))
    keys = set(_flatten_keys(previous)) | set(_flatten_keys(current))
    return {key for key in keys if _dotted_get(previous, key) != _dotted_get(current, key)}


def _serial_exists(result: DeviceDiscoveryResult, identifier: str) -> bool:
    return any(str(device.identifier) == identifier for device in result.serial_devices)


def _capture_exists(result: DeviceDiscoveryResult, name: str) -> bool:
    return any(device.name == name for device in result.capture_devices)


def _window_exists(
    windows: tuple[WindowInfo, ...],
    *,
    title: str,
    identifier: str,
    match_mode: str,
) -> bool:
    try:
        resolve_window(
            windows,
            WindowCaptureSourceConfig(
                title_pattern=title,
                identifier=identifier or None,
                match_mode="contains" if match_mode == "contains" else "exact",
            ),
        )
    except ConfigurationError:
        return False
    return True


def _has_discovery_error(result: DeviceDiscoveryResult, device_type: str) -> bool:
    return any(error.startswith(f"{device_type}:") for error in result.errors)


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
    if key in mapping:
        return mapping[key]
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
    if source_type == "capture":
        return (
            "capture",
            _dotted_get(settings, "capture_provider", "ponkan"),
            _dotted_get(settings, "capture_device_profile", "n3dsxl"),
            _dotted_get(settings, "ponkan_backend", "auto"),
            _dotted_get(settings, "ponkan_raw_slots", 2),
            _dotted_get(settings, "ponkan_output_queue_size", 2),
            _dotted_get(settings, "ponkan_drop_policy", "drop_oldest"),
            _dotted_get(settings, "ponkan_poll_interval", 0.004),
            _dotted_get(settings, "ponkan_read_timeout", 1.0),
            _dotted_get(settings, "ponkan_collect_timing", False),
            _dotted_get(settings, "n3dsxl_hd_aspect_box_enabled", True),
        )
    return (
        "camera",
        _normalize_name(_dotted_get(settings, "capture_device", "")),
        capture_fps,
        aspect_box_enabled,
    )


def _transfer_lifetime_resources(
    previous_builder: MacroRuntimeBuilder,
    next_builder: MacroRuntimeBuilder,
    *,
    keep_preview_frame_source: bool,
    keep_manual_controller: bool,
) -> None:
    if keep_preview_frame_source and getattr(previous_builder, "_preview_frame_source", None):
        callbacks = previous_builder.detach_frame_source_shutdown_callbacks()
        next_builder.attach_preview_frame_source(previous_builder.detach_preview_frame_source())
        next_builder.extend_frame_source_shutdown_callbacks(callbacks)
    if keep_manual_controller and getattr(previous_builder, "_manual_controller", None):
        callbacks = previous_builder.detach_controller_shutdown_callbacks()
        next_builder.attach_manual_controller(previous_builder.detach_manual_controller())
        next_builder.extend_controller_shutdown_callbacks(callbacks)


def _swbt_status_view(
    config: SwbtControllerConfig,
    status: object,
) -> SwbtControllerStatusView:
    connected = is_swbt_status_connected(status)
    connection_state = getattr(status, "connection_state", None)
    message = str(connection_state or ("connected" if connected else "disconnected"))
    return SwbtControllerStatusView(
        connected=connected,
        controller_type=config.model.settings_value,
        adapter=config.adapter or "",
        message=message,
    )


def _uses_swbt_controller(settings: Mapping[str, Any]) -> bool:
    return _dotted_get(settings, "controller.backend", "serial") == "swbt"
