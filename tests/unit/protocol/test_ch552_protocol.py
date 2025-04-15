import pytest
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol
from nyxpy.framework.core.macro.constants import Button, Hat, LStick, RStick, KeyboardOp

# テスト用にスティック操作のためのサブクラスが必要であれば、実装済みのものを利用
# ここでは実際の LStick, RStick をそのまま利用します

@pytest.fixture
def protocol():
    # 各テストごとに新しいインスタンスを返す
    return CH552SerialProtocol()

def test_press_single_button(protocol):
    # Button.A の押下テスト
    press_data = protocol.build_press_command((Button.A,))
    expected = bytearray([0xAB,
                          Button.A & 0xFF,
                          (Button.A >> 8) & 0xFF,
                          Hat.CENTER,
                          0x80, 0x80, 0x80, 0x80,
                          0x00, 0x00, 0x00])
    assert press_data == bytes(expected)

def test_press_multiple_keys(protocol):
    # Button.A, Button.B, Hat.UP, LStick.UP の同時押下テスト
    press_data = protocol.build_press_command((Button.A, Button.B, Hat.UP, LStick.UP))
    expected = bytearray([0xAB,
                          (Button.A & 0xFF) | (Button.B & 0xFF),
                          ((Button.A >> 8) & 0xFF) | ((Button.B >> 8) & 0xFF),
                          Hat.UP,
                          LStick.UP.x, LStick.UP.y,
                          0x80, 0x80,
                          0x00, 0x00, 0x00])
    assert press_data == bytes(expected)

def test_release_specific_keys(protocol):
    # まず、押下状態を作る
    _ = protocol.build_press_command((Button.A, LStick.UP))
    # Button.A と LStick.UP の解放テスト
    release_data = protocol.build_release_command((Button.A, LStick.UP))
    expected = bytearray([0xAB,
                          0x00,  # Button.A クリア
                          0x00,
                          Hat.CENTER,  # Hat はリセットしない場合、もしくはそのままの状態かもしれない
                          0x80, 0x80,  # LStick 解放で中央にリセット
                          0x80, 0x80,
                          0x00, 0x00, 0x00])
    assert release_data == bytes(expected)

def test_release_reset_all(protocol):
    # 何も渡さない場合、全体リセットが行われる
    # まず、押下状態を作る
    _ = protocol.build_press_command((Button.A, LStick.UP))
    release_data = protocol.build_release_command(())
    expected = bytearray([0xAB,
                          0x00, 0x00,
                          Hat.CENTER,
                          0x80, 0x80, 0x80, 0x80,
                          0x00, 0x00, 0x00])
    assert release_data == bytes(expected)

def test_keyboard_command_press(protocol):
    # 通常キー押下のテスト
    kb_data = protocol.build_keyboard_command("H", KeyboardOp.PRESS)
    expected = bytearray([0xAB,
                          0x00, 0x00,
                          Hat.CENTER,
                          0x80, 0x80, 0x80, 0x80,
                          int(KeyboardOp.PRESS),  # kbdheader = 1
                          ord('H'),
                          0x00])  # 末尾は常に0
    assert kb_data == bytes(expected)

def test_keyboard_command_release(protocol):
    # 通常キーリリースのテスト
    kb_data = protocol.build_keyboard_command("H", KeyboardOp.RELEASE)
    expected = bytearray([0xAB,
                          0x00, 0x00,
                          Hat.CENTER,
                          0x80, 0x80, 0x80, 0x80,
                          int(KeyboardOp.RELEASE),  # kbdheader = 2
                          ord('H'),
                          0x00])
    assert kb_data == bytes(expected)

def test_keyboard_command_special_press(protocol):
    # 特殊キー押下のテスト
    kb_data = protocol.build_keyboard_command("A", KeyboardOp.SPECIAL_PRESS)
    expected = bytearray([0xAB,
                          0x00, 0x00,
                          Hat.CENTER,
                          0x80, 0x80, 0x80, 0x80,
                          int(KeyboardOp.SPECIAL_PRESS),  # kbdheader = 3
                          ord('A'),
                          0x00])
    assert kb_data == bytes(expected)

def test_keyboard_command_all_release(protocol):
    # 全キーリリースのテスト
    kb_data = protocol.build_keyboard_command("", KeyboardOp.ALL_RELEASE)
    expected = bytearray([0xAB,
                          0x00, 0x00,
                          Hat.CENTER,
                          0x80, 0x80, 0x80, 0x80,
                          int(KeyboardOp.ALL_RELEASE),  # kbdheader = 5
                          0x00,  # キーなし
                          0x00])
    assert kb_data == bytes(expected)

def test_keyboard_command_empty_key(protocol):
    # 空文字で通常キー押下のテスト - 無視されるべき
    kb_data = protocol.build_keyboard_command("", KeyboardOp.PRESS)
    expected = bytearray([0xAB,
                          0x00, 0x00,
                          Hat.CENTER,
                          0x80, 0x80, 0x80, 0x80,
                          int(KeyboardOp.PRESS),
                          0x00,  # 空文字なので0
                          0x00])
    assert kb_data == bytes(expected)

def test_stick_values(protocol):
    # LStick, RStick のプリセットが正しく使われるかのテスト
    press_data = protocol.build_press_command((LStick.RIGHT, RStick.UP))
    expected = bytearray([0xAB,
                          0x00, 0x00,
                          Hat.CENTER,
                          LStick.RIGHT.x, LStick.RIGHT.y,
                          RStick.UP.x, RStick.UP.y,
                          0x00, 0x00, 0x00])
    assert press_data == bytes(expected)
