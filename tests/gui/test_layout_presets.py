from nyxpy.gui.layout import (
    DEFAULT_WINDOW_SIZE_PRESET_KEY,
    WINDOW_SIZE_PRESETS,
    layout_metrics_for_key,
    normalize_window_size_preset_key,
    virtual_controller_metrics_for_key,
)


def test_window_size_presets_are_defined() -> None:
    assert [(preset.key, preset.label, preset.window_size) for preset in WINDOW_SIZE_PRESETS] == [
        ("hd", "HD", (1280, 720)),
        ("full_hd", "FullHD", (1920, 1080)),
        ("wqhd", "WQHD", (2560, 1440)),
        ("four_k", "4K", (3840, 2160)),
    ]


def test_unknown_window_size_preset_falls_back_to_fullhd() -> None:
    assert normalize_window_size_preset_key("removed") == DEFAULT_WINDOW_SIZE_PRESET_KEY
    assert layout_metrics_for_key("removed").preview_size == (1280, 720)


def test_preview_sizes_use_standard_16_9_dimensions() -> None:
    assert [preset.preview_size for preset in WINDOW_SIZE_PRESETS] == [
        (640, 360),
        (1280, 720),
        (1600, 900),
        (2560, 1440),
    ]
    for preset in WINDOW_SIZE_PRESETS:
        width, height = preset.preview_size
        assert width * 9 == height * 16


def test_layout_horizontal_surplus_is_side_panel_width() -> None:
    assert {
        preset.key: (
            layout_metrics_for_key(preset.key).allocated_left_width(preset),
            layout_metrics_for_key(preset.key).allocated_tool_log_width(preset),
        )
        for preset in WINDOW_SIZE_PRESETS
    } == {
        "hd": (304, 304),
        "full_hd": (280, 320),
        "wqhd": (416, 496),
        "four_k": (538, 678),
    }


def test_macro_explorer_absorbs_vertical_surplus() -> None:
    full_hd = layout_metrics_for_key("full_hd")
    assert full_hd.center_height == 910
    assert full_hd.macro_explorer_height == 720


def test_virtual_controller_metrics_use_left_column_size() -> None:
    assert [
        (
            preset.key,
            virtual_controller_metrics_for_key(preset.key).width,
            virtual_controller_metrics_for_key(preset.key).height,
        )
        for preset in WINDOW_SIZE_PRESETS
    ] == [
        ("hd", 304, 220),
        ("full_hd", 280, 280),
        ("wqhd", 416, 320),
        ("four_k", 538, 360),
    ]
