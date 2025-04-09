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
from nyxpy.framework.core.macro.constants import Button
from nyxpy.framework.core.logger.log_manager import log_manager
from nyxpy.framework.core.macro.exceptions import MacroStopException
from nyxpy.framework.core.utils.cancellation import CancellationToken

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
    def __init__(self, device_index: int = 0, interval: float = 1.0/30.0):
        super().__init__(device_index, interval)

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
    def initialize(self, cmd):
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

    def initialize(self, cmd):
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

    # 実際の SerialManager と CaptureManager を作成
    serial_manager = SerialManager()
    capture_manager = CaptureManager()

    # 内部のシリアルデバイスを FakeSerialComm に差し替える
    fake_serial = FakeSerialComm()
    serial_manager.register_device("fake", fake_serial)
    # アクティブなシリアルデバイスとして設定
    serial_manager.set_active("fake", baudrate=9600)

    # 内部のキャプチャデバイスを FakeAsyncCaptureDevice に差し替える
    fake_capture = FakeAsyncCaptureDevice()
    capture_manager.register_device("fake", fake_capture)
    capture_manager.set_active("fake")

    # FakeResourceIO を作成
    resource_io = FakeResourceIO()

    # DefaultCommand のインスタンス作成（CH552SerialProtocol を使用）
    cmd = DefaultCommand(
        serial_manager=serial_manager,
        capture_manager=capture_manager,
        resource_io=resource_io,
        protocol=CH552SerialProtocol(),
        ct=token
    )

    # ログ出力のため、log_manager に独自のログハンドラを設定
    log_manager.add_handler(dummy_handler, level="DEBUG")

    yield cmd, fake_serial, fake_capture, token

    # テスト後にログハンドラを元に戻す
    log_manager.remove_handler(dummy_handler)
    # シリアルデバイスとキャプチャデバイスを解放
    # FakeSerialComm と FakeAsyncCaptureDevice は自動的に解放される
    serial_manager.active_device.close()
    capture_manager.active_device.release()

    # ログをクリア
    logs.clear()


# --- 統合テストケース ---

def test_dummy_macro_normal(integration_setup):
    cmd, fake_serial, fake_capture, token = integration_setup

    # DummyMacro のライフサイクルを実行
    dummy_macro = DummyMacro()
    dummy_macro.initialize(cmd)
    dummy_macro.run(cmd)
    dummy_macro.finalize(cmd)

    # SerialManager の FakeSerialComm に送信されたデータを検証
    sent = fake_serial.sent
    # press() 内で press と release の2件、さらに keyboard() で1件、finalize() の release() で1件 -> 合計4件以上送信される
    assert len(sent) >= 4, "Expected at least 4 send calls from press, keyboard and release operations"

    # キャプチャが成功しているか（FakeAsyncCaptureDevice が返す画像は 100x100 の黒画像だが、リスケールが走ることを確認する）
    frame = dummy_macro.captured_frame
    assert frame is not None
    assert frame.shape == (720, 1280, 3) #height=720, width=1280, channels=3
    # すべてのピクセルが 0 であることを確認
    assert np.all(frame == 0)

    # ログ出力の検証
    # log_manager がログを内部に記録している場合、その中に初期化および終了のメッセージが含まれていることを確認
    assert any("Initializing DummyMacro" in m for m in logs)
    assert any("Finalizing DummyMacro" in m for m in logs)

def test_dummy_macro_exception_handling(integration_setup):
    """
    DummyMacro の run() で例外が発生した場合でも、ハンドリングによってfinalize() を呼ぶことが出来るかを検証する。
    """
    cmd, fake_serial, fake_capture, token = integration_setup

    class ExceptionMacro(MacroBase):
        def initialize(self, cmd):
            cmd.log("Initializing ExceptionMacro", level="INFO")
        def run(self, cmd):
            cmd.press(Button.A, dur=0.1, wait=0.1)
            raise ValueError("Intentional Error")
        def finalize(self, cmd):
            cmd.release(Button.A)
            cmd.log("Finalizing ExceptionMacro", level="INFO")

    macro = ExceptionMacro()

    try:
        macro.initialize(cmd)
        macro.run(cmd)
    except ValueError:
        pass
    macro.finalize(cmd)

    # ログに "Finalizing ExceptionMacro" が含まれているか検証
    assert any("Initializing ExceptionMacro" in m for m in logs)
    assert any("Finalizing ExceptionMacro" in m for m in logs)

def test_macro_cancellation(integration_setup):
    """
    LongRunningMacro の実行中に外部から CancellationToken.cancel() を呼び出し、
    マクロ実行が中断されることを検証する。
    最終的に finalize() が呼ばれることも確認する。
    """
    cmd, fake_serial, fake_capture, token  = integration_setup
    macro = LongRunningMacro()

    # 別スレッドで中断要求を発行する
    def cancel_after_delay():
        # 数回の操作後にキャンセル要求（ここでは 0.3秒後とする）
        time.sleep(0.3)
        cmd.log("Cancellation requested from external event", level="INFO")
        token.request_stop()
    
    cancel_thread = threading.Thread(target=cancel_after_delay)
    cancel_thread.start()
    
    # マクロ実行を MacroExecutor でラップする場合：
    # ここでは直接呼び出しを行い、run() 中にキャンセル例外が発生することを検証する
    with pytest.raises(MacroStopException):
        macro.initialize(cmd)
        macro.run(cmd)
    # 例外が発生した後、必ず finalize() を呼び出す
    macro.finalize(cmd)
    cancel_thread.join()

    # キャンセル要求のログが含まれているか検証
    assert any("Cancellation requested from external event" in m for m in logs)
    # 外部要求によってキャンセルされたことを確認
    assert token.stop_requested() is True
    # 最終的に macro.finalize() が実行されたか確認
    assert macro.finalized is True
    # ログに "Finalizing LongRunningMacro" が含まれているか検証
    assert any("Finalizing LongRunningMacro" in m for m in logs)

def test_no_cancellation(integration_setup):
    """
    CancellationToken がキャンセルされていない場合、LongRunningMacro が最後まで実行されることを検証する。
    """
    cmd, fake_serial, fake_capture, token  = integration_setup
    macro = LongRunningMacro()
    
    # 確実にキャンセルされないように token を初期状態のまま保持
    token.clear()  # 余計なキャンセルフラグが立っていないか確認
    
    # 実行中に例外は発生しないはず
    macro.initialize(cmd)
    macro.run(cmd)
    macro.finalize(cmd)
    
    # 実行が最後まで完了し、finalize() が呼ばれたはず
    assert macro.finalized is True
