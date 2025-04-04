import time
import pytest
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.macro.constants import Button

# モックの SerialProtocol を定義
class MockSerialProtocol:
    def __init__(self):
        self.calls = []  # 呼び出し履歴を記録

    def build_press_command(self, keys):
        self.calls.append(('press', keys))
        # 簡易なダミー実装：キーのリストを文字列に変換して返す
        return b'press:' + b'-'.join(str(key).encode() for key in keys)

    def build_release_command(self, keys):
        self.calls.append(('release', keys))
        return b'release:' + b'-'.join(str(key).encode() for key in keys)

    def build_keyboard_command(self, text):
        self.calls.append(('keyboard', text))
        return b'keyboard:' + text.encode()

# モックの SerialManager を定義
class MockSerialManager:
    def __init__(self):
        self.sent_data = []

    def send(self, data: bytes) -> None:
        self.sent_data.append(data)

# ダミーの Command 用モック（ただし DefaultCommand で利用するため、こちらは SerialManager と Protocol のモックを注入する）
@pytest.fixture
def dummy_command(monkeypatch):
    # monkeypatch を用いて time.sleep をスキップ
    monkeypatch.setattr(time, "sleep", lambda x: None)

    mock_protocol = MockSerialProtocol()
    mock_serial_manager = MockSerialManager()
    cmd = DefaultCommand(serial_manager=mock_serial_manager, protocol=mock_protocol)
    # return cmd と共にモックも返して、検証に利用できるようにする
    return cmd, mock_protocol, mock_serial_manager

# 各テストケース

def test_press_operation(dummy_command):
    cmd, mock_protocol, mock_serial_manager = dummy_command
    # テスト対象: press() メソッド
    # Button.A と Button.B を同時に押下する（Button は IntEnum のため、直接利用）
    cmd.press(Button.A, Button.B, dur=0.2, wait=0.1)
    
    # DefaultCommand.press() 内では以下の流れになる:
    # 1. build_press_command() を呼び出し、送信
    # 2. time.sleep(dur)
    # 3. build_release_command() を呼び出し、送信
    # 4. time.sleep(wait)
    
    # モックの呼び出し履歴を検証
    assert mock_protocol.calls[0][0] == 'press'
    assert mock_protocol.calls[0][1] == (Button.A, Button.B)
    assert mock_protocol.calls[1][0] == 'release'
    assert mock_protocol.calls[1][1] == (Button.A, Button.B)
    
    # また、SerialManager の sent_data に2件のデータが送信されるはず
    assert len(mock_serial_manager.sent_data) == 2
    # 送信されたデータはモックプロトコルで生成した値であることを確認
    assert mock_serial_manager.sent_data[0].startswith(b'press:')
    assert mock_serial_manager.sent_data[1].startswith(b'release:')

def test_hold_operation(dummy_command):
    cmd, mock_protocol, mock_serial_manager = dummy_command
    # hold() は、build_press_command() を一度呼び出す設計
    cmd.hold(Button.X)
    assert mock_protocol.calls[0][0] == 'press'
    assert mock_protocol.calls[0][1] == (Button.X,)
    assert len(mock_serial_manager.sent_data) == 1
    assert mock_serial_manager.sent_data[0].startswith(b'press:')

def test_release_operation(dummy_command):
    cmd, mock_protocol, mock_serial_manager = dummy_command

    # release() を呼び出す。ここでは特定のキーを指定
    cmd.release(Button.A)
    assert mock_protocol.calls[0][0] == 'release'
    assert mock_protocol.calls[0][1] == (Button.A,)
    assert len(mock_serial_manager.sent_data) == 1
    assert mock_serial_manager.sent_data[0].startswith(b'release:')
    

def test_keyboard_operation(dummy_command):
    cmd, mock_protocol, mock_serial_manager = dummy_command
    cmd.keyboard("Test")
    assert mock_protocol.calls[0][0] == 'keyboard'
    assert mock_protocol.calls[0][1] == "Test"
    assert len(mock_serial_manager.sent_data) == 1
    assert mock_serial_manager.sent_data[0].startswith(b'keyboard:')

def test_wait_operation(dummy_command):
    cmd, mock_protocol, mock_serial_manager = dummy_command
    # wait() メソッドは単純に time.sleep を呼ぶが、monkeypatch により実際の待機はスキップされる
    start = time.time()
    cmd.wait(0.5)
    end = time.time()
    # 待機関数は実行されるが monkeypatch により待機しないので、実行時間は短いはず
    assert end - start < 0.1

def test_capture_operation(dummy_command):
    cmd, mock_protocol, mock_serial_manager = dummy_command
    result = cmd.capture()
    # capture() の実装例では単に None を返すため、それを確認
    assert result is None
