"""マクロから利用する操作 command API。"""

from __future__ import annotations

import inspect
import pathlib
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import cv2

from nyxpy.framework.core.constants import KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.io.resources import ArtifactScope, OverwritePolicy, ResourceRef
from nyxpy.framework.core.macro.decorators import check_interrupt
from nyxpy.framework.core.macro.text_input import validate_keyboard_text
from nyxpy.framework.core.utils.cancellation import CancellationToken, cancellation_aware_wait

if TYPE_CHECKING:
    from nyxpy.framework.core.runtime.context import ExecutionContext


def _get_caller_class_name() -> str | None:
    frame = inspect.currentframe()
    try:
        caller = frame.f_back.f_back if frame and frame.f_back else None
        self_obj = caller.f_locals.get("self") if caller is not None else None
        return type(self_obj).__name__ if self_obj is not None else None
    finally:
        del frame


class Command(ABC):
    """マクロから実行環境を操作するための公開 API。

    コントローラー操作、待機、ログ、キャプチャ、asset の読み込み、
    artifact の保存と読み戻し、通知はこのインターフェース経由で行います。
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
        実行中に生成した画像 artifact は探索しません。生成物を読み戻す場合は
        `load_artifact_img()` を使います。

        Args:
            filename: 資材 root からの相対パス。例: `"image.png"`。
            grayscale: グレースケール変換を行うか。

        Returns:
            読み込んだ画像データ。

        Raises:
            ResourcePathError: `filename` が不正な path の場合。
            ResourceNotFoundError: 探索 root に画像資材が存在しない場合。
            ResourceReadError: OpenCV 画像として読み込めない場合。

        """
        pass

    @abstractmethod
    def load_blob(self, filename: str | pathlib.Path) -> bytes:
        """バイナリ asset を読み込みます。

        読み込み対象は `resources/<macro_id>/assets` とマクロパッケージ内 assets です。
        実行中に生成した bytes 形式の artifact は探索しません。生成物を読み戻す場合は
        `load_artifact_blob()` を使います。

        Args:
            filename: 資材 root からの相対パス。例: `"data.bin"`。

        Returns:
            読み込んだ bytes データ。

        Raises:
            ResourcePathError: `filename` が不正な path の場合。
            ResourceNotFoundError: 探索 root に資材が存在しない場合。
            ResourceReadError: bytes データを読み込めない場合。

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

        保存先の既定は `resources/<macro_id>/artifacts/<artifact_dir_name>` 配下です。
        実行をまたいで同じ名前の artifact を再利用したい場合は `scope=ArtifactScope.STABLE`
        を指定します。

        Args:
            filename: artifact scope を基準にした相対パス。例: `"debug/frame.png"`。
            image: 保存する画像データ。
            scope: 保存先 scope。
            overwrite: 同名ファイルがある場合の処理。`None` は store の既定値を使う。
            atomic: atomic write を使うかどうか。`None` は store の既定値を使う。

        Returns:
            保存した artifact の参照。

        Raises:
            ResourcePathError: `filename` が不正な path の場合。
            ResourceAlreadyExistsError: 上書き禁止の保存先が既に存在する場合。
            ResourceWriteError: 画像を書き込めない場合。

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
        """バイナリ artifact を保存します。

        テキストはエンコード済み、JSON はシリアライズ済みの bytes として渡します。
        保存先の既定は `resources/<macro_id>/artifacts/<artifact_dir_name>` 配下です。

        Args:
            filename: artifact scope を基準にした相対パス。例: `"result/data.csv"`。
            data: 保存する bytes データ。
            scope: 保存先 scope。
            overwrite: 同名ファイルがある場合の処理。`None` は store の既定値を使う。
            atomic: atomic write を使うかどうか。`None` は store の既定値を使う。

        Returns:
            保存した artifact の参照。

        Raises:
            ResourcePathError: `filename` が不正な path の場合。
            ResourceAlreadyExistsError: 上書き禁止の保存先が既に存在する場合。
            ResourceWriteError: bytes データを書き込めない場合。

        """
        pass

    @abstractmethod
    def load_artifact_img(
        self,
        artifact: ResourceRef | str | pathlib.Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike:
        """画像 artifact を読み戻します。

        `artifact` に `ResourceRef` を渡した場合は、その参照が示す path を読み込みます。
        文字列または `Path` の場合のみ、`scope` に応じて現在実行中の
        artifact または stable artifact を解決します。

        Args:
            artifact: 保存時に返された `ResourceRef`、または artifact scope を基準にした相対パス。
            scope: `artifact` が相対パスの場合の読み込み元 scope。
            grayscale: グレースケール変換を行うか。

        Returns:
            読み込んだ画像データ。

        Raises:
            ResourcePathError: `artifact` の path が不正な場合。
            ResourceNotFoundError: artifact が存在しない場合。
            ResourceReadError: OpenCV 画像として読み込めない場合。

        """
        pass

    @abstractmethod
    def load_artifact_blob(
        self,
        artifact: ResourceRef | str | pathlib.Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
    ) -> bytes:
        """バイナリ artifact を読み戻します。

        `artifact` に `ResourceRef` を渡した場合は、その参照が示す path を読み込みます。
        文字列または `Path` の場合のみ、`scope` に応じて現在実行中の
        artifact または stable artifact を解決します。

        Args:
            artifact: 保存時に返された `ResourceRef`、または artifact scope を基準にした相対パス。
            scope: `artifact` が相対パスの場合の読み込み元 scope。

        Returns:
            読み込んだ bytes データ。

        Raises:
            ResourcePathError: `artifact` の path が不正な場合。
            ResourceNotFoundError: artifact が存在しない場合。
            ResourceReadError: bytes データとして読み込めない場合。

        """
        pass

    @property
    @abstractmethod
    def artifact_dir_name(self) -> str:
        """実行ごとの artifact 保存先を切り替えるための directory segment。

        `ArtifactScope.RUN` の保存先ディレクトリ名です。値は
        `{timestamp}_{short_id}` 形式です。マクロ側で実行ごとの
        サブディレクトリ名を組み立てる場合にも使えます。

        Returns:
            現在の実行に対応する artifact ディレクトリ名。

        """
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
        caller_class = _get_caller_class_name() or "Command"
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
