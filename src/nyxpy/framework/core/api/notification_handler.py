from typing import List, Optional
import cv2
from .notification_interface import NotificationInterface
from nyxpy.framework.core.global_settings import GlobalSettings
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

def create_notification_handler_from_settings(settings: GlobalSettings):
    notifiers = []
    # Discord
    if settings.get("notification.discord.enabled", False):
        url = settings.get("notification.discord.webhook_url", "")
        if url:
            notifiers.append(DiscordNotification(url))
    # Bluesky
    if settings.get("notification.bluesky.enabled", False):
        url = settings.get("notification.bluesky.webhook_url", "")
        if url:
            notifiers.append(BlueskyNotification(url))
    if not notifiers:
        return None
    return NotificationHandler(notifiers)
