from nyxpy.gui.main_window import WorkerThread


class DummyExecutor2:
    def __init__(self):
        self.macros = {"Macro2": None}

    def set_active_macro(self, name):
        self.selected_macro = name

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
