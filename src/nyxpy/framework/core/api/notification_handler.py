from typing import List, Optional
import cv2
from .notification_interface import NotificationInterface

class NotificationHandler:
    def __init__(self, notifiers: Optional[List[NotificationInterface]] = None):
        self.notifiers = notifiers or []

    def add_notifier(self, notifier: NotificationInterface):
        self.notifiers.append(notifier)

    def publish(self, text: str, img: Optional[cv2.Mat] = None) -> None:
        for notifier in self.notifiers:
            try:
                notifier.notify(text, img)
            except Exception as e:
                # 各notifier側でログ出力するため、ここではpass
                pass
