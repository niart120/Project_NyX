from typing import Protocol

import cv2

from nyxpy.framework.core.logger import LoggerPort, NullLoggerPort
from nyxpy.framework.core.settings.schema import SettingValue

from .bluesky_notification import BlueskyNotification
from .discord_notification import DiscordNotification
from .notification_interface import NotificationInterface


class NotificationHandler:
    def __init__(
        self,
        notifiers: list[NotificationInterface] | None = None,
        logger: LoggerPort | None = None,
    ):
        self.notifiers = notifiers or []
        self.logger = logger or NullLoggerPort()

    def add_notifier(self, notifier: NotificationInterface):
        self.notifiers.append(notifier)

    def publish(self, text: str, img: cv2.typing.MatLike | None = None) -> None:
        for notifier in self.notifiers:
            try:
                notifier.notify(text, img)
            except Exception as exc:
                self.logger.technical(
                    "WARNING",
                    "Notification failed",
                    component="NotificationHandler",
                    event="notification.failed",
                    extra={"notifier": type(notifier).__name__},
                    exc=exc,
                )


class NotificationSettings(Protocol):
    def get(self, key: str, default: SettingValue = None) -> SettingValue: ...

    def get_secret(self, key: str) -> str: ...


def create_notification_handler_from_settings(
    secrets: NotificationSettings,
    logger: LoggerPort | None = None,
):
    """
    SecretsSettingsオブジェクトから通知ハンドラーを作成します。
    通知の有効/無効設定や認証情報など、全ての通知関連設定はSecretsSettingsから取得します。

    Args:
        secrets: シークレット設定オブジェクト

    Returns:
        NotificationHandler: 通知ハンドラー、または設定が無効の場合はNone
    """
    notifiers = []

    # Discord通知の設定
    if secrets.get("notification.discord.enabled", False):
        webhook_url = secrets.get_secret("notification.discord.webhook_url")
        if webhook_url:
            notifiers.append(DiscordNotification(webhook_url, logger=logger))

    # Bluesky通知の設定
    if secrets.get("notification.bluesky.enabled", False):
        identifier = secrets.get_secret("notification.bluesky.identifier")
        password = secrets.get_secret("notification.bluesky.password")
        if identifier and password:
            notifiers.append(BlueskyNotification(identifier, password, logger=logger))

    if not notifiers:
        return None
    return NotificationHandler(notifiers, logger=logger)
