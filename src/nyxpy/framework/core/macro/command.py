import time
from abc import ABC, abstractmethod
from typing import Union

from nyxpy.framework.core.macro.constants import Button, Hat, LStick, RStick
from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface, CH552SerialProtocol
from nyxpy.framework.core.logger.log_manager import log_manager  # LogManager 利用
from nyxpy.utils.helper import get_caller_class_name

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
    def log(self, *values, sep: str = ' ', end: str = '\n', level: str = "DEBUG") -> None:
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

    操作実行時のログ出力はデフォルトで DEBUG レベルにし、
    外部からログレベルを柔軟に変更できるようにしています。
    """
    def __init__(self, serial_manager: SerialManager, protocol: SerialProtocolInterface = None):
        self.serial_manager = serial_manager
        self.protocol = protocol if protocol is not None else CH552SerialProtocol()

    def press(self, *keys: KeyType, dur: float = 0.1, wait: float = 0.1) -> None:
        self.log(f"Pressing keys: {keys}", level="DEBUG")
        press_data = self.protocol.build_press_command(keys)
        self.serial_manager.send(press_data)
        time.sleep(dur)
        self.log(f"Releasing keys: {keys}", level="DEBUG")
        release_data = self.protocol.build_release_command(keys)
        self.serial_manager.send(release_data)
        time.sleep(wait)

    def hold(self, *keys: KeyType) -> None:
        self.log(f"Holding keys: {keys}", level="DEBUG")
        hold_data = self.protocol.build_press_command(keys)
        self.serial_manager.send(hold_data)

    def release(self, *keys: KeyType) -> None:
        self.log(f"Releasing keys: {keys}", level="DEBUG")
        release_data = self.protocol.build_release_command(keys)
        self.serial_manager.send(release_data)

    def wait(self, wait: float) -> None:
        self.log(f"Waiting for {wait} seconds", level="DEBUG")
        time.sleep(wait)

    def log(self, *values, sep: str = ' ', end: str = '\n', level: str = "INFO") -> None:
        message = sep.join(map(str, values)) + end.rstrip("\n")
        log_manager.log(level, message, component=get_caller_class_name())

    def capture(self):
        self.log("Capturing screen...", level="DEBUG")
        # capture 操作はハードウェア側に委譲
        return None

    def keyboard(self, text: str) -> None:
        self.log(f"Sending keyboard input: {text}", level="DEBUG")
        kb_data = self.protocol.build_keyboard_command(text)
        self.serial_manager.send(kb_data)
