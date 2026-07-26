"""swbt 例外を Project NyX の framework error へ変換する helper。"""

from nyxpy.framework.core.macro.exceptions import ConfigurationError, DeviceError

_CONNECT_CANCELLED_CODES = frozenset({"NYX_SWBT_PAIR_CANCELLED", "NYX_SWBT_RECONNECT_CANCELLED"})


def is_swbt_connect_cancelled(error: BaseException) -> bool:
    """Nested ExceptionGroup を含む接続操作の cancellation を識別する。"""
    if getattr(error, "code", None) in _CONNECT_CANCELLED_CODES:
        return True
    if isinstance(error, BaseExceptionGroup):
        return any(is_swbt_connect_cancelled(nested) for nested in error.exceptions)
    return False


def swbt_connect_cancel_code(error: BaseException) -> str | None:
    """Nested ExceptionGroup から接続キャンセルcodeを返す。"""
    code = getattr(error, "code", None)
    if code in _CONNECT_CANCELLED_CODES:
        return str(code)
    if isinstance(error, BaseExceptionGroup):
        for nested in error.exceptions:
            nested_code = swbt_connect_cancel_code(nested)
            if nested_code is not None:
                return nested_code
    return None


def swbt_user_error_message(error: BaseException) -> str:
    """利用者が原因を特定できる swbt error code と本文を返す。"""
    coded_error = _first_swbt_coded_error(error)
    if coded_error is None:
        return str(error)
    code, cause = coded_error
    return f"{code}: {cause}"


def _first_swbt_coded_error(error: BaseException) -> tuple[str, BaseException] | None:
    code = getattr(error, "code", None)
    if isinstance(code, str) and code.startswith("NYX_SWBT_"):
        return code, error
    if isinstance(error, BaseExceptionGroup):
        for nested in error.exceptions:
            coded_error = _first_swbt_coded_error(nested)
            if coded_error is not None:
                return coded_error
    return None


def is_swbt_pair_cancelled(error: BaseException) -> bool:
    """Pair cancellation の後方互換 helper。"""
    return getattr(error, "code", None) == "NYX_SWBT_PAIR_CANCELLED" or (
        isinstance(error, BaseExceptionGroup)
        and any(is_swbt_pair_cancelled(nested) for nested in error.exceptions)
    )


def adapter_discovery_failed(exc: BaseException) -> ConfigurationError:
    """Adapter discovery 失敗を NyX の設定エラーへ変換する。"""
    return ConfigurationError(
        "swbt adapter discovery failed",
        code="NYX_SWBT_ADAPTER_DISCOVERY_FAILED",
        component="SwbtAdapterDiscoveryService",
        details={"exception_type": type(exc).__name__},
        cause=exc,
    )


def swbt_configuration_error(
    message: str,
    *,
    code: str,
    component: str,
    cause: BaseException | None = None,
) -> ConfigurationError:
    """Swbt backend の設定・接続前条件エラーを作る。"""
    return ConfigurationError(
        message,
        code=code,
        component=component,
        cause=cause,
    )


def swbt_device_error(
    message: str,
    *,
    code: str,
    component: str,
    cause: BaseException | None = None,
) -> DeviceError:
    """Swbt backend の入力・実行時エラーを作る。"""
    return DeviceError(
        message,
        code=code,
        component=component,
        cause=cause,
    )


def imu_frame_count_invalid(count: int) -> DeviceError:
    """IMU frame 数不正を NyX の device error へ変換する。"""
    return DeviceError(
        "IMU input requires exactly 1 or 3 frames",
        code="NYX_IMU_FRAME_COUNT_INVALID",
        component="NyxSwbtInputMapper",
        details={"count": count},
    )


def swbt_port_closed() -> DeviceError:
    """Close 後の port 操作を NyX の device error へ変換する。"""
    return DeviceError(
        "swbt controller output port is closed",
        code="NYX_SWBT_PORT_CLOSED",
        component="SwbtControllerOutputPort",
    )


def swbt_not_connected(component: str = "SwbtControllerSession") -> DeviceError:
    """未接続 session 操作を NyX の device error へ変換する。"""
    return DeviceError(
        "swbt controller is not connected",
        code="NYX_SWBT_NOT_CONNECTED",
        component=component,
    )


def swbt_input_unsupported(message: str, *, component: str = "NyxSwbtInputMapper") -> DeviceError:
    """Controller type 非対応入力を NyX の device error へ変換する。"""
    return DeviceError(
        message,
        code="NYX_SWBT_INPUT_UNSUPPORTED",
        component=component,
    )


def swbt_input_invalid(message: str, *, component: str = "NyxSwbtInputMapper") -> DeviceError:
    """Swbt 入力値不正を NyX の device error へ変換する。"""
    return DeviceError(
        message,
        code="NYX_SWBT_INPUT_INVALID",
        component=component,
    )


def map_swbt_exception(exc: BaseException, *, component: str) -> ConfigurationError | DeviceError:
    """swbt-python の公開例外を framework error に変換する。"""
    name = type(exc).__name__
    if isinstance(exc, FileNotFoundError):
        return ConfigurationError(
            "swbt pairing profile was not found; run Pair to create it",
            code="NYX_SWBT_PROFILE_NOT_FOUND",
            component=component,
            cause=exc,
        )
    if isinstance(exc, FileExistsError):
        return ConfigurationError(
            "swbt pairing profile already exists",
            code="NYX_SWBT_PROFILE_ALREADY_EXISTS",
            component=component,
            cause=exc,
        )
    if name == "ProfileControllerMismatchError":
        return ConfigurationError(
            "swbt pairing profile belongs to a different controller type",
            code="NYX_SWBT_PROFILE_CONTROLLER_MISMATCH",
            component=component,
            details={
                "expected_controller_kind": str(getattr(exc, "expected_controller_kind", "")),
                "actual_controller_kind": str(getattr(exc, "actual_controller_kind", "")),
            },
            cause=exc,
        )
    if name == "InvalidProfileError":
        return ConfigurationError(
            "swbt pairing profile is invalid or uses an unsupported schema",
            code="NYX_SWBT_PROFILE_INVALID",
            component=component,
            cause=exc,
        )
    if name == "AdapterIdentityRecoveryRequired":
        return ConfigurationError(
            "swbt adapter identity recovery is required; unplug and reconnect the USB Bluetooth dongle before retrying",
            code="NYX_SWBT_ADAPTER_IDENTITY_RECOVERY_REQUIRED",
            component=component,
            details={
                "target_address": str(getattr(exc, "target_address", "")),
                "stage": str(getattr(exc, "stage", "")),
            },
            cause=exc,
        )
    if name == "TransportOpenError":
        return ConfigurationError(
            "swbt transport open failed",
            code="NYX_SWBT_TRANSPORT_OPEN_FAILED",
            component=component,
            cause=exc,
        )
    if name in {"ConnectionTimeoutError", "TimeoutError"}:
        return ConfigurationError(
            "swbt connection timed out",
            code="NYX_SWBT_CONNECTION_TIMED_OUT",
            component=component,
            cause=exc,
        )
    if name == "ConnectionFailedError":
        return ConfigurationError(
            "swbt connection failed",
            code="NYX_SWBT_CONNECTION_FAILED",
            component=component,
            cause=exc,
        )
    if name == "InvalidKeyStoreError":
        return ConfigurationError(
            "swbt pairing profile contains invalid key data",
            code="NYX_SWBT_PROFILE_KEY_DATA_INVALID",
            component=component,
            cause=exc,
        )
    if name == "UnsupportedInputError":
        return swbt_input_unsupported("swbt input is unsupported", component=component)
    if name == "InvalidInputError":
        return swbt_input_invalid("swbt input is invalid", component=component)
    if name == "ClosedError":
        return swbt_not_connected(component)
    return ConfigurationError(
        "swbt operation failed",
        code="NYX_SWBT_CONNECTION_FAILED",
        component=component,
        cause=exc,
    )
