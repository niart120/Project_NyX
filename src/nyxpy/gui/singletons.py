from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.settings_service import SettingsService

serial_manager = SerialManager()
capture_manager = CaptureManager()
settings_service = SettingsService()

def initialize_managers():
    serial_manager.auto_register_devices()
    capture_manager.auto_register_devices()

def reset_for_testing():
    global serial_manager, capture_manager, settings_service
    serial_manager = SerialManager()
    capture_manager = CaptureManager()
    settings_service = SettingsService()
