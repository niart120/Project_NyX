from __future__ import annotations

from nyxpy.framework.core.macro.exceptions import ConfigurationError, ErrorKind, FrameworkError


class LoggingConfigurationError(ConfigurationError):
    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_LOGGING_CONFIGURATION_INVALID")),
            component=str(kwargs.pop("component", "LoggingConfiguration")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class LogSinkError(FrameworkError):
    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(
            message,
            kind=ErrorKind.INTERNAL,
            code=str(kwargs.pop("code", "NYX_LOG_SINK_FAILED")),
            component=str(kwargs.pop("component", "LogSinkDispatcher")),
            recoverable=True,
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class LogSerializationError(LogSinkError):
    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_LOG_SERIALIZATION_FAILED")),
            component=str(kwargs.pop("component", "LogSanitizer")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class SecretMaskingError(LogSinkError):
    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_LOG_SECRET_MASK_FAILED")),
            component=str(kwargs.pop("component", "LogSanitizer")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )
