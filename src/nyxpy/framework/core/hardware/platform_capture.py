"""キャプチャ処理向けの platform 初期化。"""

import ctypes
import platform

from nyxpy.framework.core.macro.exceptions import ConfigurationError


def ensure_capture_coordinate_space() -> None:
    """Windows で DPI awareness を設定し、キャプチャ座標のずれを防ぎます。"""
    if platform.system() != "Windows":
        return
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        raise ConfigurationError(
            "ctypes.windll is required to configure Windows DPI awareness",
            code="NYX_CAPTURE_DPI_AWARENESS_FAILED",
            component="platform_capture",
        )
    try:
        awareness_context = ctypes.c_void_p(-4)
        if windll.user32.SetProcessDpiAwarenessContext(awareness_context):
            return
        windll.shcore.SetProcessDpiAwareness(2)
    except Exception as exc:
        raise ConfigurationError(
            "failed to configure Windows DPI awareness for capture",
            code="NYX_CAPTURE_DPI_AWARENESS_FAILED",
            component="platform_capture",
            cause=exc,
        ) from exc
