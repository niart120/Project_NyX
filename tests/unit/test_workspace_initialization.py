import pytest

import nyxpy.__main__ as nyx_main
from nyxpy.gui import run_gui


def test_init_app_creates_resource_io_directories_without_static(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = nyx_main.init_app()

    assert result == 0
    for name in ("macros", "snapshots", "resources", "runs", "logs", ".nyxpy"):
        assert (tmp_path / name).exists()
    assert (tmp_path / ".nyxpy" / "global.toml").exists()
    assert (tmp_path / ".nyxpy" / "secrets.toml").exists()
    assert (tmp_path / "macros" / "sample_macro" / "macro.py").exists()
    assert (tmp_path / "resources" / "sample_macro" / "settings.toml").exists()
    assert not (tmp_path / "static").exists()


def test_init_app_blank_skips_sample_macro(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = nyx_main.init_app(blank=True)

    assert result == 0
    assert (tmp_path / "macros").exists()
    assert not (tmp_path / "macros" / "sample_macro").exists()


def test_nyxpy_docs_prints_urls(capsys):
    result = nyx_main.main(["docs"])

    assert result == 0
    captured = capsys.readouterr()
    assert "User guide: https://niart120.github.io/Project_NyX/user-guide/" in captured.out
    assert "API reference: https://niart120.github.io/Project_NyX/api/framework/" in captured.out


def test_nyxpy_create_generates_macro_in_existing_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    nyx_main.init_app(blank=True)

    result = nyx_main.main(["create", "sample_turbo"])

    assert result == 0
    assert (tmp_path / "macros" / "sample_turbo" / "macro.py").exists()
    assert (tmp_path / "resources" / "sample_turbo" / "settings.toml").exists()


def test_nyxpy_create_requires_workspace(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    result = nyx_main.main(["create", "sample_turbo"])

    assert result == 1
    captured = capsys.readouterr()
    assert "nyxpy init" in captured.out


def test_nyxpy_run_delegates_to_cli_main(monkeypatch):
    captured_args = {}

    def fake_cli_main(args):
        captured_args["args"] = args
        return 0

    monkeypatch.setattr(nyx_main, "cli_main", fake_cli_main)

    result = nyx_main.main(
        [
            "run",
            "sample",
            "--serial",
            "COM3",
            "--capture",
            "Capture Device",
            "--define",
            "count=3",
        ]
    )

    assert result == 0
    assert captured_args["args"].macro_name == "sample"
    assert captured_args["args"].serial == "COM3"
    assert captured_args["args"].capture == "Capture Device"
    assert captured_args["args"].define == ["count=3"]


def test_nyx_cli_alias_delegates_to_run_cli(monkeypatch):
    captured_args = {}

    def fake_cli_main(args):
        captured_args["args"] = args
        return 0

    monkeypatch.setattr(nyx_main, "cli_main", fake_cli_main)

    result = nyx_main.run_alias_main(
        [
            "sample",
            "--serial",
            "COM3",
            "--capture",
            "Capture Device",
        ]
    )

    assert result == 0
    assert captured_args["args"].macro_name == "sample"
    assert captured_args["args"].serial == "COM3"
    assert captured_args["args"].capture == "Capture Device"


def test_gui_startup_creates_resource_io_directories_without_static(tmp_path, monkeypatch):
    class FakeApplication:
        def __init__(self, _args):
            pass

        def exec(self):
            return 0

    captured = {}

    class FakeMainWindow:
        def __init__(self, *, project_root):
            captured["project_root"] = project_root

        def show(self):
            pass

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_gui, "QApplication", FakeApplication)
    monkeypatch.setattr(run_gui, "MainWindow", FakeMainWindow)

    with pytest.raises(SystemExit) as exc_info:
        run_gui.main()

    assert exc_info.value.code == 0
    for name in ("macros", "snapshots", "resources", "runs", "logs", ".nyxpy"):
        assert (tmp_path / name).exists()
    assert captured["project_root"] == tmp_path.resolve()
    assert not (tmp_path / "static").exists()
