import pytest
from nyxpy.framework.core.hardware.serial_comm import SerialComm
from serial import Serial

@pytest.fixture(autouse=True)
def setup_and_teardown():
    """テストのセットアップとクリーンアップ"""
    # テスト前のセットアップ
    recv_device = Serial("COM255", 9600, timeout=1)  # 受信用の実際のデバイスに接続
    assert recv_device.is_open, "Failed to open the serial port."

    yield
    # テスト後のクリーンアップ
    recv_device.close()
    assert not recv_device.is_open, "Failed to close the serial port."

@pytest.fixture
def serial_comm():
    """SerialComm のインスタンスを返す"""
    return SerialComm()

@pytest.mark.realdevice
def test_serial_comm_open_and_close(serial_comm):
    """実デバイスに対する open() と close() のテスト"""
    port = "COM127"  # 実際のデバイスのポート名に変更してください
    baudrate = 9600

    # デバイスをオープン
    serial_comm.open(port, baudrate)
    assert serial_comm.ser.is_open

    # デバイスをクローズ
    serial_comm.close()
    assert serial_comm.ser is None

@pytest.mark.realdevice
def test_serial_comm_send(serial_comm):
    """実デバイスに対する send() のテスト"""
    port = "COM127"  # 実際のデバイスのポート名に変更してください
    baudrate = 9600

    # デバイスをオープン
    serial_comm.open(port, baudrate)

    # データ送信
    test_data = b"Hello, Serial!"
    serial_comm.send(test_data)

    # デバイスをクローズ
    serial_comm.close()
    assert serial_comm.ser is None
