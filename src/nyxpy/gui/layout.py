from dataclasses import dataclass


DEFAULT_WINDOW_SIZE_PRESET_KEY = "full_hd"


@dataclass(frozen=True)
class WindowSizePreset:
    key: str
    label: str
    window_width: int
    window_height: int
    preview_width: int
    preview_height: int

    @property
    def window_size(self) -> tuple[int, int]:
        return self.window_width, self.window_height

    @property
    def preview_size(self) -> tuple[int, int]:
        return self.preview_width, self.preview_height


@dataclass(frozen=True)
class LayoutMetrics:
    margin: int
    gap: int
    left_width: int
    controller_height: int
    macro_log_width: int
    preview_tool_log_height: int
    preview_width: int
    preview_height: int
    macro_explorer_min_height: int
    macro_log_min_width: int
    macro_log_min_height: int
    preview_tool_log_min_height: int

    @property
    def preview_size(self) -> tuple[int, int]:
        return self.preview_width, self.preview_height

    @property
    def center_height(self) -> int:
        return self.preview_height + self.gap + self.preview_tool_log_height

    @property
    def macro_explorer_height(self) -> int:
        return self.center_height - self.gap - self.controller_height

    def horizontal_surplus(self, preset: WindowSizePreset) -> int:
        return preset.window_width - (
            self.margin * 2
            + self.left_width
            + self.preview_width
            + self.macro_log_width
            + self.gap * 2
        )


WINDOW_SIZE_PRESETS: tuple[WindowSizePreset, ...] = (
    WindowSizePreset("hd", "HD", 1280, 720, 640, 360),
    WindowSizePreset("full_hd", "FullHD", 1920, 1080, 1280, 720),
    WindowSizePreset("wqhd", "WQHD", 2560, 1440, 1600, 900),
    WindowSizePreset("four_k", "4K", 3840, 2160, 2560, 1440),
)

WINDOW_SIZE_PRESETS_BY_KEY = {preset.key: preset for preset in WINDOW_SIZE_PRESETS}

LAYOUT_METRICS_BY_PRESET: dict[str, LayoutMetrics] = {
    "hd": LayoutMetrics(
        margin=8,
        gap=8,
        left_width=260,
        controller_height=220,
        macro_log_width=260,
        preview_tool_log_height=120,
        preview_width=640,
        preview_height=360,
        macro_explorer_min_height=320,
        macro_log_min_width=240,
        macro_log_min_height=180,
        preview_tool_log_min_height=96,
    ),
    "full_hd": LayoutMetrics(
        margin=10,
        gap=10,
        left_width=280,
        controller_height=280,
        macro_log_width=320,
        preview_tool_log_height=180,
        preview_width=1280,
        preview_height=720,
        macro_explorer_min_height=420,
        macro_log_min_width=300,
        macro_log_min_height=280,
        preview_tool_log_min_height=140,
    ),
    "wqhd": LayoutMetrics(
        margin=12,
        gap=12,
        left_width=360,
        controller_height=320,
        macro_log_width=440,
        preview_tool_log_height=240,
        preview_width=1600,
        preview_height=900,
        macro_explorer_min_height=520,
        macro_log_min_width=380,
        macro_log_min_height=360,
        preview_tool_log_min_height=180,
    ),
    "four_k": LayoutMetrics(
        margin=16,
        gap=16,
        left_width=420,
        controller_height=360,
        macro_log_width=560,
        preview_tool_log_height=320,
        preview_width=2560,
        preview_height=1440,
        macro_explorer_min_height=640,
        macro_log_min_width=480,
        macro_log_min_height=480,
        preview_tool_log_min_height=240,
    ),
}


def normalize_window_size_preset_key(value: object) -> str:
    key = str(value) if value is not None else ""
    if key in WINDOW_SIZE_PRESETS_BY_KEY:
        return key
    return DEFAULT_WINDOW_SIZE_PRESET_KEY


def window_size_preset_for_key(value: object) -> WindowSizePreset:
    return WINDOW_SIZE_PRESETS_BY_KEY[normalize_window_size_preset_key(value)]


def layout_metrics_for_key(value: object) -> LayoutMetrics:
    return LAYOUT_METRICS_BY_PRESET[normalize_window_size_preset_key(value)]
