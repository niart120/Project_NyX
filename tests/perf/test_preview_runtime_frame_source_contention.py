import statistics
import time

import numpy as np

from nyxpy.framework.core.io.adapters import CaptureFrameSourcePort


class StaticCaptureDevice:
    def __init__(self, frame) -> None:
        self.frame = frame

    def get_frame(self):
        return self.frame


def _p95(values: list[float]) -> float:
    return statistics.quantiles(values, n=20)[18]


def test_frame_source_latest_frame_copy_perf() -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    source = CaptureFrameSourcePort(StaticCaptureDevice(frame))
    samples: list[float] = []

    for _ in range(30):
        started = time.perf_counter()
        source.latest_frame()
        samples.append(time.perf_counter() - started)

    assert _p95(samples) < 0.01


def test_preview_runtime_frame_source_contention_perf() -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    source = CaptureFrameSourcePort(StaticCaptureDevice(frame))
    baseline: list[float] = []
    contended: list[float] = []
    preview_ticks: list[float] = []

    for _ in range(30):
        started = time.perf_counter()
        source.latest_frame()
        baseline.append(time.perf_counter() - started)

    for _ in range(30):
        preview_started = time.perf_counter()
        source.try_latest_frame()
        preview_ticks.append(time.perf_counter() - preview_started)

        capture_started = time.perf_counter()
        source.latest_frame()
        contended.append(time.perf_counter() - capture_started)

    assert sum(tick >= 0.016 for tick in preview_ticks) / len(preview_ticks) < 0.01
    assert _p95(contended) < max(_p95(baseline) * 2, 0.01)
