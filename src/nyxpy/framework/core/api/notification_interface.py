from abc import ABC, abstractmethod
from typing import Optional
import cv2

class NotificationInterface(ABC):
    @abstractmethod
    def notify(self, text: str, img: Optional[cv2.Mat] = None) -> None:
        """
        通知を送信する。imgは任意添付。未対応サービスはテキストのみ送信。
        """
        pass
