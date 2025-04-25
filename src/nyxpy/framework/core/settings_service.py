from nyxpy.framework.core.global_settings import GlobalSettings
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface

class SettingsService:
    """
    Aggregates global settings, capture manager, and serial manager,
    and initializes default devices and parameters.
    """
    def __init__(self):
        # Load or create global settings
        self.global_settings = GlobalSettings()
        
        # Initialize capture manager
        self.capture_manager = CaptureManager()
        default_capture = self.global_settings.get("capture_device", "")
        
        # デフォルトのキャプチャデバイスが設定されていれば適用する
        if default_capture:
            self.capture_manager.set_default_device(default_capture)
        
        # バックグラウンドでデバイス検出開始
        self.capture_manager.auto_register_devices()
                
        # Initialize serial manager and configure default device
        self.serial_manager = SerialManager()
        default_serial = self.global_settings.get("serial_device", "")
        default_baud = self.global_settings.get("serial_baud", 9600)
        
        # 設定されているデフォルトシリアルデバイスがあれば、
        # 検出後に自動的に適用されるように設定する
        if default_serial:
            self.serial_manager.set_default_device(default_serial, default_baud)
        
        # デバイス検出を開始（バックグラウンドで実行）
        self.serial_manager.auto_register_devices()
        
    def get_protocol(self) -> SerialProtocolInterface:
        """
        設定から選択されたシリアルプロトコルのインスタンスを取得する
        
        :return: SerialProtocolInterface の実装
        """
        # global_settings から直接プロトコル名を取得する
        protocol_name = self.global_settings.get("serial_protocol", "CH552")
        return ProtocolFactory.create_protocol(protocol_name)
