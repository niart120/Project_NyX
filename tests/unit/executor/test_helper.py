"""
helper.py ユニットテスト

parse_define_args / validate_keyboard_text / extract_macro_tags /
calc_aspect_size のテストを提供する。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.utils.helper import (
    calc_aspect_size,
    extract_macro_tags,
    parse_define_args,
    validate_keyboard_text,
)

# ============================================================
# parse_define_args テスト
# ============================================================


class TestParseDefineArgs:
    """parse_define_args のテスト"""

    def test_simple_key_value(self):
        """key=value 形式の単一引数"""
        result = parse_define_args(['key1="hello"'])
        assert result["key1"] == "hello"

    def test_integer_value(self):
        """整数値のパース"""
        result = parse_define_args(["count=42"])
        assert result["count"] == 42

    def test_multiple_defines(self):
        """複数の -D 引数"""
        result = parse_define_args(['name="test"', "value=100"])
        assert result["name"] == "test"
        assert result["value"] == 100

    def test_empty_list(self):
        """空リスト → 空 dict"""
        result = parse_define_args([])
        assert result == {}

    def test_boolean_value(self):
        """bool 値のパース"""
        result = parse_define_args(["flag=true"])
        assert result["flag"] is True

    def test_accepts_single_define_string(self):
        """単一文字列入力を 1 つの define として扱う"""
        result = parse_define_args("count=42")
        assert result["count"] == 42

    def test_accepts_iterable_defines(self):
        """list 以外の Iterable[str] 入力を受け付ける"""
        result = parse_define_args(iter(['name="test"', "value=100"]))
        assert result["name"] == "test"
        assert result["value"] == 100

    def test_equal_sign_inside_string_value(self):
        """値の中の = を壊さず TOML として解釈する"""
        result = parse_define_args(['token="a=b"'])
        assert result["token"] == "a=b"

    def test_invalid_missing_separator_raises_configuration_error(self):
        with pytest.raises(ConfigurationError) as exc_info:
            parse_define_args(["flag"])

        assert exc_info.value.code == "NYX_DEFINE_INVALID"
        assert exc_info.value.component == "parse_define_args"

    def test_invalid_toml_raises_configuration_error(self):
        with pytest.raises(ConfigurationError) as exc_info:
            parse_define_args(['name="unterminated'])

        assert exc_info.value.code == "NYX_DEFINE_PARSE_FAILED"
        assert exc_info.value.component == "parse_define_args"


# ============================================================
# validate_keyboard_text テスト
# ============================================================


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


# ============================================================
# extract_macro_tags テスト
# ============================================================


class TestExtractMacroTags:
    """extract_macro_tags のテスト"""

    def test_unique_sorted(self):
        """重複が排除されソート済みで返る"""
        macros = {
            "A": SimpleNamespace(tags=["beta", "alpha"]),
            "B": SimpleNamespace(tags=["alpha", "gamma"]),
        }
        assert extract_macro_tags(macros) == ["alpha", "beta", "gamma"]

    def test_empty_macros(self):
        """空の辞書 → 空リスト"""
        assert extract_macro_tags({}) == []

    def test_no_tags_attribute(self):
        """tags 属性がないマクロは無視される"""
        macros = {"A": SimpleNamespace()}  # tags なし
        assert extract_macro_tags(macros) == []


# ============================================================
# calc_aspect_size テスト
# ============================================================


class TestCalcAspectSize:
    """calc_aspect_size のテスト"""

    def test_wider_than_16_9(self):
        """横長のサイズ → 高さ基準でフィット"""
        size = SimpleNamespace(width=lambda: 1920, height=lambda: 600)
        w, h = calc_aspect_size(size)
        assert h == 600
        assert w == int(600 * 16 / 9)

    def test_exact_16_9(self):
        """16:9 ぴったりのサイズ"""
        size = SimpleNamespace(width=lambda: 1600, height=lambda: 900)
        w, h = calc_aspect_size(size)
        assert w == 1600
        assert h == 900

    def test_taller_than_16_9(self):
        """縦長のサイズ → 幅基準でフィット"""
        size = SimpleNamespace(width=lambda: 800, height=lambda: 900)
        w, h = calc_aspect_size(size)
        assert w == 800
        assert h == int(800 * 9 / 16)

    def test_custom_aspect(self):
        """カスタムアスペクト比 (4:3)"""
        size = SimpleNamespace(width=lambda: 800, height=lambda: 600)
        w, h = calc_aspect_size(size, aspect_w=4, aspect_h=3)
        assert w == 800
        assert h == 600
