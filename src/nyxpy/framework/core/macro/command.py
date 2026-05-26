"""マクロから利用する操作 command API。"""

from __future__ import annotations

import pathlib
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import cv2

from nyxpy.framework.core.constants import KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.io.resources import ArtifactScope, OverwritePolicy, ResourceRef
from nyxpy.framework.core.macro.decorators import check_interrupt
from nyxpy.framework.core.utils.cancellation import CancellationToken, cancellation_aware_wait
from nyxpy.framework.core.utils.helper import (
    get_caller_class_name,
    validate_keyboard_text,
)

if TYPE_CHECKING:
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

        Args:
            keys: 押下するキー。
            dur: 押下時間（秒）。
            wait: 押下後の待機時間（秒）。

        """
        pass

    @abstractmethod
    def hold(self, *keys: KeyType) -> None:
        """指定されたキーを押し続けます。より厳密には、現在のキー入力の内部状態を破棄し、指定されたキー入力に変更します。

        これは、連続的な入力を必要とする場合に使用されます。

        Args:
            keys: 押し続けるキー。

        """
        pass

    @abstractmethod
    def release(self, *keys: KeyType) -> None:
        """指定されたキーを解放します。

        これは、押下または保持されたキーを解放するために使用されます。
        すべてのキーを解放する場合は、引数を省略できます。

        Args:
            keys: 解放するキー。省略時は全解除。

        """
        pass

    @abstractmethod
    def wait(self, wait: float) -> None:
        """指定秒数だけ待機します。

        実装は待機中も中断要求を確認します。長い処理では `time.sleep()` を直接使わず、
        このメソッドを使います。

        Args:
            wait: 待機時間（秒）。

        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """マクロの実行を中断します。

        これは、ユーザーが中断要求を行った場合に使用されます。
        """
        pass

    @abstractmethod
    def log(self, *values: object, sep: str = " ", end: str = "\n", level: str = "DEBUG") -> None:
        """ログ出力を行います。

        Args:
            values: ログに出力する値。
            sep: 値の区切り文字。
            end: ログの末尾に追加する文字列。
            level: ログレベル。`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`。

        """
        pass

    @abstractmethod
    def capture(
        self, crop_region: tuple[int, int, int, int] | None = None, grayscale: bool = False
    ) -> cv2.typing.MatLike:
        """キャプチャデバイスからHD解像度(1280x720) にリスケールしたスクリーンショットを取得し、必要に応じてクロップ及びグレースケール変換を行います。

        3DS のアスペクトボックス入力では、3DS 画面本体は (x=340, y=0, width=600, height=720) として扱います。
        3DS の下画面実領域は (x=400, y=360, width=480, height=360) です。

        Args:
            crop_region: クロップする領域の指定 `(x, y, width, height)`。
            grayscale: グレースケール変換を行うか。

        Returns:
            キャプチャした画像データ。

        Raises:
            FrameNotReadyError: フレームがまだ取得できない場合。
            ValueError: クロップ領域がフレームサイズ (1280x720) を超える場合。

        """
        pass

    @abstractmethod
    def load_img(
        self,
        filename: str | pathlib.Path,
        *,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike:
        """画像 asset を読み込みます。

        読み込み対象は `resources/<macro_id>/assets` とマクロパッケージ内 assets です。

        Args:
            filename: 資材 root からの相対パス。例: `"image.png"`。
            grayscale: グレースケール変換を行うか。

        Raises:
            ResourcePathError: `filename` が不正な path の場合。
            ResourceNotFoundError: 探索 root に画像資材が存在しない場合。
            ResourceReadError: OpenCV 画像として読み込めない場合。

        """
        pass

    @abstractmethod
    def load_blob(self, filename: str | pathlib.Path) -> bytes:
        """任意 bytes asset を読み込みます。

        Args:
            filename: 資材 root からの相対パス。例: `"image.png"`。

        Raises:
            ResourcePathError: `filename` が不正な path の場合。
            ResourceNotFoundError: 探索 root に資材が存在しない場合。
            ResourceReadError: bytes を読み込めない場合。

        """
        pass

    @abstractmethod
    def save_artifact_img(
        self,
        filename: str | pathlib.Path,
        image: cv2.typing.MatLike,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef:
        """画像 artifact を保存します。

        既定では `resources/<macro_id>/artifacts/<artifact_dir_name>` 配下へ保存します。

        Args:
            filename: artifact scope からの相対パス。
            image: 保存する画像データ。
            scope: 保存先 scope。
            overwrite: 既存ファイル処理。`None` は store の既定値を使う。
            atomic: atomic write を使うか。`None` は store の既定値を使う。

        """
        pass

    @abstractmethod
    def save_artifact_blob(
        self,
        filename: str | pathlib.Path,
        data: bytes,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef:
        """任意 bytes artifact を保存します。"""
        pass

    @abstractmethod
    def load_artifact_img(
        self,
        artifact: ResourceRef | str | pathlib.Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike:
        """画像 artifact を読み戻します。"""
        pass

    @abstractmethod
    def load_artifact_blob(
        self,
        artifact: ResourceRef | str | pathlib.Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
    ) -> bytes:
        """任意 bytes artifact を読み戻します。"""
        pass

    @property
    @abstractmethod
    def artifact_dir_name(self) -> str:
        """実行ごとの artifact 保存先切り替えに使う directory segment。"""
        pass

    @abstractmethod
    def keyboard(self, text: str) -> None:
        """指定されたテキスト(英数字)をキーボード入力として送信します。

        プロトコルが対応していない場合は、文字ごとに typekey に委譲されます。

        Args:
            text: 送信するテキスト。

        """
        pass

    @abstractmethod
    def type(self, key: KeyCode | SpecialKeyCode) -> None:
        """指定されたキーを個別のキーボード入力として送信します。

        これは個々のキーの押下・解放操作を表します。

        Args:
            key: 送信する通常キーまたは特殊キーのキーコード。

        """
        pass

    @abstractmethod
    def notify(self, text: str, img: cv2.typing.MatLike | None = None) -> None:
        """外部サービスへ通知を送信する"""
        pass

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

    def log(self, *values: object, sep: str = " ", end: str = "\n", level: str = "DEBUG") -> None:
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
        self, crop_region: tuple[int, int, int, int] | None = None, grayscale: bool = False
    ) -> cv2.typing.MatLike:
        self._debug_command("Capturing screen...")
        capture_data = self.context.frame_source.latest_frame()
        frame = self._format_capture(capture_data, crop_region, grayscale)
        self._debug_command("Capture successful")
        return frame

    def _format_capture(
        self,
        capture_data: cv2.typing.MatLike,
        crop_region: tuple[int, int, int, int] | None,
        grayscale: bool,
    ) -> cv2.typing.MatLike:
        target_resolution = (1280, 720)
        frame = cv2.resize(capture_data, target_resolution, interpolation=cv2.INTER_AREA)
        if crop_region is not None:
            x, y, w, h = crop_region
            if x < 0 or y < 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
                raise ValueError("Crop region exceeds frame size")
            frame = frame[y : y + h, x : x + w]
        if grayscale:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return frame

    @check_interrupt
    def load_img(
        self,
        filename: str | pathlib.Path,
        *,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike:
        self._debug_command(f"Loading image from {filename}")
        return self.context.resources.load_image(filename, grayscale=grayscale)

    @check_interrupt
    def load_blob(self, filename: str | pathlib.Path) -> bytes:
        self._debug_command(f"Loading blob from {filename}")
        return self.context.resources.load_blob(filename)

    @check_interrupt
    def save_artifact_img(
        self,
        filename: str | pathlib.Path,
        image: cv2.typing.MatLike,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef:
        self._debug_command(f"Saving artifact image to {filename}")
        return self.context.artifacts.save_image(
            filename,
            image,
            scope=scope,
            overwrite=overwrite,
            atomic=atomic,
        )

    @check_interrupt
    def save_artifact_blob(
        self,
        filename: str | pathlib.Path,
        data: bytes,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef:
        self._debug_command(f"Saving artifact blob to {filename}")
        return self.context.artifacts.save_blob(
            filename,
            data,
            scope=scope,
            overwrite=overwrite,
            atomic=atomic,
        )

    @check_interrupt
    def load_artifact_img(
        self,
        artifact: ResourceRef | str | pathlib.Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike:
        self._debug_command(f"Loading artifact image from {artifact}")
        return self.context.artifacts.load_image(artifact, scope=scope, grayscale=grayscale)

    @check_interrupt
    def load_artifact_blob(
        self,
        artifact: ResourceRef | str | pathlib.Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
    ) -> bytes:
        self._debug_command(f"Loading artifact blob from {artifact}")
        return self.context.artifacts.load_blob(artifact, scope=scope)

    @property
    def artifact_dir_name(self) -> str:
        return self.context.artifact_dir_name

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
    def notify(self, text: str, img: cv2.typing.MatLike | None = None) -> None:
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
