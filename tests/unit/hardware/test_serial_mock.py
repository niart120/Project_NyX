import pytest
from unittest.mock import MagicMock, patch
from nyxpy.framework.core.hardware.serial_comm import SerialComm, SerialManager

@pytest.fixture
def mock_serial():
    """pyserial.Serial のモックを作成"""
    with patch("serial.Serial") as mock:
        yield mock

@pytest.fixture
def serial_comm(mock_serial):
    """SerialComm のインスタンスを返す"""
    return SerialComm()

@pytest.fixture
def serial_manager():
    """SerialManager のインスタンスを返す"""
    return SerialManager()

# SerialComm のテスト
def test_serial_comm_open(serial_comm, mock_serial):
    """SerialComm.open() の正常系テスト"""
    serial_comm.open("COM3", 9600)
    mock_serial.assert_called_once_with("COM3", 9600, timeout=1)
    assert serial_comm.ser is not None

def test_serial_comm_send(serial_comm, mock_serial):
    """SerialComm.send() の正常系テスト"""
    serial_comm.open("COM3", 9600)
    serial_comm.send(b"test_data")
    serial_comm.ser.write.assert_called_once_with(b"test_data")

def test_serial_comm_close(serial_comm, mock_serial):
    """SerialComm.close() の正常系テスト"""
    serial_comm.open("COM3", 9600)
    serial_comm.close()
    assert serial_comm.ser is None

def test_serial_comm_send_without_open(serial_comm):
    """SerialComm.send() の異常系テスト: ポート未オープン"""
    with pytest.raises(RuntimeError, match="SerialComm: Serial port not open."):
        serial_comm.send(b"test_data")

# SerialManager のテスト
def test_serial_manager_register_and_set_active(serial_manager):
    """SerialManager のデバイス登録とアクティブ化のテスト"""
    mock_device = MagicMock()
    serial_manager.register_device("test_device", mock_device)
    serial_manager.set_active("test_device", "COM3", 9600)
    mock_device.open.assert_called_once_with("COM3", 9600)
    assert serial_manager.active_device == mock_device

def test_serial_manager_send(serial_manager):
    """SerialManager.send() の正常系テスト"""
    mock_device = MagicMock()
    serial_manager.register_device("test_device", mock_device)
    serial_manager.set_active("test_device", "COM3", 9600)
    serial_manager.send(b"test_data")
    mock_device.send.assert_called_once_with(b"test_data")

def test_serial_manager_close_active(serial_manager):
    """SerialManager.close_active() の正常系テスト"""
    mock_device = MagicMock()
    serial_manager.register_device("test_device", mock_device)
    serial_manager.set_active("test_device", "COM3", 9600)
    serial_manager.close_active()
    mock_device.close.assert_called_once()
    assert serial_manager.active_device is None

def test_serial_manager_set_active_unregistered_device(serial_manager):
    """SerialManager.set_active() の異常系テスト: 未登録デバイス"""
    with pytest.raises(ValueError, match="SerialManager: Device 'unknown_device' not registered."):
        serial_manager.set_active("unknown_device", "COM3", 9600)

def test_serial_manager_send_without_active_device(serial_manager):
    """SerialManager.send() の異常系テスト: アクティブデバイスなし"""
    with pytest.raises(RuntimeError, match="SerialManager: No active serial device."):
        serial_manager.send(b"test_data")
