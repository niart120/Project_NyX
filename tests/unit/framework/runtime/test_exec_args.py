"""Macro 実行引数 parser のテスト。"""

from __future__ import annotations

import pytest

from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.runtime.exec_args import parse_define_args


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
        """真偽値のパース"""
        result = parse_define_args(["flag=true"])
        assert result["flag"] is True

    def test_accepts_single_define_string(self):
        """単一文字列入力を 1 つの define として扱う"""
        result = parse_define_args("count=42")
        assert result["count"] == 42

    def test_accepts_iterable_defines(self):
        """リスト以外の Iterable[str] 入力を受け付ける"""
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
