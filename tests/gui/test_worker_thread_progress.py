from nyxpy.gui.main_window import WorkerThread


class DummyExecutor2:
    def __init__(self):
        self.macros = {"Macro2": None}

    def select_macro(self, name):
        assert name == "Macro2"

    def execute(self, cmd, args):
        cmd.log("step1")
        cmd.log("step2")


class DummyCmd2:
    def __init__(self):
        pass


def test_worker_thread_progress_signal(qtbot):
    executor = DummyExecutor2()
    cmd = DummyCmd2()
    captured = []
    worker = WorkerThread(executor, cmd, "Macro2", {})
    worker.progress.connect(lambda msg: captured.append(msg))
    # run synchronously
    worker.run()
    assert captured == ["step1", "step2"]
