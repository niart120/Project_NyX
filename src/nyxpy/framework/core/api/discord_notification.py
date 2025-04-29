import requests
from typing import Optional
import cv2
from .notification_interface import NotificationInterface

class DiscordNotification(NotificationInterface):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def notify(self, text: str, img: Optional[cv2.Mat] = None) -> None:
        try:
            if img is not None:
                # 画像がある場合は一時ファイルとして保存して送信
                import tempfile
                import numpy as np
                import os
                _, tmp_path = tempfile.mkstemp(suffix='.png')
                cv2.imwrite(tmp_path, img)
                with open(tmp_path, 'rb') as f:
                    files = {'file': f}
                    data = {'content': text}
                    requests.post(self.webhook_url, data=data, files=files, timeout=5)
                os.remove(tmp_path)
            else:
                data = {'content': text}
                requests.post(self.webhook_url, data=data, timeout=5)
        except Exception as e:
            # エラーはログ出力のみ
            import logging
            logging.getLogger(__name__).error(f"Discord通知失敗: {e}")
