"""framework core の例外 hierarchy。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

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


class MacroStopException(FrameworkError):
    """既存 import 互換のため維持する中断例外 adapter。"""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """従来の可変引数を framework error の項目へ正規化します。"""
        message = str(args[0]) if args else str(kwargs.pop("message", ""))
        super().__init__(
            message,
            kind=kwargs.pop("kind", ErrorKind.CANCELLED),
            code=kwargs.pop("code", "NYX_MACRO_CANCELLED"),
            component=kwargs.pop("component", "MacroStopException"),
            recoverable=kwargs.pop("recoverable", False),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
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
            code=str(kwargs.pop("code", "NYX_DEVICE_SERIAL_FAILED")),
            component=str(kwargs.pop("component", "DeviceError")),
            recoverable=bool(kwargs.pop("recoverable", False)),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class ResourceError(FrameworkError):
    """Resource 読み書きや解決が失敗した場合の例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """Resource error kind と既定 code/component を設定します。"""
        super().__init__(
            message,
            kind=ErrorKind.RESOURCE,
            code=str(kwargs.pop("code", "NYX_RESOURCE_READ_FAILED")),
            component=str(kwargs.pop("component", "ResourceError")),
            recoverable=bool(kwargs.pop("recoverable", False)),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class ConfigurationError(FrameworkError, ValueError):
    """設定値、設定ファイル、実行構成が不正な場合の例外。"""

    def __init__(self, message: str = "", **kwargs: object) -> None:
        """Configuration error kind と既定 code/component を設定します。"""
        super().__init__(
            message,
            kind=ErrorKind.CONFIGURATION,
            code=str(kwargs.pop("code", "NYX_RUNTIME_CONFIGURATION_INVALID")),
            component=str(kwargs.pop("component", "ConfigurationError")),
            recoverable=bool(kwargs.pop("recoverable", False)),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class MacroRuntimeError(FrameworkError):
    """Macro 実行中の利用者 code 由来の失敗を表す例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """Macro error kind と既定 code/component を設定します。"""
        super().__init__(
            message,
            kind=ErrorKind.MACRO,
            code=str(kwargs.pop("code", "NYX_MACRO_FAILED")),
            component=str(kwargs.pop("component", "MacroRunner")),
            recoverable=bool(kwargs.pop("recoverable", False)),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
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
