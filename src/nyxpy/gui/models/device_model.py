from nyxpy.gui.events import EventBus, EventType
from nyxpy.gui.singletons import serial_manager, capture_manager

class DeviceModel:
    """デバイス管理を担当するモデルクラス"""
    def __init__(self):
        self.event_bus = EventBus.get_instance()
        self._active_serial_device = None
        self._active_capture_device = None
        self.update_active_devices()

    def update_active_devices(self):
        """現在のアクティブデバイスを更新"""
        self._active_serial_device = serial_manager.get_active_device()
        self._active_capture_device = capture_manager.get_active_device()

    def change_serial_device(self, device_name: str, baudrate: int = 9600):
        """シリアルデバイスを変更し、変更を通知"""
        serial_manager.set_active(device_name, baudrate)
        self._active_serial_device = serial_manager.get_active_device()
        self.event_bus.publish(EventType.SERIAL_DEVICE_CHANGED, {
            'name': device_name,
            'baudrate': baudrate,
            'device': self._active_serial_device
        })

    def change_capture_device(self, device_name: str):
        """キャプチャデバイスを変更し、変更を通知"""
        capture_manager.set_active(device_name)
        self._active_capture_device = capture_manager.get_active_device()
        self.event_bus.publish(EventType.CAPTURE_DEVICE_CHANGED, {
            'name': device_name,
            'device': self._active_capture_device
        })

    def get_serial_device_list(self):
        """利用可能なシリアルデバイスのリストを取得"""
        return serial_manager.list_devices()

    def get_capture_device_list(self):
        """利用可能なキャプチャデバイスのリストを取得"""
        return capture_manager.list_devices()

    def get_active_serial_device(self):
        """現在のアクティブなシリアルデバイスを取得"""
        return self._active_serial_device

    def get_active_capture_device(self):
        """現在のアクティブなキャプチャデバイスを取得"""
        return self._active_capture_device
