"""マクロから利用する操作 command API。"""

from __future__ import annotations

import pathlib
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import cv2

from nyxpy.framework.core.constants import KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.macro.decorators import check_interrupt
from nyxpy.framework.core.utils.cancellation import CancellationToken, cancellation_aware_wait
from nyxpy.framework.core.utils.helper import (
    get_caller_class_name,
    validate_keyboard_text,
)

if TYPE_CHECKING:
    from nyxpy.framework.core.io.resources import RunArtifactStore
    from nyxpy.framework.core.runtime.context import ExecutionContext


class Command(ABC):
    """マクロから実行環境を操作するための公開 API。

    コントローラー操作、待機、ログ、キャプチャ、画像入出力、通知は
    このインターフェース経由で行います。
    """

    @abstractmethod
    def press(self, *keys: KeyType, dur: float = 0.1, wait: float = 0.1) -> None:
        """指定されたキーを押下します。

        押下時間と待機時間を指定することができます。

        :param keys: 押下するキーのリスト
        :param dur: 押下時間（秒）
        :param wait: 押下後の待機時間（秒）
        """
        pass

    @abstractmethod
    def hold(self, *keys: KeyType) -> None:
        """指定されたキーを押し続けます。より厳密には、現在のキー入力の内部状態を破棄し、指定されたキー入力に変更します。

        これは、連続的な入力を必要とする場合に使用されます。

        :param keys: 押し続けるキーのリスト
        """
        pass

    @abstractmethod
    def release(self, *keys: KeyType) -> None:
        """指定されたキーを解放します。

        これは、押下または保持されたキーを解放するために使用されます。
        すべてのキーを解放する場合は、引数を省略できます。

        :param keys: 解放するキーのリスト
        """
        pass

    @abstractmethod
    def wait(self, wait: float) -> None:
        """指定秒数だけ待機します。

        実装は待機中も中断要求を確認します。長い処理では `time.sleep()` を直接使わず、
        このメソッドを使います。

        :param wait: 待機時間（秒）
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """マクロの実行を中断します。

        これは、ユーザーが中断要求を行った場合に使用されます。
        """
        pass

    @abstractmethod
    def log(self, *values, sep: str = " ", end: str = "\n", level: str = "DEBUG") -> None:
        """ログ出力を行います。

        :param values: ログに出力する値
        :param sep: 値の区切り文字
        :param end: ログの末尾に追加する文字列
        :param level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        """
        pass

    @abstractmethod
    def capture(
        self, crop_region: tuple[int, int, int, int] = None, grayscale: bool = False
    ) -> cv2.typing.MatLike | None:
        """キャプチャデバイスからHD解像度(1280x720) にリスケールしたスクリーンショットを取得し、必要に応じてクロップ及びグレースケール変換を行います。

        3DS のアスペクトボックス入力では、3DS 画面本体は (x=340, y=0, width=600, height=720) として扱います。
        3DS の下画面実領域は (x=400, y=360, width=480, height=360) です。

        :param crop_region: (optional) クロップする領域の指定 (x, y, width, height)
        :param grayscale: (optional) グレースケール変換を行うかどうかのフラグ (デフォルト:False)
        :return result_frame: キャプチャした画像データ。フレームがない場合は None
        :raises ValueError: クロップ領域がフレームサイズ(1280x720)を超える場合にスローされます。
        """
        pass

    @abstractmethod
    def save_img(self, filename: str | pathlib.Path, image: cv2.typing.MatLike) -> None:
        """画像を指定されたパスに保存します。

        ディレクトリが存在しない場合は作成します。

        :param filename: 保存先のファイル名 （例: "image.png"）
        :param image: 保存する画像データ
        """
        pass

    @abstractmethod
    def load_img(self, filename: str | pathlib.Path, grayscale: bool = False) -> cv2.typing.MatLike:
        """指定されたパスから画像を読み込みます。

        画像が存在しない場合は例外をスローします。

        :param filename: 読み込む画像のファイル名 （例: "image.png"）
        :param grayscale: グレースケール変換を行うかどうかのフラグ (デフォルト:False)
        :raises FileNotFoundError: 画像ファイルが見つからない場合
        :raises ValueError: filename が空の場合
        """
        pass

    @abstractmethod
    def keyboard(self, text: str) -> None:
        """指定されたテキスト(英数字)をキーボード入力として送信します。

        プロトコルが対応していない場合は、文字ごとに typekey に委譲されます。

        :param text: 送信するテキスト
        """
        pass

    @abstractmethod
    def type(self, key: KeyCode | SpecialKeyCode) -> None:
        """指定されたキーを個別のキーボード入力として送信します。

        これは個々のキーの押下・解放操作を表します。

        :param key: 送信する通常キーまたは特殊キーのキーコード
        """
        pass

    @abstractmethod
    def notify(self, text: str, img: cv2.typing.MatLike = None) -> None:
        """外部サービスへ通知を送信する"""
        pass

    @property
    def artifacts(self) -> RunArtifactStore:
        """実行ごとの出力先へアクセスします。"""
        raise NotImplementedError("Current command does not expose run artifacts.")

    def touch(self, x: int, y: int, dur: float = 0.1, wait: float = 0.1) -> None:
        """3DS touch 対応プロトコルで touch down / wait / touch up を行います。"""
        raise NotImplementedError("Current serial protocol does not support touch input.")

    def touch_down(self, x: int, y: int) -> None:
        """3DS touch 対応プロトコルで指定座標を押し続けます。"""
        raise NotImplementedError("Current serial protocol does not support touch input.")

    def touch_up(self) -> None:
        """3DS touch 対応プロトコルで touch 入力を離します。"""
        raise NotImplementedError("Current serial protocol does not support touch input.")

    def disable_sleep(self, enabled: bool = True) -> None:
        """対応プロトコルでスリープ制御を切り替えます。"""
        raise NotImplementedError("Current serial protocol does not support sleep control.")


class DefaultCommand(Command):
    """DefaultCommand は、フレームワーク側で提供するコマンド実装です。

    SerialProtocol を利用して各操作をプロトコルに基づくコマンドデータに変換し、
    Runtime の controller Port 経由で送信します。

    操作実行時のログ出力はデフォルトで DEBUG レベルにし、
    外部からログレベルを柔軟に変更できるようにしています。
    """

    def __init__(self, context: ExecutionContext) -> None:
        """実行 context を受け取り、controller と cancellation token へ接続します。"""
        self.context = context
        self.ct: CancellationToken = context.cancellation_token

    @property
    def artifacts(self) -> RunArtifactStore:
        return self.context.artifacts

    @check_interrupt
    def press(self, *keys: KeyType, dur: float = 0.1, wait: float = 0.1) -> None:
        self._debug_command(f"Pressing keys: {keys}")
        self.context.controller.press(keys)
        if dur > 0:
            self.wait(dur)
        self._debug_command(f"Releasing keys: {keys}")
        self.context.controller.release(keys)
        if wait > 0:
            self.wait(wait)

    @check_interrupt
    def hold(self, *keys: KeyType) -> None:
        self._debug_command(f"Holding keys: {keys}")
        self.context.controller.hold(keys)

    @check_interrupt
    def release(self, *keys: KeyType) -> None:
        self._debug_command(f"Releasing keys: {keys}")
        self.context.controller.release(keys)

    @check_interrupt
    def touch(self, x: int, y: int, dur: float = 0.1, wait: float = 0.1) -> None:
        self.touch_down(x, y)
        self.wait(dur)
        self.touch_up()
        self.wait(wait)

    @check_interrupt
    def touch_down(self, x: int, y: int) -> None:
        self._debug_command(f"Touch down: ({x}, {y})")
        self.context.controller.touch_down(x, y)

    @check_interrupt
    def touch_up(self) -> None:
        self._debug_command("Touch up")
        self.context.controller.touch_up()

    @check_interrupt
    def disable_sleep(self, enabled: bool = True) -> None:
        self._debug_command(f"Disable sleep: {enabled}")
        self.context.controller.disable_sleep(enabled)

    @check_interrupt
    def wait(self, wait: float) -> None:
        self._debug_command(f"Waiting for {wait} seconds")
        cancellation_aware_wait(wait, self.ct)
        self.ct.throw_if_requested()

    def stop(self) -> None:
        self.log("Stopping macro execution", level="INFO")
        self.ct.request_cancel(reason="stop requested", source="macro")

    def log(self, *values, sep: str = " ", end: str = "\n", level: str = "DEBUG") -> None:
        message = sep.join(map(str, values)) + end.rstrip("\n")
        caller_class = get_caller_class_name()
        self.context.logger.user(
            level,
            message,
            component=caller_class,
            event="command.log",
        )

    def _debug_command(self, message: str) -> None:
        if self.context.options.command_debug_enabled:
            self.log(message, level="DEBUG")

    @check_interrupt
    def capture(
        self, crop_region: tuple[int, int, int, int] = None, grayscale: bool = False
    ) -> cv2.typing.MatLike | None:
        self._debug_command("Capturing screen...")
        capture_data = self.context.frame_source.latest_frame()
        if capture_data is None:
            self.log("Capture failed", level="ERROR")
            return None
        target_resolution = (1280, 720)
        frame = cv2.resize(capture_data, target_resolution, interpolation=cv2.INTER_AREA)
        if crop_region is not None:
            x, y, w, h = crop_region
            if x < 0 or y < 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
                raise ValueError("Crop region exceeds frame size")
            frame = frame[y : y + h, x : x + w]
        if grayscale:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self._debug_command("Capture successful")
        return frame

    @check_interrupt
    def save_img(self, filename, image) -> None:
        self._debug_command(f"Saving image to {filename}")
        self.context.artifacts.save_image(filename, image)

    @check_interrupt
    def load_img(self, filename, grayscale: bool = False) -> cv2.typing.MatLike:
        self._debug_command(f"Loading image from {filename}")
        return self.context.resources.load_image(filename, grayscale=grayscale)

    @check_interrupt
    def keyboard(self, text: str) -> None:
        self._debug_command(f"Sending keyboard text input: {text}")
        text = validate_keyboard_text(text)
        self.context.controller.keyboard(text)

    @check_interrupt
    def type(self, key: KeyCode | SpecialKeyCode) -> None:
        if not key:
            self.log("Empty key specified for keytype", level="WARNING")
            return

        self._debug_command(f"Sending keyboard key input: {key}")

        self.context.controller.type_key(key)

    @check_interrupt
    def notify(self, text: str, img: cv2.typing.MatLike = None) -> None:
        """外部サービスへ通知を送信する"""
        try:
            self.context.notifications.publish(text, img)
        except Exception as exc:
            self.context.logger.technical(
                "WARNING",
                "Notification failed",
                component="DefaultCommand",
                event="notification.failed",
                extra={"message": str(exc)},
                exc=exc,
            )
