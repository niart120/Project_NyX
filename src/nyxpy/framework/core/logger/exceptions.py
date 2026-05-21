"""ログ管理の例外型。"""

from __future__ import annotations

from nyxpy.framework.core.macro.exceptions import ConfigurationError, ErrorKind, FrameworkError


class LoggingConfigurationError(ConfigurationError):
    """Logging 設定が不正で初期化できない場合の例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """Logging 設定不正の code を持つ configuration error として初期化します。"""
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_LOGGING_CONFIGURATION_INVALID")),
            component=str(kwargs.pop("component", "LoggingConfiguration")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class LogSinkError(FrameworkError):
    """Log sink への配送や処理が失敗した場合の recoverable error。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """Sink 失敗を recoverable internal error として初期化します。"""
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
    """Log payload を保存形式へ変換できない場合の例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """Serialization 失敗の code/component を設定します。"""
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_LOG_SERIALIZATION_FAILED")),
            component=str(kwargs.pop("component", "LogSanitizer")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )


class SecretMaskingError(LogSinkError):
    """Secret masking 中に log payload を安全に処理できない場合の例外。"""

    def __init__(self, message: str, **kwargs: object) -> None:
        """Secret masking 失敗の code/component を設定します。"""
        super().__init__(
            message,
            code=str(kwargs.pop("code", "NYX_LOG_SECRET_MASK_FAILED")),
            component=str(kwargs.pop("component", "LogSanitizer")),
            details=kwargs.pop("details", None),
            cause=kwargs.pop("cause", None),
        )
