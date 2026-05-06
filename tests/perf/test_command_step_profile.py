import time

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.command import DefaultCommand
from tests.support.fake_execution_context import make_fake_execution_context


def test_press_step_profile(tmp_path):
    cmd = DefaultCommand(context=make_fake_execution_context(tmp_path))
    t0 = time.perf_counter()
    cmd.press(Button.A, dur=0.01, wait=0.01)
    t1 = time.perf_counter()

    print(f"[step profile] total: {(t1 - t0) * 1000:.3f}ms")
