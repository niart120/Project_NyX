import time
from abc import ABC, abstractmethod
from typing import Union

from framework.core.macro.constants import Button, Hat, LStick, RStick
from framework.core.hardware.serial_comm import SerialManager
from framework.core.hardware.protocol import SerialProtocolInterface, CH552SerialProtocol

# キーとして許容する型
KeyType = Union[Button, Hat, LStick, RStick]

class Command(ABC):
    @abstractmethod
    def press(self, *keys: KeyType, dur: float = 0.1, wait: float = 0.1) -> None:
        pass

    @abstractmethod
    def hold(self, *keys: KeyType) -> None:
        pass

    @abstractmethod
    def release(self, *keys: KeyType) -> None:
        pass

    @abstractmethod
    def wait(self, wait: float) -> None:
        pass

    @abstractmethod
    def log(self, *values, sep: str = ' ', end: str = '\n') -> None:
        pass

    @abstractmethod
    def capture(self):
        pass

    @abstractmethod
    def keyboard(self, text: str) -> None:
        pass

class DefaultCommand(Command):
    """
    DefaultCommand は、フレームワーク側で提供するコマンド実装です。
    SerialProtocol を利用して各操作をプロトコルに基づくコマンドデータに変換し、
    SerialManager 経由で送信します。
    
    入力時間制御（dur, wait）はフレームワーク側の責務として、
    必要なタイミングで1回ずつ発行する形にしています。
    """
    def __init__(self, serial_manager: SerialManager, protocol: SerialProtocolInterface = None):
        self.serial_manager = serial_manager
        self.protocol = protocol if protocol is not None else CH552SerialProtocol()

    def press(self, *keys: KeyType, dur: float = 0.1, wait: float = 0.1) -> None:
        self.log(f"[DefaultCommand] Pressing keys: {keys}")
        # 押下コマンド生成
        press_data = self.protocol.build_press_command(keys)
        self.serial_manager.send(press_data)
        # フレームワーク側の責務として、所定の時間待機
        time.sleep(dur)
        self.log(f"[DefaultCommand] Releasing keys: {keys}")
        # 解放コマンド生成
        release_data = self.protocol.build_release_command(keys)
        self.serial_manager.send(release_data)
        time.sleep(wait)

    def hold(self, *keys: KeyType) -> None:
        self.log(f"[DefaultCommand] Holding keys: {keys}")
        hold_data = self.protocol.build_press_command(keys)
        self.serial_manager.send(hold_data)

    def release(self, *keys: KeyType) -> None:
        self.log(f"[DefaultCommand] Releasing keys: {keys}")
        release_data = self.protocol.build_release_command(keys)
        self.serial_manager.send(release_data)

    def wait(self, wait: float) -> None:
        self.log(f"[DefaultCommand] Waiting for {wait} seconds")
        time.sleep(wait)

    def log(self, *values, sep: str = ' ', end: str = '\n') -> None:
        # シンプルなログ出力。将来的に log_manager との統合を検討
        print(*values, sep=sep, end=end)

    def capture(self):
        self.log("[DefaultCommand] Capturing screen...")
        # capture 操作はハードウェア側に委譲
        return None

    def keyboard(self, text: str) -> None:
        self.log(f"[DefaultCommand] Sending keyboard input: {text}")
        kb_data = self.protocol.build_keyboard_command(text)
        self.serial_manager.send(kb_data)