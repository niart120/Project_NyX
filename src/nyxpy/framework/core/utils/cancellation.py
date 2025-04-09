import threading

class CancellationToken:
    """
    中断要求を管理するためのクラス。
    内部にスレッドセーフなイベントを保持し、中断状態を示す。
    """
    def __init__(self):
        self._stop_event = threading.Event()

    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    def request_stop(self) -> None:
        self._stop_event.set()

    def clear(self) -> None:
        self._stop_event.clear()