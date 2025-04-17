import pytest
import tomllib
from pathlib import Path
from PySide6.QtWidgets import QDialog
from nyxpy.gui.settings_dialog import SettingsDialog
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.hardware.serial_comm import SerialManager

@ pytest.fixture(autouse=True)
def dummy_devices(monkeypatch):
    # Mock device managers to return predictable lists
    monkeypatch.setattr(CaptureManager, 'auto_register_devices', lambda self: None)
    monkeypatch.setattr(CaptureManager, 'list_devices', lambda self: ['Cam1', 'Cam2'])
    monkeypatch.setattr(SerialManager, 'auto_register_devices', lambda self: None)
    monkeypatch.setattr(SerialManager, 'list_devices', lambda self: ['COMX', 'COMY'])
    yield

@ pytest.fixture
def tmp_cwd(tmp_path, monkeypatch):
    # Change cwd to temporary path for isolation
    monkeypatch.chdir(tmp_path)
    yield tmp_path

def test_settings_dialog_defaults(tmp_cwd, qtbot):
    # When no existing settings, fields should have default values
    dlg = SettingsDialog(None, macro_name='TestMacro')
    qtbot.addWidget(dlg)
    # Defaults
    assert dlg.param_edit.text() == ''
    assert dlg.cap_device.count() == 2 and dlg.cap_device.currentText() == 'Cam1'
    assert dlg.cap_fps.value() == 30
    assert dlg.ser_device.count() == 2 and dlg.ser_device.currentText() == 'COMX'
    assert dlg.ser_baud.value() == 9600

def test_settings_dialog_load_existing(tmp_cwd, qtbot):
    # Prepare existing settings file
    base = tmp_cwd / 'static' / 'TestMacro'
    base.mkdir(parents=True)
    content = '\n'.join([
        'param_edit = "foo=bar"',
        'cap_device = "Cam2"',
        'cap_fps = 15',
        'ser_device = "COMY"',
        'ser_baud = 19200'
    ])
    (base / 'settings.toml').write_text(content)
    # Now instantiate dialog
    dlg = SettingsDialog(None, macro_name='TestMacro')
    qtbot.addWidget(dlg)
    assert dlg.param_edit.text() == 'foo=bar'
    assert dlg.cap_device.currentText() == 'Cam2'
    assert dlg.cap_fps.value() == 15
    assert dlg.ser_device.currentText() == 'COMY'
    assert dlg.ser_baud.value() == 19200

def test_settings_dialog_persist(tmp_cwd, qtbot):
    # Instantiate, modify fields, accept, then verify file
    dlg = SettingsDialog(None, macro_name='PersistMacro')
    qtbot.addWidget(dlg)
    dlg.param_edit.setText('a=1 b=2')
    dlg.cap_device.setCurrentText('Cam2')
    dlg.cap_fps.setValue(20)
    dlg.ser_device.setCurrentText('COMY')
    dlg.ser_baud.setValue(57600)
    # Accept to persist
    result = dlg.exec()
    # exec() returns QDialog.Accepted by default when clicking save, but we directly called exec() without setting buttons -> test accept directly
    # Instead, call accept
    dlg.accept()
    # Read file
    settings_path = Path.cwd() / 'static' / 'PersistMacro' / 'settings.toml'
    assert settings_path.exists()
    data = tomllib.loads(settings_path.read_text())
    assert data['param_edit'] == 'a=1 b=2'
    assert data['cap_device'] == 'Cam2'
    assert data['cap_fps'] == 20
    assert data['ser_device'] == 'COMY'
    assert data['ser_baud'] == 57600
