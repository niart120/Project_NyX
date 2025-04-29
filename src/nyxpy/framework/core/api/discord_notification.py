import requests
from typing import Optional
import cv2
import io
from .notification_interface import NotificationInterface
from nyxpy.framework.core.logger.log_manager import log_manager

class DiscordNotification(NotificationInterface):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def notify(self, text: str, img: Optional[cv2.Mat] = None) -> None:
        try:
            if img is not None:
                # 画像をメモリ上でエンコードし、そのまま送信
                ret, buf = cv2.imencode('.png', img)
                if not ret:
                    raise ValueError('画像のエンコードに失敗しました')
                file_obj = io.BytesIO(buf.tobytes())
                file_obj.name = 'image.png'  # Discordはファイル名が必要
                files = {'file': (file_obj.name, file_obj, 'image/png')}
                data = {'content': text}
                requests.post(self.webhook_url, data=data, files=files, timeout=5)
            else:
                data = {'content': text}
                requests.post(self.webhook_url, data=data, timeout=5)
        except Exception as e:
            log_manager.log("ERROR", f"Discord通知失敗: {e}", component="DiscordNotification")
