import pytest
from PySide6.QtWidgets import QPushButton
from nyxpy.gui.dialogs.macro_params_dialog import SettingsDialog
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.hardware.serial_comm import SerialManager


@pytest.fixture(autouse=True)
def dummy_devices(monkeypatch):
    # Mock device managers to return predictable lists
    monkeypatch.setattr(CaptureManager, "auto_register_devices", lambda self: None)
    monkeypatch.setattr(CaptureManager, "list_devices", lambda self: ["Cam1", "Cam2"])
    monkeypatch.setattr(SerialManager, "auto_register_devices", lambda self: None)
    monkeypatch.setattr(SerialManager, "list_devices", lambda self: ["COMX", "COMY"])
    yield


@pytest.fixture
def tmp_cwd(tmp_path, monkeypatch):
    # Change cwd to temporary path for isolation
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def test_settings_dialog_defaults(tmp_cwd, qtbot):
    # When no existing settings, fields should have default values
    dlg = SettingsDialog(None)
    qtbot.addWidget(dlg)
    # Defaults
    assert dlg.param_edit.text() == ""
    # Confirm run button exists
    run_btn = dlg.findChild(QPushButton)
    assert run_btn and run_btn.text() == "実行"
