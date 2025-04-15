import serial
import serial.tools.list_ports
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
    
    def auto_register_devices(self) -> None:
        """
        接続されているシリアルポートを検出し、デフォルト設定のシリアルデバイスとして登録します。
        """

        # アクティブなデバイスをリリース
        self.close_active()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            device = SerialComm(port=port.device)
            self.register_device(port.device, device)
    
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

    def get_active_device(self) -> SerialCommInterface:
        """
        現在アクティブなシリアルデバイス（ドライバ）を返します。
        送受信などの実際の操作は、このドライバのメソッドに委ねます。
        """
        if self.active_device is None:
            raise RuntimeError("SerialManager: No active serial device.")
        return self.active_device

    def close_active(self) -> None:
        if self.active_device:
            self.active_device.close()
            self.active_device = None
