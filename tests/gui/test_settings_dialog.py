import pytest
from PySide6.QtWidgets import QPushButton

from nyxpy.gui.dialogs.macro_params_dialog import MacroParamsDialog


@pytest.fixture
def tmp_cwd(tmp_path, monkeypatch):
    # Change cwd to temporary path for isolation
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def test_settings_dialog_defaults(tmp_cwd, qtbot):
    # When no existing settings, fields should have default values
    dlg = MacroParamsDialog(None)
    qtbot.addWidget(dlg)
    # Defaults
    assert dlg.param_edit.text() == ""
    # Confirm run button exists
    run_btn = dlg.findChild(QPushButton)
    assert run_btn and run_btn.text() == "実行"
