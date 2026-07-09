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
