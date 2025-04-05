import serial
from serial import Serial
from abc import ABC, abstractmethod

class SerialCommInterface(ABC):
    """
    シリアル通信の抽象インターフェース。
    DefaultCommand などからこのインターフェース経由で操作する。
    """
    @abstractmethod
    def open(self, port: str, baudrate: int) -> None:
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
    def __init__(self):
        self.ser: Serial = None

    def open(self, port: str, baudrate: int = 9600) -> None:
        self.ser = serial.Serial(port, baudrate, timeout=1)
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


class SerialManager:
    """
    複数のシリアルデバイスを管理し、利用するデバイスを切り替える仕組みを提供。
    また、DefaultCommand と連動して、通信プロトコルに基づくデータ送受信をサポートする。
    """
    def __init__(self):
        self.devices = {}
        self.active_device: SerialCommInterface = None

    def register_device(self, name: str, device: SerialCommInterface) -> None:
        self.devices[name] = device

    def set_active(self, name: str, port: str, baudrate: int = 9600) -> None:
        if name not in self.devices:
            raise ValueError(f"SerialManager: Device '{name}' not registered.")
        device = self.devices[name]
        device.open(port, baudrate)
        self.active_device = device

    def send(self, data: bytes) -> None:
        if self.active_device is None:
            raise RuntimeError("SerialManager: No active serial device.")
        self.active_device.send(data)

    def close_active(self) -> None:
        if self.active_device:
            self.active_device.close()
            self.active_device = None
