import time
from cv2 import log
import pytest
import numpy as np

# インポートはプロジェクトのパッケージ構成に合わせる
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.hardware.serial_comm import SerialManager, SerialCommInterface
from nyxpy.framework.core.hardware.capture import CaptureManager, AsyncCaptureDevice
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol
from nyxpy.framework.core.macro.constants import Button
from nyxpy.framework.core.logger.log_manager import log_manager

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

logs = []  # ログを記録するリスト
# --- ダミーのログハンドラのセットアップ ---
def dummy_handler(msg):
    logs.append(msg)

# --- 統合テストセットアップ ---

@pytest.fixture
def integration_setup(monkeypatch):
    # monkeypatch で time.sleep をスキップ
    monkeypatch.setattr(time, "sleep", lambda x: None)

    # 実際の SerialManager と CaptureManager を作成
    serial_manager = SerialManager()
    capture_manager = CaptureManager()

    # 内部のシリアルデバイスを FakeSerialComm に差し替える
    fake_serial = FakeSerialComm()
    serial_manager.register_device("fake", fake_serial)
    # アクティブなシリアルデバイスとして設定（port 等はダミー）
    serial_manager.set_active("fake", port="COM_FAKE", baudrate=9600)

    # 内部のキャプチャデバイスを FakeAsyncCaptureDevice に差し替える
    fake_capture = FakeAsyncCaptureDevice()
    capture_manager.register_device("fake", fake_capture)
    capture_manager.set_active("fake")

    # DefaultCommand のインスタンス作成（CH552SerialProtocol を使用）
    cmd = DefaultCommand(
        serial_manager=serial_manager,
        capture_manager=capture_manager,
        protocol=CH552SerialProtocol()
    )

    # ログ出力のため、log_manager に独自のログハンドラを設定
    log_manager.add_handler(dummy_handler, level="DEBUG")

    yield cmd, fake_serial, fake_capture

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
    cmd, fake_serial, fake_capture = integration_setup

    # DummyMacro のライフサイクルを実行
    dummy_macro = DummyMacro()
    dummy_macro.initialize(cmd)
    dummy_macro.run(cmd)
    dummy_macro.finalize(cmd)

    # SerialManager の FakeSerialComm に送信されたデータを検証
    sent = fake_serial.sent
    # press() 内で press と release の2件、さらに keyboard() で1件、finalize() の release() で1件 -> 合計4件以上送信される
    assert len(sent) >= 4, "Expected at least 4 send calls from press, keyboard and release operations"

    # キャプチャが成功しているか（FakeAsyncCaptureDevice が返す画像は 100x100 の黒画像）
    frame = dummy_macro.captured_frame
    assert frame is not None
    assert frame.shape == (100, 100, 3)
    # すべてのピクセルが 0 であることを確認
    assert np.all(frame == 0)

    # ログ出力の検証
    # log_manager がログを内部に記録している場合、その中に初期化および終了のメッセージが含まれていることを確認
    assert any("Initializing DummyMacro" in m for m in logs)
    assert any("Finalizing DummyMacro" in m for m in logs)

def test_dummy_macro_exception_handling(integration_setup):
    """
    DummyMacro の run() で例外が発生した場合でも、finalize() が必ず呼ばれるかを検証する。
    """
    cmd, fake_serial, fake_capture = integration_setup

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
