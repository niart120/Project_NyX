"""framework core の例外 hierarchy。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeGuard

type FrameworkValue = (
    str | int | float | bool | list[FrameworkValue] | dict[str, FrameworkValue] | None
)
type ErrorDetailValue = FrameworkValue


class ErrorKind(StrEnum):
    """Framework error の分類。"""

    CANCELLED = "cancelled"
    DEVICE = "device"
    RESOURCE = "resource"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    MACRO = "macro"
    INTERNAL = "internal"


class FrameworkError(Exception):
    """Framework 全体で扱う code/component 付きの基底例外。"""

    def __init__(
        self,
        message: str,
        *,
        kind: ErrorKind,
        code: str,
        component: str,
        recoverable: bool = False,
        details: dict[str, ErrorDetailValue] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        """Error kind、code、component、詳細、原因例外を保持します。"""
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.code = code
        self.component = component
        self.recoverable = recoverable
        self.details = dict(details or {})
        self.__cause__ = cause


def _is_error_detail_value(value: object) -> TypeGuard[ErrorDetailValue]:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_is_error_detail_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_error_detail_value(item) for key, item in value.items()
        )
    return False


def _pop_error_kind(kwargs: dict[str, object], key: str, default: ErrorKind) -> ErrorKind:
    value = kwargs.pop(key, default)
    if isinstance(value, ErrorKind):
        return value
    if isinstance(value, str):
        return ErrorKind(value)
    raise TypeError(f"{key} must be ErrorKind")


def _pop_str(kwargs: dict[str, object], key: str, default: str) -> str:
    value = kwargs.pop(key, default)
    return str(value)


def _pop_bool(kwargs: dict[str, object], key: str, default: bool) -> bool:
    value = kwargs.pop(key, default)
    return bool(value)


def _pop_details(
    kwargs: dict[str, object], key: str, default: dict[str, ErrorDetailValue] | None = None
) -> dict[str, ErrorDetailValue] | None:
    value = kwargs.pop(key, default)
    if value is None:
        return None
    if isinstance(value, dict):
        details: dict[str, ErrorDetailValue] = {}
        for detail_key, detail_value in value.items():
            if not isinstance(detail_key, str) or not _is_error_detail_value(detail_value):
                raise TypeError(f"{key} must be dict[str, ErrorDetailValue]")
            details[detail_key] = detail_value
        return details
    raise TypeError(f"{key} must be dict[str, ErrorDetailValue] | None")


def _pop_cause(
    kwargs: dict[str, object], key: str, default: BaseException | None = None
) -> BaseException | None:
    value = kwargs.pop(key, default)
    if value is None or isinstance(value, BaseException):
        return value
    raise TypeError(f"{key} must be BaseException | None")


class MacroStopException(FrameworkError):
    """既存 import 互換のため維持する中断例外 adapter。"""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """従来の可変引数を framework error の項目へ正規化します。"""
        message = str(args[0]) if args else str(kwargs.pop("message", ""))
        super().__init__(
            message,
            kind=_pop_error_kind(kwargs, "kind", ErrorKind.CANCELLED),
            code=_pop_str(kwargs, "code", "NYX_MACRO_CANCELLED"),
            component=_pop_str(kwargs, "component", "MacroStopException"),
            recoverable=_pop_bool(kwargs, "recoverable", False),
            details=_pop_details(kwargs, "details"),
            cause=_pop_cause(kwargs, "cause"),
        )


class MacroCancelled(MacroStopException):
    """協調キャンセルによりマクロ実行スレッドで送出される例外。"""


class DeviceError(FrameworkError):
    """Device や通信処理が失敗した場合の例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """Device error kind と既定 code/component を設定します。"""
        super().__init__(
            message,
            kind=ErrorKind.DEVICE,
            code=_pop_str(kwargs, "code", "NYX_DEVICE_SERIAL_FAILED"),
            component=_pop_str(kwargs, "component", "DeviceError"),
            recoverable=_pop_bool(kwargs, "recoverable", False),
            details=_pop_details(kwargs, "details"),
            cause=_pop_cause(kwargs, "cause"),
        )


class ResourceError(FrameworkError):
    """Resource 読み書きや解決が失敗した場合の例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """Resource error kind と既定 code/component を設定します。"""
        super().__init__(
            message,
            kind=ErrorKind.RESOURCE,
            code=_pop_str(kwargs, "code", "NYX_RESOURCE_READ_FAILED"),
            component=_pop_str(kwargs, "component", "ResourceError"),
            recoverable=_pop_bool(kwargs, "recoverable", False),
            details=_pop_details(kwargs, "details"),
            cause=_pop_cause(kwargs, "cause"),
        )


class ConfigurationError(FrameworkError, ValueError):
    """設定値、設定ファイル、実行構成が不正な場合の例外。"""

    def __init__(self, message: str = "", **kwargs: object) -> None:
        """Configuration error kind と既定 code/component を設定します。"""
        super().__init__(
            message,
            kind=ErrorKind.CONFIGURATION,
            code=_pop_str(kwargs, "code", "NYX_RUNTIME_CONFIGURATION_INVALID"),
            component=_pop_str(kwargs, "component", "ConfigurationError"),
            recoverable=_pop_bool(kwargs, "recoverable", False),
            details=_pop_details(kwargs, "details"),
            cause=_pop_cause(kwargs, "cause"),
        )


class MacroRuntimeError(FrameworkError):
    """Macro 実行中の利用者 code 由来の失敗を表す例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """Macro error kind と既定 code/component を設定します。"""
        super().__init__(
            message,
            kind=ErrorKind.MACRO,
            code=_pop_str(kwargs, "code", "NYX_MACRO_FAILED"),
            component=_pop_str(kwargs, "component", "MacroRunner"),
            recoverable=_pop_bool(kwargs, "recoverable", False),
            details=_pop_details(kwargs, "details"),
            cause=_pop_cause(kwargs, "cause"),
        )


@dataclass(frozen=True)
class ErrorInfo:
    """RunResult に保存する framework error の直列化済み情報。"""

    kind: ErrorKind
    code: str
    message: str
    component: str
    exception_type: str
    recoverable: bool
    details: dict[str, ErrorDetailValue] = field(default_factory=dict)
    traceback: str | None = None
