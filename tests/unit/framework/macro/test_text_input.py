"""Command text input validation のテスト。"""

import pytest

from nyxpy.framework.core.macro.text_input import validate_keyboard_text


class TestValidateKeyboardText:
    """validate_keyboard_text のテスト"""

    def test_valid_ascii(self):
        """印刷可能 ASCII 文字が通る"""
        assert validate_keyboard_text("Hello World!") == "Hello World!"

    def test_empty_raises(self):
        """空文字列は ValueError"""
        with pytest.raises(ValueError, match="empty"):
            validate_keyboard_text("")

    def test_special_chars_allowed(self):
        """allow_special=True でタブ・改行を許可"""
        assert validate_keyboard_text("line1\nline2\ttab", allow_special=True)

    def test_special_chars_disallowed(self):
        """allow_special=False で改行は拒否"""
        with pytest.raises(ValueError):
            validate_keyboard_text("line1\nline2", allow_special=False)

    def test_non_ascii_rejected(self):
        """非 ASCII 文字は拒否"""
        with pytest.raises(ValueError, match="Unsupported"):
            validate_keyboard_text("日本語")

    def test_printable_range(self):
        """0x20〜0x7E の全文字が許可される"""
        all_printable = "".join(chr(i) for i in range(0x20, 0x7F))
        assert validate_keyboard_text(all_printable) == all_printable
