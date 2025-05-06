from typing import Optional
import cv2
import requests
from .notification_interface import NotificationInterface

from nyxpy.framework.core.logger.log_manager import log_manager

class BlueskyNotification(NotificationInterface):
    def __init__(self, identifier: str, password: str):
        self.identifier = identifier
        self.password = password
        self.access_token = None
        self.refresh_token = None
        self.base_url = "https://bsky.social"
        self._authenticate()

    def _authenticate(self):
        try:
            response = requests.post(f"{self.base_url}/xrpc/com.atproto.server.createSession", json={
                "identifier": self.identifier,
                "password": self.password
            }, timeout=5)
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("accessJwt")
            self.refresh_token = data.get("refreshJwt")
        except Exception as e:
            log_manager.log("ERROR", f"Bluesky認証失敗: {e}", component="BlueskyNotification")

    def _refresh_token(self):
        try:
            # リフレッシュトークンを使用してアクセストークンを更新
            response = requests.post(f"{self.base_url}/xrpc/com.atproto.server.refreshSession", json={
                "refreshJwt": self.refresh_token
            }, timeout=5)
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("accessJwt")
        except Exception as e:
            log_manager.log("ERROR", f"Blueskyトークン更新失敗: {e}", component="BlueskyNotification")

    # 画像をアップロードしてblob情報を返す
    def _upload_image(self, img: cv2.Mat) -> dict:
        # PNG形式にエンコード
        _, buf = cv2.imencode('.png', img)
        files = {'file': ('image.png', buf.tobytes(), 'image/png')}
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(
            f"{self.base_url}/xrpc/com.atproto.repo.uploadBlob",
            headers=headers,
            files=files,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        # JSONレスポンスの構造に応じてblob情報を取得
        return data.get('blob') or data.get('data', {}).get('blob')

    def notify(self, text: str, img: Optional[cv2.Mat] = None) -> None:
        if not self.access_token:
            self._authenticate()
        try:
            # 画像がある場合は先にアップロードしてblobを取得
            data = {
                "collection": "app.bsky.feed.post",
                "record": {
                    "text": text,
                    "createdAt": "2025-05-06T00:00:00.000Z"
                }
            }
            if img is not None:
                blob = self._upload_image(img)
                # 画像のアスペクト比を指定
                h, w = img.shape[0], img.shape[1]
                data['record']['embed'] = {
                    "$type": "app.bsky.embed.images",
                    "images": [
                        {
                            "alt": "",
                            "image": blob,
                            "aspectRatio": {"width": w, "height": h}
                        }
                    ]
                }
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.post(
                f"{self.base_url}/xrpc/com.atproto.repo.createRecord",
                json=data,
                headers=headers,
                timeout=5
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 401:  # トークン期限切れ
                self._refresh_token()
                self.notify(text, img)
            else:
                log_manager.log("ERROR", f"Bluesky通知失敗: {http_err}", component="BlueskyNotification")
        except Exception as e:
            log_manager.log("ERROR", f"Bluesky通知失敗: {e}", component="BlueskyNotification")
