"""外部通知 adapter の共通 interface。"""

from abc import ABC, abstractmethod

import cv2


class Notifier(ABC):
    """通知 service adapter が実装する送信 interface。"""

    @abstractmethod
    def notify(self, text: str, img: cv2.typing.MatLike | None = None) -> None:
        """通知を送信する。imgは任意添付。未対応サービスはテキストのみ送信。"""
        pass
