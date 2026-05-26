"""Macro 実行引数の parser。"""

from collections.abc import Iterable
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

from nyxpy.framework.core.macro.exceptions import ConfigurationError


def parse_define_args(defines: str | Iterable[str]) -> dict[str, Any]:
    """CLI / GUI の define 入力を TOML として解析します。"""
    if isinstance(defines, str):
        define_items = [defines]
    else:
        define_items = list(defines)

    for index, define in enumerate(define_items):
        if not isinstance(define, str):
            raise ConfigurationError(
                "define argument must be a string",
                code="NYX_DEFINE_INVALID",
                component="parse_define_args",
                details={"index": index},
            )
        key, separator, _value = define.partition("=")
        if not separator or not key.strip():
            raise ConfigurationError(
                "define argument must be key=value",
                code="NYX_DEFINE_INVALID",
                component="parse_define_args",
                details={"index": index},
            )

    try:
        return tomlkit.loads("\n".join(define_items))
    except TOMLKitError as exc:
        raise ConfigurationError(
            "failed to parse define arguments",
            code="NYX_DEFINE_PARSE_FAILED",
            component="parse_define_args",
            details={"exception_type": type(exc).__name__},
            cause=exc,
        ) from exc
