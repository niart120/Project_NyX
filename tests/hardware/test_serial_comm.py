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

@pytest.mark.realdevice
def test_serial_comm_open_and_close():
    """実デバイスに対する open() と close() のテスト"""
    port = "COM255"  # 使用するポート名 (setup fixture uses COM255)
    baudrate = 9600

    # デバイスを構築しオープン
    serial_comm = SerialComm(port=port)
    serial_comm.open(baudrate)
    assert serial_comm.ser.is_open

    # デバイスをクローズ
    serial_comm.close()
    assert serial_comm.ser is None

@pytest.mark.realdevice
def test_serial_comm_send():
    """実デバイスに対する send() のテスト"""
    port = "COM255"  # 使用するポート名 (setup fixture uses COM255)
    baudrate = 9600

    # デバイスを構築しオープン
    serial_comm = SerialComm(port=port)
    serial_comm.open(baudrate)

    # データ送信
    test_data = b"Hello, Serial!"
    serial_comm.send(test_data)

    # デバイスをクローズ
    serial_comm.close()
    assert serial_comm.ser is None
