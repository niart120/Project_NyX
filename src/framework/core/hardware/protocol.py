import struct

class SerialProtocol:
    """
    SerialProtocol は、高レベルの操作を通信プロトコルに従ったコマンドデータに変換します。
    ヘッダー、フッター、チェックサムなどのフォーマットは仕様に基づいて実装します。
    """
    def __init__(self):
        self.header = b'\xAA'  # 例: ヘッダー
        self.footer = b'\x55'  # 例: フッター

    def build_press_command(self, keys: tuple) -> bytes:
        """
        press コマンド用のデータを生成します。
        """
        payload = b'PRESS'
        for key in keys:
            # 例として各キーを2バイト表現 (key.value) する
            payload += key.to_bytes(2, byteorder='big')
        checksum = bytes([sum(payload) % 256])
        return self.header + payload + checksum + self.footer

    def build_release_command(self, keys: tuple) -> bytes:
        """
        release コマンド用のデータを生成します。
        """
        payload = b'RELSE'
        for key in keys:
            payload += key.to_bytes(2, byteorder='big')
        checksum = bytes([sum(payload) % 256])
        return self.header + payload + checksum + self.footer

    def build_keyboard_command(self, text: str) -> bytes:
        payload = b'KEYBD' + text.encode('utf-8')
        checksum = bytes([sum(payload) % 256])
        return self.header + payload + checksum + self.footer

def float_to_bytes(value: float) -> bytes:
    """
    浮動小数点数を4バイトのIEEE754フォーマットに変換するヘルパー関数
    """
    return struct.pack('!f', value)