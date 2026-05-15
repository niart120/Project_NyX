from __future__ import annotations

import math

from PySide6.QtCore import QPointF

from nyxpy.framework.core.constants import Hat
from nyxpy.framework.core.logger import NullLoggerPort
from nyxpy.gui.layout import WINDOW_SIZE_PRESETS, virtual_controller_metrics_for_key
from nyxpy.gui.panes.virtual_controller_pane import VirtualControllerPane
from nyxpy.gui.widgets.controller.analog_stick import AnalogStick
from nyxpy.gui.widgets.controller.dpad import DPad

_CHILD_NAMES = (
    "btn_zl",
    "btn_l",
    "btn_r",
    "btn_zr",
    "btn_minus",
    "btn_capture",
    "btn_home",
    "btn_plus",
    "btn_x",
    "btn_y",
    "btn_a",
    "btn_b",
    "left_stick",
    "btn_ls",
    "dpad",
    "right_stick",
    "btn_rs",
)


def test_virtual_controller_preset_sizes_keep_children_inside_canvas(qtbot) -> None:
    pane = VirtualControllerPane(NullLoggerPort())
    qtbot.addWidget(pane)

    for preset in WINDOW_SIZE_PRESETS:
        metrics = virtual_controller_metrics_for_key(preset.key)
        pane.apply_layout_size(metrics.width, metrics.height)

        assert pane.minimumSize().width() == metrics.width
        assert pane.minimumSize().height() == metrics.height
        for name in _CHILD_NAMES:
            rect = getattr(pane, name).geometry()
            assert rect.left() >= 0, name
            assert rect.top() >= 0, name
            assert rect.right() < metrics.width, name
            assert rect.bottom() < metrics.height, name


def test_virtual_controller_button_sizes_scale_by_preset(qtbot) -> None:
    pane = VirtualControllerPane(NullLoggerPort())
    qtbot.addWidget(pane)

    pane.apply_layout_size(260, 220)
    hd_button_size = pane.btn_a.size()
    hd_style = pane.btn_a.styleSheet()

    pane.apply_layout_size(420, 360)
    four_k_button_size = pane.btn_a.size()
    four_k_style = pane.btn_a.styleSheet()

    assert hd_button_size.width() < four_k_button_size.width()
    assert hd_button_size.height() < four_k_button_size.height()
    assert "font-size: 8px" in hd_style
    assert "font-size: 14px" in four_k_style


def test_virtual_controller_layout_does_not_stretch_rows_vertically(qtbot) -> None:
    pane = VirtualControllerPane(NullLoggerPort())
    qtbot.addWidget(pane)

    pane.apply_layout_size(280, 280)

    assert pane.btn_zl.y() < pane.btn_minus.y()
    assert pane.btn_minus.y() < pane.btn_x.y()
    assert pane.btn_x.y() < pane.btn_b.y()
    assert pane.btn_b.y() < pane.btn_rs.y()
    assert pane.btn_rs.geometry().bottom() < pane.height()


def test_virtual_controller_layout_is_idempotent_across_preset_switches(qtbot) -> None:
    pane = VirtualControllerPane(NullLoggerPort())
    qtbot.addWidget(pane)

    pane.apply_layout_size(260, 220)
    hd_rects = {name: getattr(pane, name).geometry() for name in _CHILD_NAMES}

    pane.apply_layout_size(420, 360)
    pane.apply_layout_size(260, 220)

    assert {name: getattr(pane, name).geometry() for name in _CHILD_NAMES} == hd_rects


def test_analog_stick_uses_scaled_center_after_resize(qtbot) -> None:
    stick = AnalogStick()
    qtbot.addWidget(stick)
    events: list[tuple[float, float]] = []
    stick.valueChanged.connect(lambda angle, strength: events.append((angle, strength)))
    stick.set_diameter(96)

    stick.updateStickPosition(QPointF(48, 48))
    stick.updateStickPosition(QPointF(96, 48))

    assert events[0] == (0.0, 0.0)
    assert math.isclose(events[1][1], 1.0)


def test_dpad_uses_scaled_hit_test_after_resize(qtbot) -> None:
    dpad = DPad()
    qtbot.addWidget(dpad)
    events: list[Hat] = []
    dpad.directionChanged.connect(events.append)
    dpad.set_diameter(108)

    dpad.updateDirection(QPointF(54, 54))
    dpad.updateDirection(QPointF(107, 54))

    assert events == [Hat.RIGHT]
