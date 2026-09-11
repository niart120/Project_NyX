"""swbt 接続画面で共有する設定解決と操作選択。"""

from dataclasses import dataclass
from pathlib import Path

from nyxpy.framework.core.hardware.swbt.config import (
    SwbtControllerConfig,
    resolve_controller_model,
    supported_controller_models,
)
from nyxpy.framework.core.hardware.swbt.errors import swbt_user_error_message
from nyxpy.framework.core.io.controller_config import controller_config_from_settings
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.schema import SettingValue


def swbt_type_updates(settings: GlobalSettings, controller_type: str) -> dict[str, SettingValue]:
    """種別変更時に既定プロファイルだけを追従させる。"""
    updates: dict[str, SettingValue] = {
        "controller.backend": "swbt",
        "controller.swbt.controller_type": controller_type,
    }
    current = str(settings.get("controller.swbt.profile_path", "") or "").replace("\\", "/")
    defaults = {model.default_profile_path().as_posix() for model in supported_controller_models()}
    if not current or current in defaults:
        updates["controller.swbt.profile_path"] = (
            resolve_controller_model(controller_type).default_profile_path().as_posix()
        )
    return updates


def resolve_swbt_selection(
    settings: GlobalSettings,
    *,
    workspace_root: Path | None,
    controller_type: str | None = None,
    adapter: str | None = None,
) -> SwbtControllerConfig:
    """保存せずに画面選択を既存の controller 設定へ解決する。"""
    selected_type = controller_type or str(
        settings.get("controller.swbt.controller_type", "pro-controller")
    )
    updates = swbt_type_updates(settings, selected_type)
    config = controller_config_from_settings(
        {
            "controller": {
                "backend": "swbt",
                "swbt": {
                    "controller_type": selected_type,
                    "adapter": adapter
                    if adapter is not None
                    else settings.get("controller.swbt.adapter"),
                    "profile_path": updates.get(
                        "controller.swbt.profile_path", settings.get("controller.swbt.profile_path")
                    ),
                    "connect_timeout_sec": settings.get(
                        "controller.swbt.connect_timeout_sec", 30.0
                    ),
                },
            },
        },
        workspace_root=workspace_root,
    )
    assert isinstance(config, SwbtControllerConfig)
    return config


@dataclass(frozen=True)
class SwbtActionView:
    """接続状態から決まる主操作と副操作。"""

    operation: str
    label: str
    enabled: bool
    repair: bool = False


def swbt_action_view(
    *,
    connected: bool,
    registered: bool,
    available: bool,
    operation: str | None = None,
    cancelling: bool = False,
) -> SwbtActionView:
    """設定画面と接続メニューで同じ操作を選択する。"""
    if operation == "disconnect":
        return SwbtActionView("disconnect", "切断中…", False)
    if operation is not None:
        return SwbtActionView(
            "cancel", "キャンセル中…" if cancelling else "キャンセル", not cancelling
        )
    if connected:
        return SwbtActionView("disconnect", "切断", available)
    if registered:
        return SwbtActionView("reconnect", "接続", available, repair=True)
    return SwbtActionView("pair", "ペアリング", available)


def swbt_error_message(error: BaseException) -> str:
    """ツールログの本文だけで各失敗理由とコードを読めるようにする。"""
    if isinstance(error, BaseExceptionGroup):
        return " / ".join(swbt_error_message(nested) for nested in error.exceptions)
    return swbt_user_error_message(error)
