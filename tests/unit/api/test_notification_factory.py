from nyxpy.framework.core.api.notification_handler import create_notification_handler_from_settings
from nyxpy.framework.core.api.discord_notification import DiscordNotification
from nyxpy.framework.core.api.bluesky_notification import BlueskyNotification

class DummySettings:
    def __init__(self, d): self.d = d
    def get(self, k, default=None): return self.d.get(k, default)

def test_create_notification_handler_from_settings():
    # Discordのみ
    s = DummySettings({"notification.discord.enabled": True, "notification.discord.webhook_url": "url1"})
    handler = create_notification_handler_from_settings(s)
    assert any(isinstance(n, DiscordNotification) for n in handler.notifiers)
    # Blueskyのみ
    s = DummySettings({"notification.bluesky.enabled": True, "notification.bluesky.identifier": "id1", "notification.bluesky.password": "pass1"})
    handler = create_notification_handler_from_settings(s)
    assert any(isinstance(n, BlueskyNotification) for n in handler.notifiers)
    # どちらも無効
    s = DummySettings({})
    handler = create_notification_handler_from_settings(s)
    assert handler is None
