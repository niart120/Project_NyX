from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

type FrameworkValue = (
    str | int | float | bool | list[FrameworkValue] | dict[str, FrameworkValue] | None
)
type ErrorDetailValue = FrameworkValue


class ErrorKind(StrEnum):
    CANCELLED = "cancelled"
    DEVICE = "device"
    RESOURCE = "resource"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    MACRO = "macro"
    INTERNAL = "internal"


class FrameworkError(Exception):
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
    def __init__(self, message: str, **kwargs: object) -> None:
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
    def __init__(self, message: str, **kwargs: object) -> None:
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
    def __init__(self, message: str = "", **kwargs: object) -> None:
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
    def __init__(self, message: str, **kwargs: object) -> None:
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
    kind: ErrorKind
    code: str
    message: str
    component: str
    exception_type: str
    recoverable: bool
    details: dict[str, ErrorDetailValue] = field(default_factory=dict)
    traceback: str | None = None
