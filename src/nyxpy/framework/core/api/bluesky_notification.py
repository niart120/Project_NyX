from typing import Optional
import cv2
from .notification_interface import NotificationInterface

class BlueskyNotification(NotificationInterface):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def notify(self, text: str, img: Optional[cv2.Mat] = None) -> None:
        try:
            # Blueskyは画像送信未対応想定。テキストのみ送信。
            import requests
            data = {'text': text}
            requests.post(self.webhook_url, json=data, timeout=5)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Bluesky通知失敗: {e}")
