from abc import ABC, abstractmethod
from nyxpy.framework.core.macro.constants import Button, Hat, KeyboardOp, LStick, RStick, KeyType

class SerialProtocolInterface(ABC):
    @abstractmethod
    def build_press_command(self, keys: tuple[KeyType, ...]) -> bytes:
        """キー押下操作のコマンドデータを生成する
        
        :param keys: 押下するキーのタプル
        :return: コマンドデータ
        """
        
        
        pass

    @abstractmethod
    def build_release_command(self, keys: tuple[KeyType, ...]) -> bytes:
        """キー解放操作のコマンドデータを生成する
        
        :param keys: 解放するキーのタプル
        :return: コマンドデータ
        """
        pass

    @abstractmethod
    def build_keyboard_command(self, key: str, op: KeyboardOp) -> bytes:
        """
        キーボード入力操作のコマンドデータを生成する

        :param key: キーの文字
        :param op: KeyboardOp キーボード操作の種類
        :return: コマンドデータ
        """
        pass

class CH552SerialProtocol(SerialProtocolInterface):
    """
    CH552SerialProtocol は、CH552 デバイス向けの通信プロトコルを実装します。
    内部状態（key_state）は以下の構成になっています：
      [header, btn1, btn2, hat, lx, ly, rx, ry, kbdheader, key, centinel]
    - header: 固定値 0xAB
    - btn1, btn2: ボタンの下位／上位8ビット
    - hat: 方向パッドの状態（押下時は対応する値、解放時は Hat.CENTER）
    - lx, ly: 左スティックの X, Y 座標（中央は 0x80）
    - rx, ry: 右スティックの X, Y 座標（中央は 0x80）
    - kbdheader, key, centinel: キーボード入力用フィールド（kbdheader は操作の種類、key はキーの文字、centinel は常に 0x00）
    """
    def __init__(self):
        self._initialize_key_state()

    def _initialize_key_state(self) -> None:
        # 初期状態：キーはすべて未押下、スティックは中央位置、Hat は CENTER
        self.key_state = bytearray([
            0xAB,       # header
            0x00,       # btn1
            0x00,       # btn2
            Hat.CENTER, # hat
            0x80,       # lx (左スティックX中央)
            0x80,       # ly (左スティックY中央)
            0x80,       # rx (右スティックX中央)
            0x80,       # ry (右スティックY中央)
            0x00,       # kbdheader
            0x00,       # key
            0x00        # centinel (未使用)
        ])

    def build_press_command(self, keys: tuple[KeyType, ...]) -> bytes:
        # 各キーに対して、内部状態を更新する
        for key in keys:
            if isinstance(key, Button):
                # ボタンは2バイト（btn1, btn2）にわたってマスクする
                self.key_state[1] |= (key & 0xFF)
                self.key_state[2] |= ((key >> 8) & 0xFF)
            elif isinstance(key, Hat):
                self.key_state[3] = key
            elif isinstance(key, LStick):
                self.key_state[4] = key.x
                self.key_state[5] = key.y
            elif isinstance(key, RStick):
                self.key_state[6] = key.x
                self.key_state[7] = key.y

        # 生成された状態をそのままコマンドデータとして返す
        return bytes(self.key_state)

    def build_release_command(self, keys: tuple[KeyType, ...]) -> bytes:
        # キーが指定されなければ、全体を初期状態にリセット
        if not keys:
            self._initialize_key_state()
        else:
            for key in keys:
                if isinstance(key, Button):
                    self.key_state[1] &= (~(key & 0xFF)) & 0xFF
                    self.key_state[2] &= (~((key >> 8) & 0xFF)) & 0xFF
                elif isinstance(key, Hat):
                    self.key_state[3] = Hat.CENTER
                elif isinstance(key, LStick):
                    self.key_state[4] = 0x80
                    self.key_state[5] = 0x80
                elif isinstance(key, RStick):
                    self.key_state[6] = 0x80
                    self.key_state[7] = 0x80

        return bytes(self.key_state)

    def build_keyboard_command(self, key: str, op: KeyboardOp) -> bytes:
        # キーボード操作の状態を更新する
        # キーボード操作のヘッダーを設定
        self.key_state[8] = int(op)

        # キーの状態を更新
        if op == KeyboardOp.ALL_RELEASE:
            self.key_state[9] = 0x00
        else:
            encoded = key.encode('ascii', errors='ignore') 
            self.key_state[9] = encoded[0] if len(encoded) > 0 else 0x00

        return bytes(self.key_state)
