import io

import cv2
import requests

from nyxpy.framework.core.logger import LoggerPort, NullLoggerPort

from .notification_interface import NotificationInterface


class DiscordNotification(NotificationInterface):
    def __init__(self, webhook_url: str, logger: LoggerPort | None = None):
        self.webhook_url = webhook_url
        self.logger = logger or NullLoggerPort()

    def notify(self, text: str, img: cv2.Mat | None = None) -> None:
        try:
            if img is not None:
                # 画像をメモリ上でエンコードし、そのまま送信
                ret, buf = cv2.imencode(".png", img)
                if not ret:
                    raise ValueError("画像のエンコードに失敗しました")
                file_obj = io.BytesIO(buf.tobytes())
                file_obj.name = "image.png"  # Discordはファイル名が必要
                files = {"file": (file_obj.name, file_obj, "image/png")}
                data = {"content": text}
                requests.post(self.webhook_url, data=data, files=files, timeout=5)
            else:
                data = {"content": text}
                requests.post(self.webhook_url, data=data, timeout=5)
        except Exception as exc:
            self.logger.technical(
                "ERROR",
                "Discord notification failed",
                component="DiscordNotification",
                event="notification.failed",
                extra={"notifier": "discord"},
                exc=exc,
            )
