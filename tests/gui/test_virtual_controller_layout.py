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

    pane.apply_layout_size(304, 220)
    hd_button_size = pane.btn_a.size()
    hd_font = pane.btn_a.font()

    pane.apply_layout_size(280, 280)
    full_hd_font = pane.btn_a.font()

    pane.apply_layout_size(538, 360)
    four_k_button_size = pane.btn_a.size()
    four_k_font = pane.btn_a.font()

    assert hd_button_size.width() < four_k_button_size.width()
    assert hd_button_size.height() < four_k_button_size.height()
    assert "font-size" not in pane.btn_a.styleSheet()
    assert hd_font.pointSize() == 9
    assert full_hd_font.pointSize() == 10
    assert four_k_font.pointSize() == 14
    assert hd_font.bold()


def test_virtual_controller_layout_does_not_stretch_rows_vertically(qtbot) -> None:
    pane = VirtualControllerPane(NullLoggerPort())
    qtbot.addWidget(pane)

    pane.apply_layout_size(280, 280)

    assert pane.btn_zl.y() < pane.btn_minus.y()
    assert pane.btn_minus.y() < pane.left_stick.y()
    assert pane.left_stick.y() < pane.dpad.y()
    assert pane.btn_b.y() < pane.right_stick.y()
    assert pane.right_stick.geometry().bottom() < pane.height()


def test_virtual_controller_uses_two_rows_for_main_controls(qtbot) -> None:
    pane = VirtualControllerPane(NullLoggerPort())
    qtbot.addWidget(pane)

    pane.apply_layout_size(280, 280)

    left_stick_center_y = pane.left_stick.geometry().center().y()
    abxy_center_y = pane.btn_y.geometry().united(pane.btn_a.geometry()).center().y()
    dpad_center_y = pane.dpad.geometry().center().y()
    right_stick_center_y = pane.right_stick.geometry().center().y()

    assert abs(left_stick_center_y - abxy_center_y) <= 16
    assert dpad_center_y == right_stick_center_y
    assert dpad_center_y > left_stick_center_y
    assert pane.btn_y.x() > pane.left_stick.geometry().right()
    assert pane.right_stick.x() > pane.dpad.geometry().right()
    assert pane.width() - pane.right_stick.geometry().right() >= 40


def test_virtual_controller_places_l3_r3_on_trigger_row(qtbot) -> None:
    pane = VirtualControllerPane(NullLoggerPort())
    qtbot.addWidget(pane)

    pane.apply_layout_size(280, 280)

    trigger_row = [
        pane.btn_zl,
        pane.btn_l,
        pane.btn_ls,
        pane.btn_rs,
        pane.btn_r,
        pane.btn_zr,
    ]

    assert [button.text() for button in trigger_row] == ["ZL", "L", "L3", "R3", "R", "ZR"]
    assert [button.x() for button in trigger_row] == sorted(button.x() for button in trigger_row)
    assert (
        max(button.y() for button in trigger_row) - min(button.y() for button in trigger_row) <= 1
    )


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
