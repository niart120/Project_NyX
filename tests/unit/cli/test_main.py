import pytest
import pathlib
import unittest.mock
from unittest.mock import MagicMock

from nyxpy.cli.run_cli import (
    configure_logging,
    create_protocol,
    create_command,
    execute_macro,
    cli_main,
)
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol
from nyxpy.framework.core.macro.exceptions import MacroStopException


# LogManager のモック
class MockLogManager:
    def __init__(self):
        self.current_level = None
        self.logs = []

    def set_level(self, level):
        self.current_level = level

    def log(self, level, message, component=""):
        self.logs.append((level, message, component))


# SerialManager のモック
class MockSerialManager:
    def __init__(self, devices=None):
        self.devices = devices or {}
        self.active_device = None

    def auto_register_devices(self):
        pass

    def list_devices(self):
        return list(self.devices.keys())

    def set_active(self, name, baudrate=9600):
        if name not in self.devices:
            raise ValueError(f"SerialManager: Device '{name}' not registered.")
        self.active_device = self.devices[name]
        return True


# CaptureManager のモック
class MockCaptureManager:
    def __init__(self, devices=None):
        self.devices = devices or {}
        self.active_device = None

    def auto_register_devices(self):
        pass

    def list_devices(self):
        return list(self.devices.keys())

    def set_active(self, name):
        if name not in self.devices:
            raise ValueError(f"CaptureManager: Device '{name}' not registered.")
        self.active_device = self.devices[name]
        return True


# MacroExecutor のモック
class MockMacroExecutor:
    def __init__(self, macros=None):
        self.macros = macros or {}
        self.macro = None
        self.executed = False
        self.exec_args = None

    def set_active_macro(self, name):
        if name in self.macros:
            self.selected_macro = name
            self.macro = self.macros[name]
        else:
            raise ValueError(f"Macro '{name}' not found")

    def execute(self, cmd, exec_args={}):
        self.executed = True
        self.exec_args = exec_args
        if self.macro == "fail":
            raise Exception("Macro execution failed")
        if self.macro == "stop":
            raise MacroStopException("Macro execution stopped")
        return True


# テスト用フィクスチャ
@pytest.fixture
def mock_log_manager():
    return MockLogManager()


@pytest.fixture
def mock_serial_manager():
    return MockSerialManager({"COM1": MagicMock(), "COM2": MagicMock()})


@pytest.fixture
def mock_capture_manager():
    return MockCaptureManager({"Camera1": MagicMock(), "Camera2": MagicMock()})


@pytest.fixture
def mock_executor():
    return MockMacroExecutor(
        {"TestMacro": "success", "FailMacro": "fail", "StopMacro": "stop"}
    )


# configure_logging のテスト
def test_configure_logging_normal(monkeypatch, mock_log_manager):
    monkeypatch.setattr("nyxpy.cli.run_cli.log_manager", mock_log_manager)
    configure_logging()
    assert mock_log_manager.current_level == "INFO"


def test_configure_logging_silent(monkeypatch, mock_log_manager):
    monkeypatch.setattr("nyxpy.cli.run_cli.log_manager", mock_log_manager)
    configure_logging(silence=True)
    assert mock_log_manager.current_level == "ERROR"


def test_configure_logging_verbose(monkeypatch, mock_log_manager):
    monkeypatch.setattr("nyxpy.cli.run_cli.log_manager", mock_log_manager)
    configure_logging(verbose=True)
    assert mock_log_manager.current_level == "DEBUG"


# create_protocol のテスト
def test_create_protocol_valid():
    protocol = create_protocol("CH552")
    assert isinstance(protocol, CH552SerialProtocol)


def test_create_protocol_empty():
    with pytest.raises(ValueError, match="Protocol name cannot be empty"):
        create_protocol("")


def test_create_protocol_unknown():
    with pytest.raises(ValueError, match="Unknown protocol: UNKNOWN"):
        create_protocol("UNKNOWN")


# create_command のテスト
def test_create_command_default_path(monkeypatch):
    mock_protocol = MagicMock()
    mock_resource_io = MagicMock()
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.StaticResourceIO", lambda path: mock_resource_io
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.serial_manager", MagicMock(get_active_device=lambda: "serial"))
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.capture_manager", MagicMock(get_active_device=lambda: "capture"))
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.DefaultCommand",
        lambda serial_device, capture_device, resource_io, protocol, ct, notification_handler: "command",
    )
    result = create_command(mock_protocol)
    assert result == "command"


def test_create_command_custom_path(monkeypatch):
    mock_protocol = MagicMock()
    mock_resource_io = MagicMock()
    custom_path = pathlib.Path("custom/path")
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.StaticResourceIO", lambda path: mock_resource_io
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.serial_manager", MagicMock(get_active_device=lambda: "serial"))
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.capture_manager", MagicMock(get_active_device=lambda: "capture"))
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.DefaultCommand",
        lambda serial_device, capture_device, resource_io, protocol, ct, notification_handler: "command",
    )
    result = create_command(mock_protocol, resources_dir=custom_path)
    assert result == "command"


# execute_macro のテスト
def test_execute_macro_success(mock_executor):
    cmd = MagicMock()
    execute_macro(mock_executor, cmd, "TestMacro", {"arg1": "value1"})

    assert mock_executor.executed
    assert mock_executor.exec_args == {"arg1": "value1"}


def test_execute_macro_not_found(mock_executor):
    cmd = MagicMock()

    with pytest.raises(ValueError, match="Macro 'UnknownMacro' not found"):
        execute_macro(mock_executor, cmd, "UnknownMacro", {})


def test_execute_macro_stop_exception(mock_executor):
    cmd = MagicMock()
    execute_macro(mock_executor, cmd, "StopMacro", {})

    assert mock_executor.executed
    # 実際のコードでは例外オブジェクト自体がログに渡されている
    cmd.log.assert_any_call(
        "Macro execution was interrupted:",
        unittest.mock.ANY,  # MacroStopException オブジェクト
        level="WARNING",
    )


def test_execute_macro_exception(mock_executor):
    cmd = MagicMock()

    with pytest.raises(Exception, match="Macro execution failed"):
        execute_macro(mock_executor, cmd, "FailMacro", {})

    # 実際のコードでは例外オブジェクト自体がログに渡されている
    cmd.log.assert_any_call(
        "An unexpected error occurred during macro execution:",
        unittest.mock.ANY,  # Exception オブジェクト
        level="ERROR",
    )


# cli_main のテスト
def test_cli_main_success(monkeypatch, mock_serial_manager, mock_capture_manager):
    args = MagicMock()
    args.serial = "COM1"
    args.capture = "Camera1"
    args.protocol = "CH552"
    args.macro_name = "TestMacro"
    args.silence = False
    args.verbose = False
    args.define = []

    mock_configure = MagicMock()
    mock_protocol = MagicMock()
    mock_command = MagicMock()
    mock_exec = MagicMock()

    # serial_manager/capture_managerを直接パッチ
    monkeypatch.setattr("nyxpy.cli.run_cli.serial_manager", mock_serial_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.capture_manager", mock_capture_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.configure_logging", mock_configure)
    monkeypatch.setattr("nyxpy.cli.run_cli.create_protocol", lambda name: mock_protocol)
    monkeypatch.setattr("nyxpy.cli.run_cli.create_command", lambda protocol: mock_command)
    monkeypatch.setattr("nyxpy.cli.run_cli.parse_define_args", lambda args: {})
    monkeypatch.setattr("nyxpy.cli.run_cli.MacroExecutor", lambda: mock_exec)
    monkeypatch.setattr("nyxpy.cli.run_cli.execute_macro", MagicMock())

    result = cli_main(args)

    assert result == 0
    mock_configure.assert_called_once()


def test_cli_main_value_error(monkeypatch, mock_log_manager, mock_serial_manager, mock_capture_manager):
    args = MagicMock()
    args.serial = "COM3"  # 存在しないシリアルポート
    args.capture = "Camera1"
    args.protocol = "CH552"

    monkeypatch.setattr("nyxpy.cli.run_cli.log_manager", mock_log_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.configure_logging", MagicMock())
    monkeypatch.setattr("nyxpy.cli.run_cli.serial_manager", mock_serial_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.capture_manager", mock_capture_manager)

    result = cli_main(args)

    assert result == 1
    assert any(log[0] == "ERROR" for log in mock_log_manager.logs)


def test_cli_main_exception(monkeypatch, mock_log_manager, mock_serial_manager, mock_capture_manager):
    args = MagicMock()

    args.serial = "COM1" 
    args.capture = "Camera1"
    args.protocol = "CH552"

    monkeypatch.setattr("nyxpy.cli.run_cli.log_manager", mock_log_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.configure_logging", MagicMock())
    monkeypatch.setattr("nyxpy.cli.run_cli.serial_manager", mock_serial_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.capture_manager", mock_capture_manager)
    # create_protocolで例外を発生させる
    monkeypatch.setattr("nyxpy.cli.run_cli.create_protocol", lambda name: (_ for _ in ()).throw(Exception("Unexpected error")))

    result = cli_main(args)

    assert result == 2
    assert any(
        log[0] == "ERROR" and "Unhandled exception" in log[1]
        for log in mock_log_manager.logs
    )
