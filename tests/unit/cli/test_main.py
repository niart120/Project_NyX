from datetime import datetime
from unittest.mock import MagicMock

import pytest

from nyxpy.cli.run_cli import (
    cli_main,
    configure_logging,
    create_protocol,
    create_runtime_builder,
    execute_macro,
)
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol, ThreeDSSerialProtocol
from nyxpy.framework.core.macro.exceptions import ErrorInfo, ErrorKind
from nyxpy.framework.core.runtime.result import RunResult, RunStatus


class MockLogManager:
    def __init__(self):
        self.current_level = None
        self.logs = []

    def set_level(self, level):
        self.current_level = level

    def log(self, level, message, component=""):
        self.logs.append((level, message, component))


class MockSerialManager:
    def __init__(self, devices=None):
        self.devices = devices or {}
        self.active_name = None
        self.active_baudrate = None

    def auto_register_devices(self):
        pass

    def list_devices(self):
        return list(self.devices.keys())

    def set_active(self, name, baudrate=9600):
        if name not in self.devices:
            raise ValueError(f"SerialManager: Device '{name}' not registered.")
        self.active_name = name
        self.active_baudrate = baudrate

    def get_active_device(self):
        return self.devices[self.active_name]

    def close_active(self):
        pass


class MockCaptureManager:
    def __init__(self, devices=None):
        self.devices = devices or {}
        self.active_name = None

    def auto_register_devices(self):
        pass

    def list_devices(self):
        return list(self.devices.keys())

    def set_active(self, name):
        if name not in self.devices:
            raise ValueError(f"CaptureManager: Device '{name}' not registered.")
        self.active_name = name

    def get_active_device(self):
        return self.devices[self.active_name]

    def release_active(self):
        pass


@pytest.fixture
def mock_log_manager():
    return MockLogManager()


@pytest.fixture
def mock_serial_manager():
    return MockSerialManager({"COM1": MagicMock(), "COM2": MagicMock()})


@pytest.fixture
def mock_capture_manager():
    return MockCaptureManager({"Camera1": MagicMock(), "Camera2": MagicMock()})


def result(status: RunStatus, message: str = "") -> RunResult:
    error = (
        ErrorInfo(
            kind=ErrorKind.MACRO,
            code="NYX_MACRO_FAILED",
            message=message,
            component="test",
            exception_type="RuntimeError",
            recoverable=False,
        )
        if message
        else None
    )
    now = datetime.now()
    return RunResult(
        run_id="run-1",
        macro_id="Sample",
        macro_name="Sample",
        status=status,
        started_at=now,
        finished_at=now,
        error=error,
    )


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


def test_create_protocol_valid():
    assert isinstance(create_protocol("CH552"), CH552SerialProtocol)


def test_create_protocol_3ds():
    assert isinstance(create_protocol("3DS"), ThreeDSSerialProtocol)


def test_create_protocol_empty():
    with pytest.raises(ValueError, match="Protocol name cannot be empty"):
        create_protocol("")


def test_create_protocol_unknown():
    with pytest.raises(ValueError, match="Unknown protocol: UNKNOWN"):
        create_protocol("UNKNOWN")


def test_create_runtime_builder_uses_active_devices(monkeypatch, tmp_path):
    mock_resource_io = MagicMock()
    mock_registry = MagicMock()
    registry = MagicMock()
    mock_registry.return_value = registry
    mock_builder = MagicMock()
    monkeypatch.setattr("nyxpy.cli.run_cli.StaticResourceIO", lambda path: mock_resource_io)
    monkeypatch.setattr("nyxpy.cli.run_cli.MacroRegistry", mock_registry)
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.serial_manager",
        MagicMock(get_active_device=lambda: "serial"),
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.capture_manager",
        MagicMock(get_active_device=lambda: "capture"),
    )
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_notification_handler_from_settings",
        lambda settings: "notifier",
    )
    monkeypatch.setattr("nyxpy.cli.run_cli.create_legacy_runtime_builder", mock_builder)

    create_runtime_builder(MagicMock(), resources_dir=tmp_path)

    mock_registry.assert_called_once()
    registry.reload.assert_called_once()
    mock_builder.assert_called_once()


def test_execute_macro_success(monkeypatch, mock_log_manager):
    builder = MagicMock(run=MagicMock(return_value=result(RunStatus.SUCCESS)))
    monkeypatch.setattr("nyxpy.cli.run_cli.log_manager", mock_log_manager)

    run_result = execute_macro(builder, "Sample", {"arg1": "value1"})

    assert run_result.status is RunStatus.SUCCESS
    request = builder.run.call_args.args[0]
    assert request.macro_id == "Sample"
    assert request.exec_args == {"arg1": "value1"}


def test_execute_macro_cancelled(monkeypatch, mock_log_manager):
    builder = MagicMock(run=MagicMock(return_value=result(RunStatus.CANCELLED)))
    monkeypatch.setattr("nyxpy.cli.run_cli.log_manager", mock_log_manager)

    run_result = execute_macro(builder, "Sample", {})

    assert run_result.status is RunStatus.CANCELLED
    assert any(log[0] == "WARNING" for log in mock_log_manager.logs)


def test_execute_macro_failed(monkeypatch, mock_log_manager):
    builder = MagicMock(run=MagicMock(return_value=result(RunStatus.FAILED, "boom")))
    monkeypatch.setattr("nyxpy.cli.run_cli.log_manager", mock_log_manager)

    with pytest.raises(RuntimeError, match="boom"):
        execute_macro(builder, "Sample", {})


def make_args():
    args = MagicMock()
    args.serial = "COM1"
    args.capture = "Camera1"
    args.protocol = "CH552"
    args.baud = None
    args.macro_name = "Sample"
    args.silence = False
    args.verbose = False
    args.define = []
    return args


def test_cli_main_success(monkeypatch, mock_serial_manager, mock_capture_manager):
    args = make_args()
    mock_configure = MagicMock()
    mock_protocol = MagicMock()
    mock_builder = MagicMock()
    mock_execute = MagicMock()

    monkeypatch.setattr("nyxpy.cli.run_cli.serial_manager", mock_serial_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.capture_manager", mock_capture_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.configure_logging", mock_configure)
    monkeypatch.setattr("nyxpy.cli.run_cli.create_protocol", lambda name: mock_protocol)
    monkeypatch.setattr("nyxpy.cli.run_cli.create_runtime_builder", lambda protocol: mock_builder)
    monkeypatch.setattr("nyxpy.cli.run_cli.parse_define_args", lambda args: {})
    monkeypatch.setattr("nyxpy.cli.run_cli.execute_macro", mock_execute)

    assert cli_main(args) == 0
    mock_configure.assert_called_once()
    assert mock_serial_manager.active_baudrate == 9600
    mock_execute.assert_called_once_with(
        runtime_builder=mock_builder, macro_name="Sample", exec_args={}
    )


def test_cli_main_uses_3ds_default_baudrate(monkeypatch, mock_serial_manager, mock_capture_manager):
    args = make_args()
    args.protocol = "3DS"

    monkeypatch.setattr("nyxpy.cli.run_cli.serial_manager", mock_serial_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.capture_manager", mock_capture_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.configure_logging", MagicMock())
    monkeypatch.setattr("nyxpy.cli.run_cli.create_runtime_builder", lambda protocol: MagicMock())
    monkeypatch.setattr("nyxpy.cli.run_cli.parse_define_args", lambda args: {})
    monkeypatch.setattr("nyxpy.cli.run_cli.execute_macro", MagicMock())

    assert cli_main(args) == 0
    assert mock_serial_manager.active_name == "COM1"
    assert mock_serial_manager.active_baudrate == 115200


def test_cli_main_baud_override(monkeypatch, mock_serial_manager, mock_capture_manager):
    args = make_args()
    args.protocol = "3DS"
    args.baud = 9600

    monkeypatch.setattr("nyxpy.cli.run_cli.serial_manager", mock_serial_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.capture_manager", mock_capture_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.configure_logging", MagicMock())
    monkeypatch.setattr("nyxpy.cli.run_cli.create_runtime_builder", lambda protocol: MagicMock())
    monkeypatch.setattr("nyxpy.cli.run_cli.parse_define_args", lambda args: {})
    monkeypatch.setattr("nyxpy.cli.run_cli.execute_macro", MagicMock())

    assert cli_main(args) == 0
    assert mock_serial_manager.active_baudrate == 9600


def test_cli_main_value_error(
    monkeypatch, mock_log_manager, mock_serial_manager, mock_capture_manager
):
    args = make_args()
    args.serial = "COM3"

    monkeypatch.setattr("nyxpy.cli.run_cli.log_manager", mock_log_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.configure_logging", MagicMock())
    monkeypatch.setattr("nyxpy.cli.run_cli.serial_manager", mock_serial_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.capture_manager", mock_capture_manager)

    assert cli_main(args) == 1
    assert any(log[0] == "ERROR" for log in mock_log_manager.logs)


def test_cli_main_exception(
    monkeypatch, mock_log_manager, mock_serial_manager, mock_capture_manager
):
    args = make_args()
    monkeypatch.setattr("nyxpy.cli.run_cli.log_manager", mock_log_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.configure_logging", MagicMock())
    monkeypatch.setattr("nyxpy.cli.run_cli.serial_manager", mock_serial_manager)
    monkeypatch.setattr("nyxpy.cli.run_cli.capture_manager", mock_capture_manager)
    monkeypatch.setattr(
        "nyxpy.cli.run_cli.create_protocol",
        lambda name: (_ for _ in ()).throw(Exception("Unexpected error")),
    )

    assert cli_main(args) == 2
    assert any(
        log[0] == "ERROR" and "Unhandled exception" in log[1] for log in mock_log_manager.logs
    )
