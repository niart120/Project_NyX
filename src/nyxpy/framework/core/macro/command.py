import time
from abc import ABC, abstractmethod
import cv2

from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.macro.constants import KeyType
from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface, CH552SerialProtocol
from nyxpy.framework.core.logger.log_manager import log_manager  # LogManager 利用
from nyxpy.utils.helper import get_caller_class_name

class Command(ABC):
    """
    Command は、マクロ用コマンドのインターフェースを定義します。
    コントローラー操作の実行、待機、ログ出力、キャプチャなどの基本的な操作を提供します。
    """

    @abstractmethod
    def press(self, *keys: KeyType, dur: float = 0.1, wait: float = 0.1) -> None:
        """
        指定されたキーを押下します。
        押下時間と待機時間を指定することができます。

        :param keys: 押下するキーのリスト
        :param dur: 押下時間（秒）
        :param wait: 押下後の待機時間（秒）
        """
        pass

    @abstractmethod
    def hold(self, *keys: KeyType) -> None:
        """
        指定されたキーを押し続けます。

        :param keys: 押し続けるキーのリスト
        """
        pass

    @abstractmethod
    def release(self, *keys: KeyType) -> None:
        """
        指定されたキーを解放します。
        これは、押下または保持されたキーを解放するために使用されます。
        すべてのキーを解放する場合は、引数を省略できます。

        :param keys: 解放するキーのリスト
        """
        pass

    @abstractmethod
    def wait(self, wait: float) -> None:
        """
        指定された時間だけ待機します。

        :param wait: 待機時間（秒）
        """
        pass

    @abstractmethod
    def log(self, *values, sep: str = ' ', end: str = '\n', level: str = "DEBUG") -> None:
        """
        ログ出力を行います。

        :param values: ログに出力する値
        :param sep: 値の区切り文字
        :param end: ログの末尾に追加する文字列
        :param level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        """
        pass

    @abstractmethod
    def capture(self, crop_region:tuple[int, int, int, int] = None, grayscale: bool = False)->cv2.typing.MatLike:
        """
        キャプチャデバイスからHD解像度(1280x720) にリスケールしたスクリーンショットを取得し、必要に応じてクロップ及びグレースケール変換を行います。

        :param crop_region: (optional) クロップする領域の指定 (x, y, width, height)
        :param grayscale: (optional) グレースケール変換を行うかどうかのフラグ (デフォルト:False)
        :return result_frame: キャプチャした画像データ
        :raises ValueError: クロップ領域がフレームサイズ(1280x720)を超える場合にスローされます。
        """
        pass

    @abstractmethod
    def keyboard(self, text: str) -> None:
        """
        指定されたテキストをキーボード入力として送信します。

        :param text: 送信するテキスト
        """
        pass

class DefaultCommand(Command):
    """
    DefaultCommand は、フレームワーク側で提供するコマンド実装です。
    SerialProtocol を利用して各操作をプロトコルに基づくコマンドデータに変換し、
    SerialManager 経由で送信します。

    操作実行時のログ出力はデフォルトで DEBUG レベルにし、
    外部からログレベルを柔軟に変更できるようにしています。
    """
    def __init__(self, serial_manager: SerialManager, capture_manager: CaptureManager, protocol: SerialProtocolInterface = None):
        self.serial_manager = serial_manager
        self.capture_manager = capture_manager
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

    def capture(self, crop_region:tuple[int, int, int, int] = None, grayscale: bool = False)->cv2.typing.MatLike:
        # キャプチャマネージャを使用してスクリーンキャプチャを取得
        self.log("Capturing screen...", level="DEBUG")
        capture_data = self.capture_manager.get_frame()
        if capture_data is None:
            self.log("Capture failed", level="ERROR")
            return None
        
        # リスケール処理を実行
        target_resolution = (1280, 720)  # HD解像度
        frame = cv2.resize(capture_data, target_resolution, interpolation=cv2.INTER_LINEAR)

        # クロップ処理を実行
        if crop_region is not None:
            x, y, w, h = crop_region
            # クロップ領域がフレームサイズを超える場合は例外をスロー
            if x < 0 or y < 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
                raise ValueError("Crop region exceeds frame size")
            # クロップ領域がフレームサイズを超えない場合はクロップを実行
            frame = frame[y:y+h, x:x+w]

        # グレースケール変換を実行
        if grayscale:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        self.log("Capture successful", level="DEBUG")
        return frame

    def keyboard(self, text: str) -> None:
        self.log(f"Sending keyboard input: {text}", level="DEBUG")
        kb_data = self.protocol.build_keyboard_command(text)
        self.serial_manager.send(kb_data)
