from abc import ABC, abstractmethod
from nyxpy.framework.core.macro.constants import Button, Hat, KeyCode, KeyboardOp, LStick, RStick, KeyType, SpecialKeyCode

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
    def build_keyboard_command(self, text: str) -> bytes:
        """
        キーボード文字列入力操作のコマンドデータを生成する
        
        :param text: 入力する文字列
        :return: コマンドデータ
        :raises NotImplementedError: プロトコルが対応していない場合
        """
        pass
        
    @abstractmethod
    def build_keytype_command(self, key: KeyCode|SpecialKeyCode, op: KeyboardOp) -> bytes:
        """
        キーボード個別キー操作のコマンドデータを生成する
        
        :param key: 操作するキーの文字
        :param op: KeyboardOp キーボード操作の種類
        :return: コマンドデータ
        :raises NotImplementedError: プロトコルが対応していない場合
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

    def build_keyboard_command(self, text: str) -> bytes:
        # CH552はテキスト入力をサポートしていないため、すべての操作でエラーを発生させる
        raise NotImplementedError("CH552 protocol does not support text mode keyboard input. Use build_keytype_command instead.")
        
    def build_keytype_command(self, key: KeyCode|SpecialKeyCode, op: KeyboardOp) -> bytes:
        # キーボード個別キー操作の状態を更新する
        # キーボード操作のヘッダーを設定
        self.key_state[8] = int(op)

        # キーの状態を更新
        if op == KeyboardOp.ALL_RELEASE:
            self.key_state[9] = 0x00
        else:
            self.key_state[9] = key

        return bytes(self.key_state)

class PokeConSerialProtocol(SerialProtocolInterface):
    """
    PokeConSerialProtocol は、PokeCon用プログラムが実装された Arduino デバイス向けの通信プロトコルを実装します。
    内部状態（key_state）は以下の構成になっています：
    [hex_btns, hex_hat, hex_pc_lx, hex_pc_ly, hex_pc_rx, hex_pc_ry]
    - hex_btns: ボタンの状態（下位／上位8ビット）
    - hex_hat: 方向パッドの状態（押下時は対応する値、解放時は Hat.CENTER）
    - hex_pc_lx, hex_pc_ly: 左スティックの X, Y 座標（中央は 0x80）
    - hex_pc_rx, hex_pc_ry: 右スティックの X, Y 座標（中央は 0x80）
    """
    def __init__(self):
        self._initialize_key_state()

    def _initialize_key_state(self) -> None:
        # 初期状態：キーはすべて未押下、スティックは中央位置、Hat は CENTER
        self.key_state:list[int] = list([
            0x0003,       # hex_btns (16ビット)
            Hat.CENTER, # hex_hat
            0x80,       # hex_pc_lx (左スティックX中央)
            0x80,       # hex_pc_ly (左スティックY中央)
            0x80,       # hex_pc_rx (右スティックX中央)
            0x80        # hex_pc_ry (右スティックY中央)
        ])

    def build_press_command(self, keys: tuple[KeyType, ...]) -> bytes:
        # 各キーに対して、内部状態を更新する
        for key in keys:
            if isinstance(key, Button):
                # ボタンは16ビット（hex_btns）にわたってマスクする
                self.key_state[0] |= ((key<<2) & 0xFFFF)  # Update to use hex_btns
            elif isinstance(key, Hat):
                self.key_state[1] = key
            elif isinstance(key, LStick):
                self.key_state[2] = key.x
                self.key_state[3] = key.y
            elif isinstance(key, RStick):
                self.key_state[4] = key.x
                self.key_state[5] = key.y

        # 生成された状態を16進数の文字列に変換後、バイト列として返す
        hex_string = f"{self.key_state[0]:#X} {self.key_state[1]:X} {self.key_state[2]:X} {self.key_state[3]:X} {self.key_state[4]:X} {self.key_state[5]:X}\r\n"
        # 16進数の改行コード付き文字列をバイト列(UTF-8)に変換
        return hex_string.encode('utf-8')

    def build_release_command(self, keys: tuple[KeyType, ...]) -> bytes:
        # キーが指定されなければ、全体を初期状態にリセット
        if not keys:
            self._initialize_key_state()
        else:
            for key in keys:
                if isinstance(key, Button):
                    self.key_state[0] &= (~((key<<2) & 0xFFFF)) & 0xFFFF
                elif isinstance(key, Hat):
                    self.key_state[1] = Hat.CENTER
                elif isinstance(key, LStick):
                    self.key_state[2] = 0x80
                    self.key_state[3] = 0x80
                elif isinstance(key, RStick):
                    self.key_state[4] = 0x80
                    self.key_state[5] = 0x80
        # 生成された状態を16進数の文字列に変換後、バイト列として返す
        hex_string = f"{self.key_state[0]:#X} {self.key_state[1]:X} {self.key_state[2]:X} {self.key_state[3]:X} {self.key_state[4]:X} {self.key_state[5]:X}\r\n"
        # 16進数の改行コード付き文字列をバイト列(UTF-8)に変換
        return hex_string.encode('utf-8')

    def build_keyboard_command(self, key: str) -> bytes:
        # テキスト入力操作のコマンドを生成する
        # 文字列をバイト列に変換して返す
        encoded = f'"{key}"'.encode('utf-8', errors='ignore')
        return encoded + b'\r\n'
                
    def build_keytype_command(self, key: KeyCode|SpecialKeyCode, op: KeyboardOp) -> bytes:
        # キーボード個別キー操作の種類に応じて、コマンドを生成する
        match op:

            case KeyboardOp.SPECIAL_PUSH:
                # 特殊キー打鍵操作のコマンドを生成する
                encoded = f"KEY {int(key)}\r\n".encode('utf-8', errors='ignore')
                return encoded
            
            case KeyboardOp.SPECIAL_PRESS:
                # 特殊キー押下操作のコマンドを生成する
                encoded = f"PRESS {int(key)}\r\n".encode('utf-8', errors='ignore')
                return encoded
            case KeyboardOp.SPECIAL_RELEASE:
                # 特殊キー解放操作のコマンドを生成する
                encoded = f"RELEASE {int(key)}\r\n".encode('utf-8', errors='ignore')
                return encoded
            
            case KeyboardOp.PUSH | KeyboardOp.PRESS:
                # 通常キー押下操作のコマンドを生成する
                # PokeConプロトコルは、通常キーの押下操作をサポートしないため、テキスト入力形式のコマンドで代替する
                encoded = f'"{str(key)}"\r\n'.encode('utf-8', errors='ignore')
                return encoded

            case KeyboardOp.RELEASE:
                # PokeConプロトコルは通常のキー操作の解放コマンドを持たないため、ここでは何もしない
                pass

            case KeyboardOp.ALL_RELEASE:
                # すべてのキー解放操作のコマンドを生成する
                # PokeConプロトコルはすべてのキー解放操作をサポートしないため、エラーを発生させる
                raise NotImplementedError("PokeCon protocol does not support ALL_RELEASE operation.")
            case _:
                raise ValueError("Unsupported keyboard operation type")
