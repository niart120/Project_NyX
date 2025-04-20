from nyxpy.framework.core.global_settings import GlobalSettings
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.hardware.serial_comm import SerialManager

class SettingsService:
    """
    Aggregates global settings, capture manager, and serial manager,
    and initializes default devices and parameters.
    """
    def __init__(self):
        # Load or create global settings
        self.global_settings = GlobalSettings()
        # Initialize capture manager and select default device
        self.capture_manager = CaptureManager()
        self.capture_manager.auto_register_devices()
        devices = self.capture_manager.list_devices()
        default_capture = self.global_settings.get("capture_device", "")
        try:
            if default_capture and default_capture in devices:
                self.capture_manager.set_active(default_capture)
            elif devices:
                self.capture_manager.set_active(devices[0])
        except Exception:
            pass
        # Initialize serial manager and select default device
        self.serial_manager = SerialManager()
        self.serial_manager.auto_register_devices()
        serials = self.serial_manager.list_devices()
        default_serial = self.global_settings.get("serial_device", "")
        default_baud = self.global_settings.get("serial_baud", 9600)
        try:
            if default_serial and default_serial in serials:
                self.serial_manager.set_active(default_serial, default_baud)
            elif serials:
                self.serial_manager.set_active(serials[0], default_baud)
        except Exception:
            pass
