from abc import ABC, abstractmethod

import serial


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
