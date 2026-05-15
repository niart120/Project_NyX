from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from nyxpy.framework.core.hardware.frame_transform import FrameTransformConfig
from nyxpy.framework.core.macro.exceptions import ConfigurationError

CaptureSourceType = Literal["camera", "window", "screen_region"]
WindowMatchMode = Literal["exact", "contains"]
CaptureBackendName = Literal["auto", "mss", "windows_graphics_capture"]


@dataclass(frozen=True)
class CaptureRect:
    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
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
    device_name: str = ""
    source_type: Literal["camera"] = "camera"
    fps: float = 60.0
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)


@dataclass(frozen=True)
class WindowCaptureSourceConfig:
    title_pattern: str = ""
    source_type: Literal["window"] = "window"
    match_mode: WindowMatchMode = "exact"
    identifier: str | int | None = None
    backend: CaptureBackendName = "auto"
    fps: float = 30.0
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)


@dataclass(frozen=True)
class ScreenRegionCaptureSourceConfig:
    region: CaptureRect
    source_type: Literal["screen_region"] = "screen_region"
    fps: float = 60.0
    transform: FrameTransformConfig = field(default_factory=FrameTransformConfig)
    backend: CaptureBackendName = "auto"


CaptureSourceConfig = (
    CameraCaptureSourceConfig | WindowCaptureSourceConfig | ScreenRegionCaptureSourceConfig
)


@dataclass(frozen=True)
class CaptureSourceKey:
    source_type: CaptureSourceType
    identifier: str
    backend: str
    fps: float
    region: CaptureRect | None = None
    match_mode: str = ""
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
            case ScreenRegionCaptureSourceConfig():
                return cls(
                    source_type="screen_region",
                    identifier="screen_region",
                    backend=source.backend,
                    fps=source.fps,
                    region=source.region,
                    transform=source.transform,
                )


def capture_source_from_settings(
    settings: Mapping[str, object],
    *,
    capture_name_override: str | None = None,
) -> CaptureSourceConfig:
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
        case "screen_region":
            return ScreenRegionCaptureSourceConfig(
                region=_region(settings.get("capture_region", {})),
                backend=_backend(settings.get("capture_backend", "auto")),
                fps=_fps(settings.get("capture_fps"), 60.0),
                transform=_transform(settings),
            )
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


def _region(value: object) -> CaptureRect:
    if not isinstance(value, Mapping):
        raise _region_error("capture_region must be a mapping")
    missing = {"left", "top", "width", "height"} - set(value)
    if missing:
        raise _region_error("capture_region is missing required keys", missing=sorted(missing))
    try:
        return CaptureRect(
            left=int(value["left"]),
            top=int(value["top"]),
            width=int(value["width"]),
            height=int(value["height"]),
        )
    except (TypeError, ValueError) as exc:
        raise _region_error("capture_region values must be integers") from exc


def _region_error(message: str, **details: object) -> ConfigurationError:
    return ConfigurationError(
        message,
        code="NYX_CAPTURE_REGION_INVALID",
        component="CaptureSourceConfig",
        details=dict(details),
    )


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
        fps = float(value)
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
    if text not in ("exact", "contains"):
        raise ConfigurationError(
            "invalid capture window match mode",
            code="NYX_CAPTURE_WINDOW_MATCH_MODE_INVALID",
            component="CaptureSourceConfig",
            details={"capture_window_match_mode": text},
        )
    return text


def _backend(value: object) -> CaptureBackendName:
    text = _text(value) or "auto"
    if text not in ("auto", "mss", "windows_graphics_capture"):
        raise ConfigurationError(
            "invalid capture backend",
            code="NYX_CAPTURE_BACKEND_INVALID",
            component="CaptureSourceConfig",
            details={"capture_backend": text},
        )
    return text
