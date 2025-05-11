import threading
import time
import pytest
import numpy as np

# インポートはプロジェクトのパッケージ構成に合わせる
from nyxpy.framework.core.hardware.resource import StaticResourceIO
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.hardware.serial_comm import SerialManager, SerialCommInterface
from nyxpy.framework.core.hardware.capture import CaptureManager, AsyncCaptureDevice
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol
from nyxpy.framework.core.constants import Button, Hat
from nyxpy.framework.core.logger.log_manager import log_manager
from nyxpy.framework.core.utils.cancellation import CancellationToken
from nyxpy.framework.core.macro.executor import MacroExecutor

class MockNotificationHandler:
    def __init__(self):
        self.calls = []
    def publish(self, text, img=None):
        self.calls.append((text, img))

# --- Fake デバイス実装 ---


class FakeSerialComm(SerialCommInterface):
    """Fake SerialComm で、送信されたデータを記録する"""

    def __init__(self):
        self.sent = []

    def open(self, port: str, baudrate: int = 9600) -> None:
        # 何もしない
        pass

    def send(self, data: bytes) -> None:
        self.sent.append(data)

    def close(self) -> None:
        pass


class FakeAsyncCaptureDevice(AsyncCaptureDevice):
    """Fake AsyncCaptureDevice で、固定の黒画像を返す"""

    def __init__(self, device_index: int = 0, fps: float = 30.0):
        super().__init__(device_index, fps)

    def initialize(self) -> None:
        # 初期化は通常通り行い、代わりに固定フレームを設定
        self.latest_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        self._running = True  # スレッドは起動せず、固定フレームのみ利用

    def release(self) -> None:
        self._running = False
        # スレッドの join は不要


# --- Fake リソースIO実装 ---
class FakeResourceIO(StaticResourceIO):
    """FakeResourceIO で、画像の読み書きは行わず、メモリ上で管理する"""

    def __init__(self):
        self.saved_images = {}

    def save_image(self, filename: str, image) -> None:
        # 画像を保存せず、メモリ上で管理
        self.saved_images[filename] = image

    def load_image(self, filename: str, grayscale: bool = False):
        # 保存された画像を返す
        return self.saved_images.get(filename, None)


# --- ダミーマクロの実装 ---


class DummyMacro(MacroBase):
    """
    DummyMacro は MacroBase を継承し、各ライフサイクルで Command のメソッドを呼び出す。
    """

    def initialize(self, cmd, args):
        cmd.log("Initializing DummyMacro", level="INFO")

    def run(self, cmd):
        # ボタン操作、キーボード入力、キャプチャの各操作を実行する
        cmd.press(Button.A, dur=0.1, wait=0.1)
        cmd.keyboard("Hello")
        self.captured_frame = cmd.capture()

    def finalize(self, cmd):
        cmd.release(Button.A)
        cmd.log("Finalizing DummyMacro", level="INFO")


class LongRunningMacro(MacroBase):
    """
    LongRunningMacro は、複数回の操作ループを実行します。
    途中で CancellationToken による中断要求があれば、check_cancellation のデコレータが例外を発生させます。
    """

    def __init__(self):
        self.finalized = False

    def initialize(self, cmd, args):
        cmd.log("Initializing LongRunningMacro", level="INFO")

    def run(self, cmd):
        # 例えば10回ループし、各ループで press を実行
        for i in range(10):
            cmd.log(f"Running iteration {i}", level="DEBUG")
            # 各操作前にデコレータが中断チェックを実施する
            cmd.press(Button.A, dur=0.1, wait=0.05)
            # 短い休止（sleep は monkeypatch でスキップできるが、ここでは実際の呼び出しとして記録）
            time.sleep(0.05)

    def finalize(self, cmd):
        cmd.log("Finalizing LongRunningMacro", level="INFO")
        self.finalized = True


logs = []  # ログを記録するリスト


# --- ダミーのログハンドラのセットアップ ---
def dummy_handler(msg):
    logs.append(msg)


# --- 統合テストセットアップ ---


@pytest.fixture
def integration_setup(monkeypatch):
    # CancellationToken の作成
    token = CancellationToken()
    serial_manager = SerialManager()
    capture_manager = CaptureManager()
    fake_serial = FakeSerialComm()
    serial_manager.register_device("fake", fake_serial)
    serial_manager.set_active("fake", baudrate=9600)
    fake_capture = FakeAsyncCaptureDevice()
    capture_manager.register_device("fake", fake_capture)
    capture_manager.set_active("fake")
    resource_io = FakeResourceIO()
    mock_notifier = MockNotificationHandler()
    cmd = DefaultCommand(
        serial_device=fake_serial,
        capture_device=fake_capture,
        resource_io=resource_io,
        protocol=CH552SerialProtocol(),
        ct=token,
        notification_handler=mock_notifier,
    )
    log_manager.add_handler(dummy_handler, level="DEBUG")
    executor = MacroExecutor()
    executor.macros = {
        "DummyMacro": DummyMacro(),
        "LongRunningMacro": LongRunningMacro(),
    }
    yield executor, cmd, fake_serial, fake_capture, token, mock_notifier
    log_manager.remove_handler(dummy_handler)
    serial_manager.active_device.close()
    capture_manager.active_device.release()
    logs.clear()


# --- 統合テストケース ---


def test_macro_executor_normal_flow(integration_setup):
    """
    MacroExecutor経由でDummyMacroのライフサイクルを一気通貫でテスト
    """
    executor, cmd, fake_serial, fake_capture, token, mock_notifier = integration_setup
    executor.set_active_macro("DummyMacro")
    executor.execute(cmd)

    # コマンド送信内容
    sent = fake_serial.sent
    press_expected = bytearray(
        [
            0xAB,
            Button.A & 0xFF,
            (Button.A >> 8) & 0xFF,
            Hat.CENTER,
            0x80,
            0x80,
            0x80,
            0x80,
            0x00,
            0x00,
            0x00,
        ]
    )
    release_expected = bytearray(
        [0xAB, 0x00, 0x00, Hat.CENTER, 0x80, 0x80, 0x80, 0x80, 0x00, 0x00, 0x00]
    )
    assert press_expected == sent[0]
    assert release_expected == sent[1]

    # キーボード入力
    keyboard_data = sent[2]
    assert keyboard_data[8] == 1  # kbdheader = 1 (PRESS)
    assert keyboard_data[9] == ord("H")  # 'H' の ASCII コード
    assert keyboard_data[10] == 0x00  # centinel は常に0

    # キャプチャ画像
    macro = executor.macro
    assert hasattr(macro, "captured_frame")
    frame = macro.captured_frame
    assert frame.shape == (720, 1280, 3)
    assert np.all(frame == 0)

    # ログ
    assert any("Initializing DummyMacro" in m for m in logs)
    assert any("Finalizing DummyMacro" in m for m in logs)


def test_macro_executor_exception_handling(integration_setup):
    """
    run()で例外発生時もfinalize()が必ず呼ばれることをMacroExecutor経由で検証
    """

    class ExceptionMacro(MacroBase):
        def initialize(self, cmd, args):
            cmd.log("init", level="INFO")

        def run(self, cmd):
            raise RuntimeError("fail!")

        def finalize(self, cmd):
            cmd.log("final", level="INFO")

    executor, cmd, *_ = integration_setup
    executor.macros = {"ExceptionMacro": ExceptionMacro()}
    executor.set_active_macro("ExceptionMacro")

    # 例外発生時はexecutor内でハンドリングされるが再スローされる
    # 例外が発生するかを確認
    with pytest.raises(RuntimeError):
        executor.execute(cmd)

    # 内部で例外が発生したことを確認
    assert any("fail!" in m for m in logs)
    # 例外が発生しても finalize() が呼ばれることを確認
    assert any("final" in m for m in logs)


def test_macro_executor_cancellation(integration_setup):
    """
    run()中にCancellationTokenで中断→MacroStopException→finalize()が呼ばれる
    """
    executor, cmd, fake_serial, fake_capture, token, mock_handler = integration_setup
    executor.set_active_macro("LongRunningMacro")

    def cancel():
        time.sleep(0.2)
        token.request_stop()

    # スレッドでキャンセルを実行
    t = threading.Thread(target=cancel)
    t.start()

    # マクロを実行
    # 例外が発生するまで待つ
    executor.execute(cmd)

    # スレッドが終了するのを待つ
    t.join()
    macro = executor.macro
    assert macro.finalized is True
    assert token.stop_requested()
    assert any("Finalizing LongRunningMacro" in m for m in logs)


def test_macro_executor_no_cancellation(integration_setup):
    """
    CancellationTokenが未発火ならLongRunningMacroが最後まで実行される
    """
    executor, cmd, fake_serial, fake_capture, token, mock_handler = integration_setup
    executor.set_active_macro("LongRunningMacro")
    token.clear()
    executor.execute(cmd)
    macro = executor.macro
    assert macro.finalized is True
    assert not token.stop_requested()
