import numpy as np
import pytest

from nyxpy.framework.core.hardware.frame_transform import FrameTransformConfig, FrameTransformer


def test_frame_transform_keeps_raw_when_disabled() -> None:
    frame = np.ones((720, 600, 3), dtype=np.uint8)

    transformed = FrameTransformer().transform(frame, FrameTransformConfig())

    assert transformed is frame


def test_frame_transform_keeps_16x9_input() -> None:
    frame = np.ones((720, 1280, 3), dtype=np.uint8)

    transformed = FrameTransformer().transform(
        frame,
        FrameTransformConfig(aspect_box_enabled=True),
    )

    assert transformed is frame


def test_frame_transform_adds_pillarbox_to_600x720() -> None:
    frame = np.full((720, 600, 3), 255, dtype=np.uint8)

    transformed = FrameTransformer().transform(
        frame,
        FrameTransformConfig(aspect_box_enabled=True),
    )

    assert transformed.shape == (720, 1280, 3)
    assert np.all(transformed[:, :340] == 0)
    assert np.all(transformed[:, 340:940] == 255)
    assert np.all(transformed[:, 940:] == 0)


def test_frame_transform_adds_letterbox_to_wide_input() -> None:
    frame = np.full((600, 1280, 3), 255, dtype=np.uint8)

    transformed = FrameTransformer().transform(
        frame,
        FrameTransformConfig(aspect_box_enabled=True),
    )

    assert transformed.shape == (720, 1280, 3)
    assert np.all(transformed[:60, :] == 0)
    assert np.all(transformed[60:660, :] == 255)
    assert np.all(transformed[660:, :] == 0)


def test_frame_transform_rejects_invalid_background() -> None:
    with pytest.raises(ValueError):
        FrameTransformConfig(background_bgr=(0, 0, 256))
