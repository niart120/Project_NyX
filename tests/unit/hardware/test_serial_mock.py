from unittest.mock import patch

import pytest

from nyxpy.framework.core.hardware.serial_comm import (
    DummySerialComm,
    SerialComm,
)


@pytest.fixture
def mock_serial():
    """pyserial.Serial のモックを作成"""
    with patch("serial.Serial") as mock:
        yield mock


@pytest.fixture
def serial_comm(mock_serial):
    """SerialComm のインスタンスを返す"""
    return SerialComm(port="DUMMY")


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


def test_dummy_serial_comm_noops() -> None:
    device = DummySerialComm("dummy")
    assert isinstance(device, DummySerialComm)
    device.open(9600)
    device.send(b"test_data")
    device.close()
