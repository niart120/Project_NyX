import pytest

import nyxpy.__main__ as nyx_main
from nyxpy.gui import run_gui


def test_init_app_creates_resource_io_directories_without_static(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = nyx_main.init_app()

    assert result == 0
    for name in ("macros", "snapshots", "resources", "runs", ".nyxpy"):
        assert (tmp_path / name).exists()
    assert not (tmp_path / "static").exists()


def test_gui_startup_creates_resource_io_directories_without_static(tmp_path, monkeypatch):
    class FakeApplication:
        def __init__(self, _args):
            pass

        def exec(self):
            return 0

    class FakeMainWindow:
        def show(self):
            pass

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_gui, "QApplication", FakeApplication)
    monkeypatch.setattr(run_gui, "MainWindow", FakeMainWindow)

    with pytest.raises(SystemExit) as exc_info:
        run_gui.main()

    assert exc_info.value.code == 0
    for name in ("macros", "snapshots", "resources", "runs"):
        assert (tmp_path / name).exists()
    assert not (tmp_path / "static").exists()
