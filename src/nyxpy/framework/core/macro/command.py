import time
import pathlib
from abc import ABC, abstractmethod
import cv2

from nyxpy.framework.core.hardware.facade import HardwareFacade
from nyxpy.framework.core.hardware.resource import StaticResourceIO
from nyxpy.framework.core.constants import KeyCode, KeyType, KeyboardOp, SpecialKeyCode
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.logger.log_manager import log_manager  # LogManager 利用
from nyxpy.framework.core.macro.exceptions import MacroStopException
from nyxpy.framework.core.utils.cancellation import CancellationToken
from nyxpy.framework.core.macro.decorators import check_interrupt
from nyxpy.framework.core.utils.helper import get_caller_class_name, validate_keyboard_text

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
    def stop(self)-> None:
        """
        マクロの実行を中断します。
        これは、ユーザーが中断要求を行った場合に使用されます。
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
    def save_img(self, filename: str | pathlib.Path, image: cv2.typing.MatLike) -> None:
        """
        画像を指定されたパスに保存します。
        ディレクトリが存在しない場合は作成します。

        :param filename: 保存先のファイル名 （例: "image.png"）
        :param image: 保存する画像データ
        """
        pass

    @abstractmethod
    def load_img(self, filename: str | pathlib.Path, grayscale: bool = False) -> cv2.typing.MatLike:
        """
        指定されたパスから画像を読み込みます。
        画像が存在しない場合は例外をスローします。

        :param filename: 読み込む画像のファイル名 （例: "image.png"）
        :param grayscale: グレースケール変換を行うかどうかのフラグ (デフォルト:False)
        :raises FileNotFoundError: 画像ファイルが見つからない場合
        :raises ValueError: filename が空の場合
        """
        pass

    @abstractmethod
    def keyboard(self, text: str) -> None:
        """
        指定されたテキスト(英数字)をキーボード入力として送信します。
        プロトコルが対応していない場合は、文字ごとに keytype に委譲されます。

        :param text: 送信するテキスト
        """
        pass

    @abstractmethod
    def keytype(self, key: str) -> None:
        """
        指定されたキーを個別のキーボード入力として送信します。
        これは個々のキーの押下・解放操作を表します。

        :param key: 送信するキー文字
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
    def __init__(self, hardware_facade:HardwareFacade, 
                 resource_io:StaticResourceIO, 
                 protocol:SerialProtocolInterface, 
                 ct:CancellationToken) -> None:

        self.hardware_facade = hardware_facade
        self.resource_io = resource_io
        self.protocol = protocol
        self.ct = ct

    @check_interrupt
    def press(self, *keys: KeyType, dur: float = 0.1, wait: float = 0.1) -> None:
        self.log(f"Pressing keys: {keys}", level="DEBUG")
        press_data = self.protocol.build_press_command(keys)
        self.hardware_facade.send(press_data)
        self.wait(dur)
        self.log(f"Releasing keys: {keys}", level="DEBUG")
        release_data = self.protocol.build_release_command(keys)
        self.hardware_facade.send(release_data)
        self.wait(wait)

    @check_interrupt
    def hold(self, *keys: KeyType) -> None:
        self.log(f"Holding keys: {keys}", level="DEBUG")
        hold_data = self.protocol.build_press_command(keys)
        self.hardware_facade.send(hold_data)

    @check_interrupt
    def release(self, *keys: KeyType) -> None:
        self.log(f"Releasing keys: {keys}", level="DEBUG")
        release_data = self.protocol.build_release_command(keys)
        self.hardware_facade.send(release_data)

    @check_interrupt
    def wait(self, wait: float) -> None:
        self.log(f"Waiting for {wait} seconds", level="DEBUG")
        time.sleep(wait)

    def stop(self) -> None:
        self.log("Stopping macro execution", level="INFO")
        self.ct.request_stop()
        raise MacroStopException("Macro execution interrupted.")

    def log(self, *values, sep: str = ' ', end: str = '\n', level: str = "INFO") -> None:
        message = sep.join(map(str, values)) + end.rstrip("\n")
        log_manager.log(level, message, component=get_caller_class_name())

    @check_interrupt
    def capture(self, crop_region:tuple[int, int, int, int] = None, grayscale: bool = False)->cv2.typing.MatLike:
        # キャプチャマネージャを使用してスクリーンキャプチャを取得
        self.log("Capturing screen...", level="DEBUG")
        capture_data = self.hardware_facade.capture()
        if capture_data is None:
            self.log("Capture failed", level="ERROR")
            return None
        
        # リスケール処理を実行
        target_resolution = (1280, 720)  # HD解像度
        frame = cv2.resize(capture_data, target_resolution, interpolation=cv2.INTER_AREA)

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
    
    @check_interrupt
    def save_img(self, filename, image)-> None:
        self.log(f"Saving image to {filename}", level="DEBUG")
        self.resource_io.save_image(filename, image)
    
    @check_interrupt
    def load_img(self, filename, grayscale: bool = False) -> cv2.typing.MatLike:
        self.log(f"Loading image from {filename}", level="DEBUG")
        return self.resource_io.load_image(filename, grayscale=grayscale)

    @check_interrupt
    def keyboard(self, text: str) -> None:
        self.log(f"Sending keyboard text input: {text}", level="DEBUG")
        text = validate_keyboard_text(text)
        
        try:
            # まずテキスト入力としてプロトコルに処理を依頼
            kb_data = self.protocol.build_keyboard_command(text)
            self.hardware_facade.send(kb_data)
        except (ValueError, NotImplementedError):
            # プロトコルがテキスト入力に対応していない場合は、1文字ずつkeytype処理に委譲
            for char in text:
                self.keytype(KeyCode(char))
        
        # すべてのキーを解放（念のため）
        try:
            kb_all_release = self.protocol.build_keytype_command(KeyCode(""), KeyboardOp.ALL_RELEASE)
            self.hardware_facade.send(kb_all_release)
        except NotImplementedError:
            pass
    
    @check_interrupt
    def keytype(self, key: KeyCode|SpecialKeyCode) -> None:
        if not key:
            self.log("Empty key specified for keytype", level="WARNING")
            return
            
        self.log(f"Sending keyboard key input: {key}", level="DEBUG")
        
        # キーの種類に応じて操作を分岐
        match key:
            case KeyCode():
                press_op = KeyboardOp.PRESS
                release_op = KeyboardOp.RELEASE
            case SpecialKeyCode():
                press_op = KeyboardOp.SPECIAL_PRESS
                release_op = KeyboardOp.SPECIAL_RELEASE
            case _:
                raise ValueError(f"Invalid key type: {type(key)}")
        
        try:
            # キー押下
            kb_press = self.protocol.build_keytype_command(key, press_op)
            self.hardware_facade.send(kb_press)
            self.wait(0.02)  # 必要に応じて調整
            
            # キー解放
            kb_release = self.protocol.build_keytype_command(key, release_op)
            self.hardware_facade.send(kb_release)
            self.wait(0.01)  # 必要に応じて調整
        except NotImplementedError as e:
            self.log(f"Protocol doesn't support key input: {str(e)}", level="WARNING")
