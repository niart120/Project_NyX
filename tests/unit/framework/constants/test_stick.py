import pytest

from nyxpy.framework.core.constants import LStick, RStick


@pytest.mark.parametrize("stick_cls", [LStick, RStick])
def test_stick_center_uses_protocol_neutral_axis(stick_cls) -> None:
    stick = stick_cls.CENTER

    assert (stick.x, stick.y) == (128, 128)


@pytest.mark.parametrize(
    ("stick", "expected"),
    [
        (LStick.RIGHT, (255, 128)),
        (LStick.UP, (128, 0)),
        (LStick.LEFT, (0, 128)),
        (LStick.DOWN, (128, 255)),
        (RStick.RIGHT, (255, 128)),
        (RStick.UP, (128, 0)),
        (RStick.LEFT, (0, 128)),
        (RStick.DOWN, (128, 255)),
    ],
)
def test_stick_cardinal_presets_keep_perpendicular_axis_neutral(stick, expected) -> None:
    assert (stick.x, stick.y) == expected
