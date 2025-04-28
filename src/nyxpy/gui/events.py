from enum import Enum, auto
from typing import Callable, Dict, List, Any

class EventType(Enum):
    SERIAL_DEVICE_CHANGED = auto()
    CAPTURE_DEVICE_CHANGED = auto()
    PROTOCOL_CHANGED = auto()
    # その他必要なイベント

class EventBus:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if EventBus._instance is not None:
            raise RuntimeError("EventBusはシングルトンです。get_instance()を使用してください。")
        self._subscribers: Dict[EventType, List[Callable]] = {}

    def subscribe(self, event_type: EventType, callback: Callable[[Any], None]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable):
        if event_type in self._subscribers and callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    def publish(self, event_type: EventType, data: Any = None):
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                callback(data)
