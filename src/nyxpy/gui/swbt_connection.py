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
class SwbtAction:
    """接続操作部の各ボタンに割り当てる操作。"""

    operation: str
    label: str
    enabled: bool


def swbt_actions(
    *,
    connected: bool,
    registered: bool,
    available: bool,
    operation: str | None = None,
    cancelling: bool = False,
) -> tuple[SwbtAction, SwbtAction]:
    """左はペアリング、右は接続・切断とし、実行元をキャンセルにする。"""
    idle = available and operation is None
    pair = SwbtAction("pair", "ペアリング", idle and not connected)
    connection = SwbtAction(
        "disconnect" if connected else "reconnect",
        "切断" if connected else "接続",
        idle and (connected or registered),
    )
    cancel = SwbtAction("cancel", "キャンセル", not cancelling)
    if operation == "pair":
        pair = cancel
    elif operation in {"connect", "reconnect"}:
        connection = cancel
    elif operation == "disconnect":
        connection = SwbtAction("disconnect", "切断", False)
    return pair, connection


def swbt_error_message(error: BaseException) -> str:
    """ツールログの本文だけで各失敗理由とコードを読めるようにする。"""
    if isinstance(error, BaseExceptionGroup):
        return " / ".join(swbt_error_message(nested) for nested in error.exceptions)
    return swbt_user_error_message(error)
