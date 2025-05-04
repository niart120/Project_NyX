import time
import pytest
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.constants import Button, KeyCode, KeyboardOp, SpecialKeyCode


# Mock for SerialCommInterface
class MockSerialDevice:
    def __init__(self):
        self.sent_data = []
    def send(self, data):
        self.sent_data.append(data)

# Mock for CaptureDeviceInterface
class MockCaptureDevice:
    def __init__(self):
        self._frame = None
        self.captured = False
    def get_frame(self):
        self.captured = True
        return self._frame


# Mock for ResourceIO
class MockResourceIO:
    def __init__(self):
        self.saved_images = {}

    def save_image(self, filename, image):
        self.saved_images[filename] = image

    def load_image(self, filename, grayscale=False):
        return self.saved_images.get(filename, None)


# Mock for Protocol
class MockProtocol:
    def __init__(self):
        self.calls = []

    def build_press_command(self, keys):
        self.calls.append(("press", keys))
        return b"press:" + b"-".join(str(k).encode() for k in keys)
    
    def build_hold_command(self, keys):
        self.calls.append(("hold", keys))
        return b"hold:" + b"-".join(str(k).encode() for k in keys)

    def build_release_command(self, keys):
        self.calls.append(("release", keys))
        return b"release:" + b"-".join(str(k).encode() for k in keys)

    def build_keyboard_command(self, text: str):
        self.calls.append(("keyboard_text", text))
        return f"keyboard_text:{text}".encode()

    def build_keytype_command(self, key: KeyCode | SpecialKeyCode, op: KeyboardOp):
        self.calls.append(("keyboard", key, op))
        return f"keyboard:{key}:{op.name}".encode()


# CH552のようにbuild_keyboard_commandが例外を投げるプロトコル用のモック
class MockProtocolKeyboardNotSupported(MockProtocol):
    def build_keyboard_command(self, text: str):
        raise NotImplementedError(
            "Mock protocol does not support text mode keyboard input. Use build_keytype_command instead."
        )


# Mock for CancellationToken
class MockCancellationToken:
    def __init__(self):
        self.stopped = False

    def request_stop(self):
        self.stopped = True

    def stop_requested(self):
        return self.stopped


@pytest.fixture
def dummy_command(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda x: None)
    serial_device = MockSerialDevice()
    capture_device = MockCaptureDevice()
    resource_io = MockResourceIO()
    protocol = MockProtocol()
    ct = MockCancellationToken()
    cmd = DefaultCommand(
        serial_device=serial_device,
        capture_device=capture_device,
        resource_io=resource_io,
        protocol=protocol,
        ct=ct,
        notification_handler=None,  # ここを追加
    )
    return cmd, serial_device, capture_device, resource_io, protocol, ct


@pytest.fixture
def dummy_command_keyboard_not_supported(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda x: None)
    serial_device = MockSerialDevice()
    capture_device = MockCaptureDevice()
    resource_io = MockResourceIO()
    protocol = MockProtocolKeyboardNotSupported()
    ct = MockCancellationToken()
    cmd = DefaultCommand(
        serial_device=serial_device,
        capture_device=capture_device,
        resource_io=resource_io,
        protocol=protocol,
        ct=ct,
        notification_handler=None,  # ここを追加
    )
    return cmd, serial_device, capture_device, resource_io, protocol, ct


def test_press_and_release(dummy_command):
    cmd, serial_device, capture_device, resource_io, protocol, ct = dummy_command
    cmd.press(Button.A, Button.B, dur=0.2, wait=0.1)
    assert protocol.calls[0][0] == "press"
    assert protocol.calls[1][0] == "release"
    assert serial_device.sent_data[0].startswith(b"press:")
    assert serial_device.sent_data[1].startswith(b"release:")


def test_hold(dummy_command):
    cmd, serial_device, capture_device, resource_io, protocol, ct = dummy_command
    cmd.hold(Button.X)
    assert protocol.calls[0][0] == "hold"
    assert serial_device.sent_data[0].startswith(b"hold:")


def test_release(dummy_command):
    cmd, serial_device, capture_device, resource_io, protocol, ct = dummy_command
    cmd.release(Button.Y)
    assert protocol.calls[0][0] == "release"
    assert serial_device.sent_data[0].startswith(b"release:")


def test_wait(dummy_command):
    cmd, *_ = dummy_command
    start = time.time()
    cmd.wait(0.5)
    end = time.time()
    assert end - start < 0.1  # monkeypatchで即時


def test_stop(dummy_command):
    cmd, _, _, _, _, ct = dummy_command
    with pytest.raises(Exception):
        cmd.stop()
    assert ct.stopped


def test_keyboard_text_mode(dummy_command):
    """テキストモード対応プロトコルでのkeyboardメソッドのテスト"""
    cmd, serial_device, capture_device, resource_io, protocol, _ = dummy_command
    cmd.keyboard("Hello")

    # build_keyboard_commandとbuild_keytype_commandの呼び出しが行われていることを確認
    assert len(protocol.calls) == 2
    assert protocol.calls[0][0] == "keyboard_text"
    assert protocol.calls[0][1] == "Hello"

    assert protocol.calls[1][0] == "keyboard"
    assert protocol.calls[1][1] == KeyCode("")
    assert protocol.calls[1][2] == KeyboardOp.ALL_RELEASE

    # 送信されたデータが正しいか確認
    assert serial_device.sent_data[0].decode().startswith("keyboard_text:Hello")


def test_keyboard_keytype_mode(dummy_command_keyboard_not_supported):
    """テキストモード非対応プロトコルでのkeyboardメソッドのテスト（keytype委譲）"""
    cmd, serial_device, capture_device, resource_io, protocol, _ = dummy_command_keyboard_not_supported
    cmd.keyboard("Hello")

    # 各文字ごとに押下→解放のシーケンスが実行されることを確認
    assert (
        len(protocol.calls) == 11
    )  # "Hello"の5文字 × 2 (押下・解放) + 1 (ALL_RELEASE)

    # 最初の文字 'H' の押下
    assert protocol.calls[0][0] == "keyboard"
    assert protocol.calls[0][1] == KeyCode("H")
    assert protocol.calls[0][2] == KeyboardOp.PRESS

    # 最初の文字 'H' の解放
    assert protocol.calls[1][0] == "keyboard"
    assert protocol.calls[1][1] == KeyCode("H")
    assert protocol.calls[1][2] == KeyboardOp.RELEASE

    # 最後の文字 'o' の解放
    assert protocol.calls[9][0] == "keyboard"
    assert protocol.calls[9][1] == KeyCode("o")
    assert protocol.calls[9][2] == KeyboardOp.RELEASE

    # 最後の ALL_RELEASE コマンド
    assert protocol.calls[10][0] == "keyboard"
    assert protocol.calls[10][1] == KeyCode("")
    assert protocol.calls[10][2] == KeyboardOp.ALL_RELEASE

    # 送信されたデータが正しいか確認
    assert (
        serial_device.sent_data[0]
        .decode()
        .startswith(f"keyboard:{KeyCode('H')}:PRESS")
    )


def test_keyboard_empty_string(dummy_command):
    """空文字列の場合、validate_keyboard_text が ValueErrorを発生させるはず"""
    cmd, _, _, resource_io, protocol, _ = dummy_command

    # 空文字列を渡すと例外が発生することを確認
    with pytest.raises(ValueError, match="Input text is empty"):
        cmd.keyboard("")

    # 呼び出しが行われていないことを確認
    assert len(protocol.calls) == 0


def test_keyboard_validation_called(dummy_command_keyboard_not_supported):
    """validate_keyboard_text の動作確認（有効な入力文字）"""
    cmd, _, _, resource_io, protocol, _ = dummy_command_keyboard_not_supported

    # 通常のASCII文字が正しく処理されることを確認
    cmd.keyboard("test123")

    # 各文字が適切に処理されていることを確認
    assert len(protocol.calls) == 15  # 7文字 × 2 + ALL_RELEASE

    # 最初の文字 't' の押下
    assert protocol.calls[0][0] == "keyboard"
    assert protocol.calls[0][1] == KeyCode("t")
    assert protocol.calls[0][2] == KeyboardOp.PRESS

    # 数字も正しく処理されていることを確認
    assert protocol.calls[8][0] == "keyboard"
    assert protocol.calls[8][1] == KeyCode("1")
    assert protocol.calls[8][2] == KeyboardOp.PRESS

    assert protocol.calls[12][0] == "keyboard"
    assert protocol.calls[12][1] == KeyCode("3")
    assert protocol.calls[12][2] == KeyboardOp.PRESS


def test_keyboard_special_chars(dummy_command_keyboard_not_supported):
    """特殊文字の処理が正しく行われるか確認"""
    cmd, _, _, resource_io, protocol, _ = dummy_command_keyboard_not_supported

    # 特殊文字を含むテキストを送信
    cmd.keyboard("\n\t")

    # 各文字ごとに適切なコマンドが呼ばれていることを確認

    # press/release で1回ずつコマンドが発行されるはず
    assert protocol.calls[0][1] == KeyCode("\n")
    assert protocol.calls[1][1] == KeyCode("\n")
    assert protocol.calls[2][1] == KeyCode("\t")
    assert protocol.calls[3][1] == KeyCode("\t")


def test_keyboard_invalid_character(dummy_command):
    """無効な文字（制御文字など）を含む場合はエラーが発生することを確認"""
    cmd, _, _, resource_io, protocol, _ = dummy_command

    # 無効な文字（ここでは制御文字(ビープ)）を含むテキストでエラーになることを確認
    with pytest.raises(ValueError, match="Unsupported character"):
        cmd.keyboard("test\x07")

    # 最初のバリデーションチェックで止まるためプロトコル呼び出しは起こらない
    assert len(protocol.calls) == 0


def test_save_img_and_load_img(dummy_command):
    cmd, _, _, resource_io, _, _ = dummy_command
    dummy_img = b"img"
    cmd.save_img("foo.png", dummy_img)
    assert resource_io.saved_images["foo.png"] == dummy_img
    loaded = cmd.load_img("foo.png")
    assert loaded == dummy_img


def test_capture_success(monkeypatch, dummy_command):
    cmd, serial_device, capture_device, _, _, _ = dummy_command
    import numpy as np

    # 1280x720x3 のダミーフレーム
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    capture_device._frame = dummy_frame
    result = cmd.capture()
    assert result.shape == (720, 1280, 3)


def test_capture_crop_and_gray(monkeypatch, dummy_command):
    cmd, serial_device, capture_device, _, _, _ = dummy_command
    import numpy as np

    dummy_frame = np.ones((720, 1280, 3), dtype=np.uint8) * 255
    capture_device._frame = dummy_frame
    # クロップ領域指定
    crop = (100, 100, 200, 200)
    result = cmd.capture(crop_region=crop, grayscale=True)
    assert result.shape == (200, 200)
    assert result.dtype == dummy_frame.dtype


def test_capture_crop_out_of_bounds(dummy_command):
    cmd, serial_device, capture_device, _, _, _ = dummy_command
    import numpy as np

    dummy_frame = np.ones((720, 1280, 3), dtype=np.uint8)
    capture_device._frame = dummy_frame
    with pytest.raises(ValueError):
        cmd.capture(crop_region=(1200, 700, 200, 200))


def test_keyboard_type(dummy_command):
    """単一キーのタイプ操作のテスト"""
    cmd, serial_device, capture_device, _, protocol, _ = dummy_command
    cmd.type(KeyCode("X"))

    # PRESS操作とRELEASE操作が実行されることを確認
    assert len(protocol.calls) == 2
    assert protocol.calls[0][0] == "keyboard"
    assert protocol.calls[0][1] == KeyCode("X")
    assert protocol.calls[0][2] == KeyboardOp.PRESS

    assert protocol.calls[1][0] == "keyboard"
    assert protocol.calls[1][1] == KeyCode("X")
    assert protocol.calls[1][2] == KeyboardOp.RELEASE

    # 送信されたデータが正しいか確認
    assert serial_device.sent_data[0].decode().startswith("keyboard:X:PRESS")
    assert serial_device.sent_data[1].decode().startswith("keyboard:X:RELEASE")


# Mock for NotificationHandler
class MockNotificationHandler:
    def __init__(self):
        self.calls = []
    def publish(self, text, img=None):
        self.calls.append((text, img))


def test_notify_calls_notification_handler(monkeypatch):
    serial_device = MockSerialDevice()
    capture_device = MockCaptureDevice()
    resource_io = MockResourceIO()
    protocol = MockProtocol()
    ct = MockCancellationToken()
    mock_notifier = MockNotificationHandler()
    cmd = DefaultCommand(
        serial_device=serial_device,
        capture_device=capture_device,
        resource_io=resource_io,
        protocol=protocol,
        ct=ct,
        notification_handler=mock_notifier,
    )
    # テキストのみ
    cmd.notify("通知テスト")
    assert mock_notifier.calls[0][0] == "通知テスト"
    assert mock_notifier.calls[0][1] is None
    # 画像付き
    dummy_img = b"dummy_img"
    cmd.notify("画像付き通知", img=dummy_img)
    assert mock_notifier.calls[1][0] == "画像付き通知"
    assert mock_notifier.calls[1][1] == dummy_img
