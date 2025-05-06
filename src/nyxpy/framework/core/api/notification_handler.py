from typing import List, Optional
import cv2
from .notification_interface import NotificationInterface
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings
from .discord_notification import DiscordNotification
from .bluesky_notification import BlueskyNotification

class NotificationHandler:
    def __init__(self, notifiers: Optional[List[NotificationInterface]] = None):
        self.notifiers = notifiers or []

    def add_notifier(self, notifier: NotificationInterface):
        self.notifiers.append(notifier)

    def publish(self, text: str, img: Optional[cv2.typing.MatLike] = None) -> None:
        for notifier in self.notifiers:
            try:
                notifier.notify(text, img)
            except Exception as e:
                # 各notifier側でログ出力するため、ここではpass
                pass

def create_notification_handler_from_settings(secrets: SecretsSettings):
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
        webhook_url = secrets.get("notification.discord.webhook_url", "")
        if webhook_url:
            notifiers.append(DiscordNotification(webhook_url))
    
    # Bluesky通知の設定
    if secrets.get("notification.bluesky.enabled", False):
        identifier = secrets.get("notification.bluesky.identifier", "")
        password = secrets.get("notification.bluesky.password", "")
        if identifier and password:
            notifiers.append(BlueskyNotification(identifier, password))
    
    if not notifiers:
        return None
    return NotificationHandler(notifiers)
