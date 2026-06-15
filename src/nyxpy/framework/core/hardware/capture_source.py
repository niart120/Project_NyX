"""キャプチャ入力元の設定 model。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from nyxpy.framework.core.hardware.frame_transform import FrameTransformConfig
from nyxpy.framework.core.macro.exceptions import ConfigurationError

CaptureSourceType = Literal["camera", "window", "capture"]
WindowMatchMode = Literal["exact", "contains"]
CaptureBackendName = Literal["auto", "mss", "windows_graphics_capture"]
PonkanBackendName = Literal["auto", "d3xx", "d3xx-native"]
PonkanDropPolicy = Literal["drop_oldest", "drop_newest", "block"]


@dataclass(frozen=True)
class CaptureRect:
    """画面キャプチャ対象の矩形領域。"""

    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        """キャプチャ範囲のサイズを検証します。"""
        if self.width <= 0 or self.height <= 0:
            raise ConfigurationError(
                "capture region width and height must be positive",
                code="NYX_CAPTURE_REGION_INVALID",
                component="CaptureSourceConfig",
                details={"width": self.width, "height": self.height},
            )

    def to_mss_monitor(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class CameraCaptureSourceConfig:
    """カメラ型キャプチャ入力元の設定。"""

    device_name: str = ""
    source_type: Literal["camera"] = "camera"
    fps: float = 60.0
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)


@dataclass(frozen=True)
class WindowCaptureSourceConfig:
    """Window capture 入力元の検索条件と backend 設定。"""

    title_pattern: str = ""
    source_type: Literal["window"] = "window"
    match_mode: WindowMatchMode = "exact"
    identifier: str | int | None = None
    backend: CaptureBackendName = "auto"
    fps: float = 30.0
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)


@dataclass(frozen=True)
class PonkanCaptureSourceConfig:
    """ponkan-python を使う直接接続型キャプチャ入力元の設定。"""

    source_type: Literal["capture"] = "capture"
    provider: Literal["ponkan"] = "ponkan"
    device_profile: str = "n3dsxl"
    ponkan_backend: PonkanBackendName = "auto"
    raw_slots: int = 2
    output_queue_size: int = 2
    drop_policy: PonkanDropPolicy = "drop_oldest"
    poll_interval: float = 0.004
    read_timeout: float | None = 1.0
    collect_timing: bool = False
    transform: FrameTransformConfig = field(
        default_factory=lambda: FrameTransformConfig(aspect_box_enabled=True)
    )


CaptureSourceConfig = (
    CameraCaptureSourceConfig | WindowCaptureSourceConfig | PonkanCaptureSourceConfig
)


@dataclass(frozen=True)
class CaptureSourceKey:
    """Frame source の再利用判定に使う正規化済み key。"""

    source_type: CaptureSourceType
    identifier: str
    backend: str
    fps: float
    region: CaptureRect | None = None
    match_mode: str = ""
    provider: str = ""
    device_profile: str = ""
    raw_slots: int = 0
    output_queue_size: int = 0
    drop_policy: str = ""
    poll_interval: float = 0.0
    read_timeout: float | None = None
    collect_timing: bool = False
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)

    @classmethod
    def from_source(cls, source: CaptureSourceConfig) -> CaptureSourceKey:
        match source:
            case CameraCaptureSourceConfig():
                return cls(
                    source_type="camera",
                    identifier=source.device_name.strip(),
                    backend="camera",
                    fps=source.fps,
                    transform=source.transform,
                )
            case WindowCaptureSourceConfig():
                identifier = source.identifier
                return cls(
                    source_type="window",
                    identifier=str(
                        identifier if identifier not in (None, "") else source.title_pattern
                    ),
                    backend=source.backend,
                    fps=source.fps,
                    match_mode=source.match_mode,
                    transform=source.transform,
                )
            case PonkanCaptureSourceConfig():
                return cls(
                    source_type="capture",
                    identifier=f"{source.provider}:{source.device_profile}",
                    backend=source.ponkan_backend,
                    fps=0.0,
                    provider=source.provider,
                    device_profile=source.device_profile,
                    raw_slots=source.raw_slots,
                    output_queue_size=source.output_queue_size,
                    drop_policy=source.drop_policy,
                    poll_interval=source.poll_interval,
                    read_timeout=source.read_timeout,
                    collect_timing=source.collect_timing,
                    transform=source.transform,
                )


def capture_source_from_settings(
    settings: Mapping[str, object],
    *,
    capture_name_override: str | None = None,
) -> CaptureSourceConfig:
    """設定値からキャプチャ入力元の設定を構築します。"""
    if capture_name_override is not None:
        return CameraCaptureSourceConfig(
            device_name=_text(capture_name_override),
            fps=_fps(settings.get("capture_fps"), 60.0),
            transform=_transform(settings),
        )

    source_type = _text(settings.get("capture_source_type", "camera")) or "camera"
    match source_type:
        case "camera":
            return CameraCaptureSourceConfig(
                device_name=_text(settings.get("capture_device", "")),
                fps=_fps(settings.get("capture_fps"), 60.0),
                transform=_transform(settings),
            )
        case "window":
            title = _text(settings.get("capture_window_title", ""))
            identifier = _optional_text(settings.get("capture_window_identifier", ""))
            return WindowCaptureSourceConfig(
                title_pattern=title,
                match_mode=_match_mode(settings.get("capture_window_match_mode", "exact")),
                identifier=identifier,
                backend=_backend(settings.get("capture_backend", "auto")),
                fps=_fps(settings.get("capture_fps"), 30.0),
                transform=_transform(settings),
            )
        case "capture":
            return _ponkan_source(settings)
        case _:
            raise ConfigurationError(
                "invalid capture source type",
                code="NYX_CAPTURE_SOURCE_INVALID",
                component="CaptureSourceConfig",
                details={"capture_source_type": source_type},
            )


def _transform(settings: Mapping[str, object]) -> FrameTransformConfig:
    return FrameTransformConfig(
        aspect_box_enabled=bool(settings.get("capture_aspect_box_enabled", False))
    )


def _ponkan_transform(settings: Mapping[str, object], *, profile: str) -> FrameTransformConfig:
    if profile != "n3dsxl":
        return FrameTransformConfig()
    return FrameTransformConfig(
        aspect_box_enabled=bool(_setting(settings, "n3dsxl_hd_aspect_box_enabled", True))
    )


def _ponkan_source(settings: Mapping[str, object]) -> PonkanCaptureSourceConfig:
    provider = _text(_setting(settings, "capture_provider", "ponkan")) or "ponkan"
    if provider != "ponkan":
        raise ConfigurationError(
            "invalid capture provider",
            code="NYX_CAPTURE_PROVIDER_INVALID",
            component="CaptureSourceConfig",
            details={"capture_provider": provider},
        )
    profile = _text(_setting(settings, "capture_device_profile", "n3dsxl")) or "n3dsxl"
    return PonkanCaptureSourceConfig(
        device_profile=profile,
        ponkan_backend=_ponkan_backend(_setting(settings, "ponkan_backend", "auto")),
        raw_slots=_positive_int(_setting(settings, "ponkan_raw_slots", 2), "ponkan_raw_slots"),
        output_queue_size=_positive_int(
            _setting(settings, "ponkan_output_queue_size", 2),
            "ponkan_output_queue_size",
        ),
        drop_policy=_ponkan_drop_policy(_setting(settings, "ponkan_drop_policy", "drop_oldest")),
        poll_interval=_positive_float(
            _setting(settings, "ponkan_poll_interval", 0.004),
            "ponkan_poll_interval",
        ),
        read_timeout=_read_timeout(_setting(settings, "ponkan_read_timeout", 1.0)),
        collect_timing=bool(_setting(settings, "ponkan_collect_timing", False)),
        transform=_ponkan_transform(settings, profile=profile),
    )


def _setting(settings: Mapping[str, object], key: str, default: object) -> object:
    return settings[key] if key in settings else default


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _fps(value: object, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        fps = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            "capture_fps must be numeric",
            code="NYX_CAPTURE_FPS_INVALID",
            component="CaptureSourceConfig",
        ) from exc
    if fps <= 0:
        raise ConfigurationError(
            "capture_fps must be positive",
            code="NYX_CAPTURE_FPS_INVALID",
            component="CaptureSourceConfig",
            details={"capture_fps": fps},
        )
    return fps


def _match_mode(value: object) -> WindowMatchMode:
    text = _text(value) or "exact"
    if text == "exact":
        return "exact"
    if text == "contains":
        return "contains"
    raise ConfigurationError(
        "invalid capture window match mode",
        code="NYX_CAPTURE_WINDOW_MATCH_MODE_INVALID",
        component="CaptureSourceConfig",
        details={"capture_window_match_mode": text},
    )


def _backend(value: object) -> CaptureBackendName:
    text = _text(value) or "auto"
    if text == "auto":
        return "auto"
    if text == "mss":
        return "mss"
    if text == "windows_graphics_capture":
        return "windows_graphics_capture"
    raise ConfigurationError(
        "invalid capture backend",
        code="NYX_CAPTURE_BACKEND_INVALID",
        component="CaptureSourceConfig",
        details={"capture_backend": text},
    )


def _ponkan_backend(value: object) -> PonkanBackendName:
    text = _text(value) or "auto"
    if text == "auto":
        return "auto"
    if text == "d3xx":
        return "d3xx"
    if text == "d3xx-native":
        return "d3xx-native"
    raise ConfigurationError(
        "invalid ponkan capture backend",
        code="NYX_PONKAN_CAPTURE_BACKEND_INVALID",
        component="CaptureSourceConfig",
        details={"ponkan_backend": text},
    )


def _ponkan_drop_policy(value: object) -> PonkanDropPolicy:
    text = _text(value) or "drop_oldest"
    if text == "drop_oldest":
        return "drop_oldest"
    if text == "drop_newest":
        return "drop_newest"
    if text == "block":
        return "block"
    raise ConfigurationError(
        "invalid ponkan drop policy",
        code="NYX_PONKAN_DROP_POLICY_INVALID",
        component="CaptureSourceConfig",
        details={"ponkan_drop_policy": text},
    )


def _positive_int(value: object, key: str) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"{key} must be an integer",
            code="NYX_PONKAN_CAPTURE_NUMERIC_INVALID",
            component="CaptureSourceConfig",
            details={key: str(value)},
        ) from exc
    if parsed <= 0:
        raise ConfigurationError(
            f"{key} must be positive",
            code="NYX_PONKAN_CAPTURE_NUMERIC_INVALID",
            component="CaptureSourceConfig",
            details={key: parsed},
        )
    return parsed


def _positive_float(value: object, key: str) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"{key} must be numeric",
            code="NYX_PONKAN_CAPTURE_NUMERIC_INVALID",
            component="CaptureSourceConfig",
            details={key: str(value)},
        ) from exc
    if parsed <= 0:
        raise ConfigurationError(
            f"{key} must be positive",
            code="NYX_PONKAN_CAPTURE_NUMERIC_INVALID",
            component="CaptureSourceConfig",
            details={key: parsed},
        )
    return parsed


def _read_timeout(value: object) -> float | None:
    if value is None:
        return None
    if value == "":
        return 1.0
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            "ponkan_read_timeout must be numeric or null",
            code="NYX_PONKAN_CAPTURE_NUMERIC_INVALID",
            component="CaptureSourceConfig",
            details={"ponkan_read_timeout": str(value)},
        ) from exc
    if parsed < 0:
        raise ConfigurationError(
            "ponkan_read_timeout must be greater than or equal to 0",
            code="NYX_PONKAN_CAPTURE_NUMERIC_INVALID",
            component="CaptureSourceConfig",
            details={"ponkan_read_timeout": parsed},
        )
    return parsed
