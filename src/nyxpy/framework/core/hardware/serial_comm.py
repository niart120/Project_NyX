import serial
import serial.tools.list_ports
import threading
from abc import ABC, abstractmethod

class SerialCommInterface(ABC):
    """
    シリアル通信の抽象インターフェース。
    DefaultCommand などからこのインターフェース経由で操作する。
    """
    @abstractmethod
    def open(self, baudrate: int) -> None:
        pass

    @abstractmethod
    def send(self, data: bytes) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class SerialComm(SerialCommInterface):
    """
    pyserial を利用したシリアル通信の実装例。
    """
    def __init__(self, port: str):
        self.ser: serial.Serial = None
        self.port: str = port

    def open(self, baudrate: int = 9600) -> None:
        self.ser = serial.Serial(self.port, baudrate, timeout=1)
        if not self.ser.is_open:
            self.ser.open()

    def send(self, data: bytes) -> None:
        if self.ser is None or not self.ser.is_open:
            raise RuntimeError("SerialComm: Serial port not open.")
        self.ser.write(data)

    def close(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None

class DummySerialComm(SerialCommInterface):
    """
    ダミーのシリアル通信クラス。
    実際の通信は行わない。
    """

    def __init__(self, port: str):
        self.port = port

    def open(self, baudrate: int) -> None:
        pass

    def send(self, data: bytes) -> None:
        pass

    def close(self) -> None:
        pass

class SerialManager:
    """
    複数のシリアルデバイスを管理し、利用するデバイスを切り替える仕組みを提供。
    また、DefaultCommand と連動して、通信プロトコルに基づくデータ送受信をサポートする。
    """
    def __init__(self):
        self.devices = {}
        self.active_device: SerialCommInterface = None
        self._default_serial = ""
        self._default_baud = 9600
        # Add a dummy device by default for faster startup
        self.register_device("ダミーデバイス", DummySerialComm("dummy"))
    
    def auto_register_devices(self) -> None:
        """
        接続されているシリアルポートを検出し、デフォルト設定のシリアルデバイスとして登録します。
        """
        # Start a background thread to detect devices to avoid blocking the UI
        thread = threading.Thread(target=self._detect_devices_thread, daemon=True)
        thread.start()
        
    def set_default_device(self, device_name: str, baudrate: int = 9600) -> None:
        """
        デフォルトのデバイス設定を保存します。デバイス検出後に自動的に適用されます。
        """
        self._default_serial = device_name
        self._default_baud = baudrate
    
    def _detect_devices_thread(self) -> None:
        """
        バックグラウンドでデバイスを検出するスレッド処理。
        UIをブロックせずにデバイスを検出します。
        """
        try:
            ports = serial.tools.list_ports.comports()
            for port in ports:
                device = SerialComm(port=port.device)
                self.register_device(port.device, device)
                
            # デバイス検出が完了したら、デフォルト設定を適用
            if self._default_serial and self._default_serial in self.devices:
                self.set_active(self._default_serial, self._default_baud)
            elif len(self.devices) > 1:  # ダミーデバイス以外が存在する場合
                # ダミーデバイス以外の最初のデバイスを選択
                non_dummy_devices = [name for name in self.devices.keys() if name != "ダミーデバイス"]
                if non_dummy_devices:
                    self.set_active(non_dummy_devices[0], self._default_baud)
        except Exception as e:
            import traceback
            traceback.print_exc()
            # Make sure we always have at least the dummy device
            if "ダミーデバイス" not in self.devices:
                self.register_device("ダミーデバイス", DummySerialComm("dummy"))
    
    def list_devices(self) -> list[str]:
        """
        登録されているデバイスのリストを返します。
        """
        return list(self.devices.keys())

    def register_device(self, name: str, device: SerialCommInterface) -> None:
        self.devices[name] = device

    def set_active(self, name: str, baudrate: int = 9600) -> None:
        """
        指定されたデバイスをアクティブにします。
        """

        # アクティブなデバイスをリリース
        self.close_active()

        # デバイスが登録されているか確認
        if name not in self.devices:
            raise ValueError(f"SerialManager: Device '{name}' not registered.")
        device = self.devices[name]
        device.open(baudrate)
        self.active_device = device

    def is_active(self) -> bool:
        """
        アクティブなシリアルデバイスが設定されているかを返します。
        
        Returns:
            bool: アクティブなデバイスが存在する場合はTrue、それ以外はFalse
        """
        return self.active_device is not None

    def get_active_device(self) -> SerialCommInterface:
        """
        現在アクティブなシリアルデバイス（ドライバ）を返します。
        送受信などの実際の操作は、このドライバのメソッドに委ねます。
        """
        if self.active_device is None:
            # Use dummy device instead of raising error
            self.set_active("ダミーデバイス", 9600)
        return self.active_device

    def close_active(self) -> None:
        if self.active_device:
            self.active_device.close()
            self.active_device = None
