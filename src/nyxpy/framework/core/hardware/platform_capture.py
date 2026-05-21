"""キャプチャ処理向けの platform 初期化。"""

from __future__ import annotations

import ctypes
import platform

from nyxpy.framework.core.macro.exceptions import ConfigurationError


def ensure_capture_coordinate_space() -> None:
    """Windows で DPI awareness を設定し、キャプチャ座標のずれを防ぎます。"""
    if platform.system() != "Windows":
        return
    try:
        awareness_context = ctypes.c_void_p(-4)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(awareness_context):
            return
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception as exc:
        raise ConfigurationError(
            "failed to configure Windows DPI awareness for capture",
            code="NYX_CAPTURE_DPI_AWARENESS_FAILED",
            component="platform_capture",
            cause=exc,
        ) from exc
