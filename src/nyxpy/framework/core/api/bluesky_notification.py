from datetime import datetime, timezone
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
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}", 
                       "Content-Type": "image/png"}
            response = requests.post(
                f"{self.base_url}/xrpc/com.atproto.repo.uploadBlob",
                headers=headers,
                data=buf.tobytes(),
                timeout=3
            )
            response.raise_for_status()
            data = response.json()
            return data.get('blob')
            
        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 401:  # トークン期限切れ
                log_manager.log("DEBUG", "トークン期限切れ。リフレッシュを試みます", component="BlueskyNotification")
                self._refresh_token()
                return self._upload_image(img)
            else:
                log_manager.log("ERROR", f"画像アップロード失敗: {http_err}", component="BlueskyNotification")
                if hasattr(http_err.response, 'text'):
                    log_manager.log("ERROR", f"レスポンス詳細: {http_err.response.text}", component="BlueskyNotification")
                return None
        except Exception as e:
            log_manager.log("ERROR", f"画像アップロード失敗: {e}", component="BlueskyNotification")
            return None

    def notify(self, text: str, img: Optional[cv2.Mat] = None) -> None:
        if not self.access_token:
            self._authenticate()
        try:

            data = {
                "repo": self.identifier,
                "collection": "app.bsky.feed.post",
                "record": {
                    "text": text,
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            }
            if img is not None:
                # 画像がある場合は先にアップロードしてblobを取得
                blob = self._upload_image(img)
                # 画像のアスペクト比を指定
                h, w = img.shape[0], img.shape[1]
                # 画像のアップロードが成功した場合のみ、embedを追加
                if blob:
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
            headers = {"Authorization": f"Bearer {self.access_token}",
                       "Content-Type": "application/json"}
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
