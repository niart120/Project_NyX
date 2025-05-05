from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.global_settings import GlobalSettings
from nyxpy.framework.core.secrets_settings import SecretsSettings

serial_manager = SerialManager()
capture_manager = CaptureManager()
global_settings = GlobalSettings()
secrets_settings = SecretsSettings()

def initialize_managers():
    serial_manager.auto_register_devices()
    capture_manager.auto_register_devices()

def reset_for_testing():
    global serial_manager, capture_manager, global_settings, secrets_settings
    serial_manager = SerialManager()
    capture_manager = CaptureManager()
    global_settings = GlobalSettings()
    secrets_settings = SecretsSettings()
