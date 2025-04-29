import pytest
from nyxpy.gui.main_window import WorkerThread


class DummyExecutor:
    def __init__(self, should_fail=False):
        self.macros = {"Macro": None}
        self.should_fail = should_fail

    def set_active_macro(self, name):
        self.selected_macro = name

    def execute(self, cmd, args):
        if self.should_fail:
            raise RuntimeError("fail")
        # simulate normal execution
        return


class DummyCmd:
    def __init__(self):
        pass


@pytest.mark.parametrize(
    "should_fail, expected",
    [
        (False, "完了"),
        (True, "エラー: fail"),
    ],
)
def test_worker_thread_finish_signal(qtbot, should_fail, expected):
    executor = DummyExecutor(should_fail)
    cmd = DummyCmd()
    # connect to capture finished signal
    captured = []
    worker = WorkerThread(executor, cmd, "Macro", {})
    worker.finished.connect(lambda status: captured.append(status))
    # run synchronously
    worker.run()
    assert captured and captured[0] == expected
