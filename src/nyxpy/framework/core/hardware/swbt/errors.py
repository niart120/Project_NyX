"""swbt 例外を Project NyX の framework error へ変換する helper。"""

from nyxpy.framework.core.macro.exceptions import ConfigurationError, DeviceError


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
    if name == "TransportOpenError":
        return ConfigurationError(
            "swbt transport open failed",
            code="NYX_SWBT_TRANSPORT_OPEN_FAILED",
            component=component,
            cause=exc,
        )
    if name == "ConnectionTimeoutError":
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
            "swbt key store is invalid",
            code="NYX_SWBT_KEY_STORE_INVALID",
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
