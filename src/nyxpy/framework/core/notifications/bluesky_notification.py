"""Bluesky への外部通知 adapter。"""

from datetime import UTC, datetime
from typing import Any

import cv2
import requests

from nyxpy.framework.core.logger import LoggerPort, NullLoggerPort

from .notifier import Notifier


class BlueskyNotification(Notifier):
    """Bluesky の atproto API へテキストと画像を投稿する通知 adapter。"""

    def __init__(self, identifier: str, password: str, logger: LoggerPort | None = None):
        """認証情報で session を作成し、投稿用 token を保持します。"""
        self.identifier = identifier
        self.password = password
        self.logger = logger or NullLoggerPort()
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.base_url = "https://bsky.social"
        self._authenticate()

    def _authenticate(self):
        try:
            response = requests.post(
                f"{self.base_url}/xrpc/com.atproto.server.createSession",
                json={"identifier": self.identifier, "password": self.password},
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("accessJwt")
            self.refresh_token = data.get("refreshJwt")
        except Exception as exc:
            self._log_failure("Bluesky authentication failed", exc)

    def _refresh_token(self):
        try:
            # リフレッシュトークンを使用してアクセストークンを更新
            response = requests.post(
                f"{self.base_url}/xrpc/com.atproto.server.refreshSession",
                json={"refreshJwt": self.refresh_token},
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("accessJwt")
        except Exception as exc:
            self._log_failure("Bluesky token refresh failed", exc)

    # 画像をアップロードしてblob情報を返す
    def _upload_image(self, img: cv2.typing.MatLike) -> dict[str, Any] | None:
        # PNG形式にエンコード
        _, buf = cv2.imencode(".png", img)

        try:
            headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "image/png"}
            response = requests.post(
                f"{self.base_url}/xrpc/com.atproto.repo.uploadBlob",
                headers=headers,
                data=buf.tobytes(),
                timeout=3,
            )
            response.raise_for_status()
            data = response.json()
            blob = data.get("blob")
            return blob if isinstance(blob, dict) else None

        except requests.exceptions.HTTPError as http_err:
            response = http_err.response
            if response is not None and response.status_code == 401:  # トークン期限切れ
                self.logger.technical(
                    "DEBUG",
                    "Bluesky token expired; refreshing",
                    component="BlueskyNotification",
                    event="notification.token_expired",
                )
                self._refresh_token()
                return self._upload_image(img)
            else:
                self._log_failure("Bluesky image upload failed", http_err)
                if response is not None:
                    self.logger.technical(
                        "ERROR",
                        "Bluesky image upload response detail",
                        component="BlueskyNotification",
                        event="notification.failed",
                        extra={"response": response.text},
                    )
                return None
        except Exception as exc:
            self._log_failure("Bluesky image upload failed", exc)
            return None

    def notify(self, text: str, img: cv2.typing.MatLike | None = None) -> None:
        if not self.access_token:
            self._authenticate()
        try:
            record: dict[str, Any] = {
                "text": text,
                "createdAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            data: dict[str, Any] = {
                "repo": self.identifier,
                "collection": "app.bsky.feed.post",
                "record": record,
            }
            if img is not None:
                # 画像がある場合は先にアップロードしてblobを取得
                blob = self._upload_image(img)
                # 画像のアスペクト比を指定
                h, w = img.shape[0], img.shape[1]
                # 画像のアップロードが成功した場合のみ、embedを追加
                if blob:
                    record["embed"] = {
                        "$type": "app.bsky.embed.images",
                        "images": [
                            {"alt": "", "image": blob, "aspectRatio": {"width": w, "height": h}}
                        ],
                    }
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            response = requests.post(
                f"{self.base_url}/xrpc/com.atproto.repo.createRecord",
                json=data,
                headers=headers,
                timeout=5,
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            response = http_err.response
            if response is not None and response.status_code == 401:  # トークン期限切れ
                self._refresh_token()
                self.notify(text, img)
            else:
                self._log_failure("Bluesky notification failed", http_err)
        except Exception as exc:
            self._log_failure("Bluesky notification failed", exc)

    def _log_failure(self, message: str, exc: Exception) -> None:
        self.logger.technical(
            "ERROR",
            message,
            component="BlueskyNotification",
            event="notification.failed",
            extra={"notifier": "bluesky"},
            exc=exc,
        )
