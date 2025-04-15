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
    return SerialComm(port="DUMMY")

@pytest.fixture
def serial_manager():
    """SerialManager のインスタンスを返す"""
    return SerialManager()

# SerialComm のテスト
def test_serial_comm_open(serial_comm, mock_serial):
    """SerialComm.open() の正常系テスト"""
    serial_comm.open(9600)
    mock_serial.assert_called_once_with("DUMMY", 9600, timeout=1)
    assert serial_comm.ser is not None

def test_serial_comm_send(serial_comm, mock_serial):
    """SerialComm.send() の正常系テスト"""
    serial_comm.open(9600)
    serial_comm.send(b"test_data")
    serial_comm.ser.write.assert_called_once_with(b"test_data")

def test_serial_comm_close(serial_comm, mock_serial):
    """SerialComm.close() の正常系テスト"""
    serial_comm.open(9600)
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
    serial_manager.set_active("test_device", 9600)
    mock_device.open.assert_called_once_with(9600)
    assert serial_manager.active_device == mock_device

def test_serial_manager_send(serial_manager):
    """SerialManager.send() の正常系テスト"""
    mock_device = MagicMock()
    serial_manager.register_device("test_device", mock_device)
    serial_manager.set_active("test_device", 9600)
    serial_manager.get_active_device().send(b"test_data")
    mock_device.send.assert_called_once_with(b"test_data")

def test_serial_manager_close_active(serial_manager):
    """SerialManager.close_active() の正常系テスト"""
    mock_device = MagicMock()
    serial_manager.register_device("test_device", mock_device)
    serial_manager.set_active("test_device", 9600)
    serial_manager.close_active()
    mock_device.close.assert_called_once()
    assert serial_manager.active_device is None

def test_serial_manager_set_active_unregistered_device(serial_manager):
    """SerialManager.set_active() の異常系テスト: 未登録デバイス"""
    with pytest.raises(ValueError, match="'unknown_device'"):
        serial_manager.set_active("unknown_device", 9600)

def test_serial_manager_send_without_active_device(serial_manager):
    """SerialManager.send() の異常系テスト: アクティブデバイスなし"""
    with pytest.raises(RuntimeError, match="SerialManager: No active serial device."):
        serial_manager.get_active_device()

def test_serial_manager_close_without_active_device(serial_manager):
    """SerialManager.close_active() の異常系テスト: アクティブデバイスなし"""
    # アクティブデバイスがない状態でクローズしても例外は発生しないことを確認
    serial_manager.close_active()
    assert serial_manager.active_device is None

def test_serial_manager_register_duplicate_device(serial_manager):
    """SerialManager の重複デバイス登録テスト"""
    mock_device1 = MagicMock()
    mock_device2 = MagicMock()
    serial_manager.register_device("test_device", mock_device1)
    serial_manager.register_device("test_device", mock_device2)
    # 後から登録したデバイスで上書きされることを確認
    serial_manager.set_active("test_device", 9600)
    mock_device2.open.assert_called_once_with(9600)
    assert serial_manager.active_device == mock_device2

def test_serial_manager_get_device_names(serial_manager):
    """SerialManager.get_device_names() のテスト"""
    mock_device1 = MagicMock()
    mock_device2 = MagicMock()
    serial_manager.register_device("device1", mock_device1)
    serial_manager.register_device("device2", mock_device2)
    device_names = serial_manager.list_devices()
    assert "device1" in device_names
    assert "device2" in device_names
    assert len(device_names) == 2
