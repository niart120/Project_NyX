from abc import ABC, abstractmethod

from nyxpy.framework.core.constants import (
    Button,
    Hat,
    KeyboardOp,
    KeyCode,
    KeyType,
    LStick,
    RStick,
    SpecialKeyCode,
    ThreeDSButton,
    TouchState,
)


class SerialProtocolInterface(ABC):
    @abstractmethod
    def build_press_command(self, keys: tuple[KeyType, ...]) -> bytes:
        """キー押下操作のコマンドデータを生成する

        :param keys: 押下するキーのタプル
        :return: コマンドデータ
        """
        pass

    @abstractmethod
    def build_hold_command(self, keys: tuple[KeyType, ...]) -> bytes:
        """キー保持操作のコマンドデータを生成する

        :param keys: ホールドするキーのタプル
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
    def build_keytype_command(self, key: KeyCode | SpecialKeyCode, op: KeyboardOp) -> bytes:
        """
        キーボード個別キー操作のコマンドデータを生成する

        :param key: 操作するキーの文字
        :param op: KeyboardOp キーボード操作の種類
        :return: コマンドデータ
        :raises NotImplementedError: プロトコルが対応していない場合
        """
        pass


class UnsupportedKeyError(ValueError):
    """指定されたキーが対象プロトコルで表現できない場合の例外。"""


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
        self.key_state = bytearray(
            [
                0xAB,  # header
                0x00,  # btn1
                0x00,  # btn2
                Hat.CENTER,  # hat
                0x80,  # lx (左スティックX中央)
                0x80,  # ly (左スティックY中央)
                0x80,  # rx (右スティックX中央)
                0x80,  # ry (右スティックY中央)
                0x00,  # kbdheader
                0x00,  # key
                0x00,  # centinel (未使用)
            ]
        )

    def build_press_command(self, keys: tuple[KeyType, ...]) -> bytes:
        # 各キーに対して、内部状態を更新する
        for key in keys:
            if isinstance(key, Button):
                # ボタンは2バイト（btn1, btn2）にわたってマスクする
                self.key_state[1] |= key & 0xFF
                self.key_state[2] |= (key >> 8) & 0xFF
            elif isinstance(key, Hat):
                self.key_state[3] = key
            elif isinstance(key, LStick):
                self.key_state[4] = key.x
                self.key_state[5] = key.y
            elif isinstance(key, RStick):
                self.key_state[6] = key.x
                self.key_state[7] = key.y
            elif isinstance(key, ThreeDSButton | TouchState):
                raise UnsupportedKeyError(f"CH552 protocol does not support {key!r}.")

        # 生成された状態をそのままコマンドデータとして返す
        return bytes(self.key_state)

    def build_hold_command(self, keys: tuple[KeyType, ...]) -> bytes:
        # キー入力状態をリセット
        self._initialize_key_state()
        # 各キーに対して、内部状態を更新する
        for key in keys:
            if isinstance(key, Button):
                # ボタンは2バイト（btn1, btn2）にわたってマスクする
                self.key_state[1] |= key & 0xFF
                self.key_state[2] |= (key >> 8) & 0xFF
            elif isinstance(key, Hat):
                self.key_state[3] = key
            elif isinstance(key, LStick):
                self.key_state[4] = key.x
                self.key_state[5] = key.y
            elif isinstance(key, RStick):
                self.key_state[6] = key.x
                self.key_state[7] = key.y
            elif isinstance(key, ThreeDSButton | TouchState):
                raise UnsupportedKeyError(f"CH552 protocol does not support {key!r}.")

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
                elif isinstance(key, ThreeDSButton | TouchState):
                    raise UnsupportedKeyError(f"CH552 protocol does not support {key!r}.")

        return bytes(self.key_state)

    def build_keyboard_command(self, text: str) -> bytes:
        # CH552はテキスト入力をサポートしていないため、すべての操作でエラーを発生させる
        raise NotImplementedError(
            "CH552 protocol does not support text mode keyboard input. Use build_keytype_command instead."
        )

    def build_keytype_command(self, key: KeyCode | SpecialKeyCode, op: KeyboardOp) -> bytes:
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
        self.key_state: list[int] = list(
            [
                0x0003,  # hex_btns (16ビット)
                Hat.CENTER,  # hex_hat
                0x80,  # hex_pc_lx (左スティックX中央)
                0x80,  # hex_pc_ly (左スティックY中央)
                0x80,  # hex_pc_rx (右スティックX中央)
                0x80,  # hex_pc_ry (右スティックY中央)
            ]
        )

    def build_press_command(self, keys: tuple[KeyType, ...]) -> bytes:
        # 各キーに対して、内部状態を更新する
        for key in keys:
            if isinstance(key, Button):
                # ボタンは16ビット（hex_btns）にわたってマスクする
                self.key_state[0] |= (key << 2) & 0xFFFF  # Update to use hex_btns
            elif isinstance(key, Hat):
                self.key_state[1] = key
            elif isinstance(key, LStick):
                self.key_state[2] = key.x
                self.key_state[3] = key.y
            elif isinstance(key, RStick):
                self.key_state[4] = key.x
                self.key_state[5] = key.y
            elif isinstance(key, ThreeDSButton | TouchState):
                raise UnsupportedKeyError(f"PokeCon protocol does not support {key!r}.")

        # 生成された状態を16進数の文字列に変換後、バイト列として返す
        hex_string = f"{self.key_state[0]:#X} {self.key_state[1]:X} {self.key_state[2]:X} {self.key_state[3]:X} {self.key_state[4]:X} {self.key_state[5]:X}\r\n"
        # 16進数の改行コード付き文字列をバイト列(UTF-8)に変換
        return hex_string.encode("utf-8")

    def build_hold_command(self, keys: tuple[KeyType, ...]) -> bytes:
        # キー入力状態をリセット
        self._initialize_key_state()
        # 各キーに対して、内部状態を更新する
        for key in keys:
            if isinstance(key, Button):
                # ボタンは16ビット（hex_btns）にわたってマスクする
                self.key_state[0] |= (key << 2) & 0xFFFF  # Update to use hex_btns
            elif isinstance(key, Hat):
                self.key_state[1] = key
            elif isinstance(key, LStick):
                self.key_state[2] = key.x
                self.key_state[3] = key.y
            elif isinstance(key, RStick):
                self.key_state[4] = key.x
                self.key_state[5] = key.y
            elif isinstance(key, ThreeDSButton | TouchState):
                raise UnsupportedKeyError(f"PokeCon protocol does not support {key!r}.")

        # 生成された状態を16進数の文字列に変換後、バイト列として返す
        hex_string = f"{self.key_state[0]:#X} {self.key_state[1]:X} {self.key_state[2]:X} {self.key_state[3]:X} {self.key_state[4]:X} {self.key_state[5]:X}\r\n"
        # 16進数の改行コード付き文字列をバイト列(UTF-8)に変換
        return hex_string.encode("utf-8")

    def build_release_command(self, keys: tuple[KeyType, ...]) -> bytes:
        # キーが指定されなければ、全体を初期状態にリセット
        if not keys:
            self._initialize_key_state()
        else:
            for key in keys:
                if isinstance(key, Button):
                    self.key_state[0] &= (~((key << 2) & 0xFFFF)) & 0xFFFF
                elif isinstance(key, Hat):
                    self.key_state[1] = Hat.CENTER
                elif isinstance(key, LStick):
                    self.key_state[2] = 0x80
                    self.key_state[3] = 0x80
                elif isinstance(key, RStick):
                    self.key_state[4] = 0x80
                    self.key_state[5] = 0x80
                elif isinstance(key, ThreeDSButton | TouchState):
                    raise UnsupportedKeyError(f"PokeCon protocol does not support {key!r}.")
        # 生成された状態を16進数の文字列に変換後、バイト列として返す
        hex_string = f"{self.key_state[0]:#X} {self.key_state[1]:X} {self.key_state[2]:X} {self.key_state[3]:X} {self.key_state[4]:X} {self.key_state[5]:X}\r\n"
        # 16進数の改行コード付き文字列をバイト列(UTF-8)に変換
        return hex_string.encode("utf-8")

    def build_keyboard_command(self, key: str) -> bytes:
        # テキスト入力操作のコマンドを生成する
        # 文字列をバイト列に変換して返す
        encoded = f'"{key}"'.encode("utf-8", errors="ignore")
        return encoded + b"\r\n"

    def build_keytype_command(self, key: KeyCode | SpecialKeyCode, op: KeyboardOp) -> bytes:
        # キーボード個別キー操作の種類に応じて、コマンドを生成する
        match op:
            case KeyboardOp.SPECIAL_PUSH:
                # 特殊キー打鍵操作のコマンドを生成する
                encoded = f"KEY {int(key)}\r\n".encode("utf-8", errors="ignore")
                return encoded

            case KeyboardOp.SPECIAL_PRESS:
                # 特殊キー押下操作のコマンドを生成する
                encoded = f"PRESS {int(key)}\r\n".encode("utf-8", errors="ignore")
                return encoded
            case KeyboardOp.SPECIAL_RELEASE:
                # 特殊キー解放操作のコマンドを生成する
                encoded = f"RELEASE {int(key)}\r\n".encode("utf-8", errors="ignore")
                return encoded

            case KeyboardOp.PUSH | KeyboardOp.PRESS:
                # 通常キー押下操作のコマンドを生成する
                # PokeConプロトコルは、通常キーの押下操作をサポートしないため、テキスト入力形式のコマンドで代替する
                encoded = f'"{str(key)}"\r\n'.encode("utf-8", errors="ignore")
                return encoded

            case KeyboardOp.RELEASE:
                # PokeConプロトコルは通常のキー操作の解放コマンドを持たないため、ここでは何もしない
                pass

            case KeyboardOp.ALL_RELEASE:
                # すべてのキー解放操作のコマンドを生成する
                # PokeConプロトコルはすべてのキー解放操作をサポートしないため、エラーを発生させる
                raise NotImplementedError(
                    "PokeCon protocol does not support ALL_RELEASE operation."
                )
            case _:
                raise ValueError("Unsupported keyboard operation type")


class ThreeDSSerialProtocol(SerialProtocolInterface):
    """Nintendo 3DS 向け S2/T3 シリアルプロトコル実装。"""

    _BUTTON_MASKS: dict[Button, int] = {
        Button.Y: 0x0080,
        Button.B: 0x0020,
        Button.A: 0x0010,
        Button.X: 0x0040,
        Button.L: 0x0100,
        Button.R: 0x0200,
        Button.ZL: 0x4000,
        Button.ZR: 0x8000,
        Button.MINUS: 0x1000,
        Button.PLUS: 0x0800,
        Button.HOME: 0x0400,
    }

    _HAT_MASKS: dict[Hat, int] = {
        Hat.LEFT: 0x01,
        Hat.DOWN: 0x02,
        Hat.RIGHT: 0x04,
        Hat.UP: 0x08,
        Hat.UPRIGHT: 0x0C,
        Hat.DOWNRIGHT: 0x06,
        Hat.DOWNLEFT: 0x03,
        Hat.UPLEFT: 0x09,
        Hat.CENTER: 0x00,
    }

    def __init__(self):
        self._initialize_key_state()

    def _initialize_key_state(self) -> None:
        self.button_mask = 0x0000
        self.slide_x = 0x80
        self.slide_y = 0x80
        self.c_stick_x = 0x00
        self.c_stick_y = 0x00
        self.touch_pressed = False
        self.touch_x = 0
        self.touch_y = 0

    def _build_frame(self) -> bytes:
        touch_flag = 0x01 if self.touch_pressed else 0x00
        x_high = (self.touch_x >> 8) & 0xFF if self.touch_pressed else 0x00
        x_low = self.touch_x & 0xFF if self.touch_pressed else 0x00
        y_low = self.touch_y & 0xFF if self.touch_pressed else 0x00
        return bytes(
            [
                0xA1,
                self.button_mask & 0xFF,
                (self.button_mask >> 8) & 0xFF,
                0xA2,
                self.slide_x,
                self.slide_y,
                0xA4,
                self.c_stick_x,
                self.c_stick_y,
                0xB2,
                touch_flag,
                x_high,
                x_low,
                y_low,
            ]
        )

    def _apply_press_key(self, key: KeyType) -> None:
        if isinstance(key, Button | ThreeDSButton):
            self.button_mask |= self._button_mask(key)
        elif isinstance(key, Hat):
            self.button_mask |= self._hat_mask(key)
        elif isinstance(key, LStick):
            self.slide_x = self._convert_slide_axis(key.x)
            self.slide_y = self._convert_slide_axis(key.y)
        elif isinstance(key, RStick):
            self.c_stick_x = self._convert_c_stick_axis(key.x)
            self.c_stick_y = self._convert_c_stick_axis(key.y)
        elif isinstance(key, TouchState):
            self._set_touch_state(key)

    def _apply_release_key(self, key: KeyType) -> None:
        if isinstance(key, Button | ThreeDSButton):
            self.button_mask &= ~self._button_mask(key) & 0xFFFF
        elif isinstance(key, Hat):
            self.button_mask &= ~self._hat_mask(key) & 0xFFFF
        elif isinstance(key, LStick):
            self.slide_x = 0x80
            self.slide_y = 0x80
        elif isinstance(key, RStick):
            self.c_stick_x = 0x00
            self.c_stick_y = 0x00
        elif isinstance(key, TouchState):
            self._set_touch_up()

    def _button_mask(self, key: Button | ThreeDSButton) -> int:
        if isinstance(key, ThreeDSButton):
            if key == ThreeDSButton.POWER:
                return 0x2000
            raise UnsupportedKeyError(f"3DS protocol does not support {key!r}.")
        if key not in self._BUTTON_MASKS:
            raise UnsupportedKeyError(f"3DS protocol does not support {key!r}.")
        return self._BUTTON_MASKS[key]

    def _hat_mask(self, key: Hat) -> int:
        return self._HAT_MASKS[key]

    def _set_touch_state(self, touch: TouchState) -> None:
        if touch.pressed:
            self._validate_touch(touch.x, touch.y)
            self.touch_pressed = True
            self.touch_x = touch.x
            self.touch_y = touch.y
        else:
            self._set_touch_up()

    def _set_touch_up(self) -> None:
        self.touch_pressed = False
        self.touch_x = 0
        self.touch_y = 0

    @staticmethod
    def _validate_touch(x: int, y: int) -> None:
        if not 0 <= x <= 320:
            raise ValueError("Touch X must be in range 0..320")
        if not 0 <= y <= 240:
            raise ValueError("Touch Y must be in range 0..240")

    @staticmethod
    def _convert_slide_axis(value: int) -> int:
        if not 0 <= value <= 255:
            raise ValueError("Stick axis must be in range 0..255")
        if value <= 128:
            return round(0x7E + (value / 128) * (0x80 - 0x7E))
        return round(0x80 + ((value - 128) / 127) * (0xFA - 0x80))

    @staticmethod
    def _convert_c_stick_axis(value: int) -> int:
        if not 0 <= value <= 255:
            raise ValueError("Stick axis must be in range 0..255")
        if value in (127, 128):
            return 0x00
        return max(-128, min(127, value - 128)) & 0xFF

    @staticmethod
    def _validate_calibration_values(values: tuple[int, ...]) -> None:
        for value in values:
            if not 0 <= value <= 255:
                raise ValueError("Touch calibration value must be in range 0..255")

    def build_press_command(self, keys: tuple[KeyType, ...]) -> bytes:
        for key in keys:
            self._apply_press_key(key)
        return self._build_frame()

    def build_hold_command(self, keys: tuple[KeyType, ...]) -> bytes:
        self._initialize_key_state()
        for key in keys:
            self._apply_press_key(key)
        return self._build_frame()

    def build_release_command(self, keys: tuple[KeyType, ...]) -> bytes:
        if not keys:
            self._initialize_key_state()
        else:
            for key in keys:
                self._apply_release_key(key)
        return self._build_frame()

    def build_touch_down_command(self, x: int, y: int) -> bytes:
        self._set_touch_state(TouchState.down(x, y))
        return self._build_frame()

    def build_touch_up_command(self) -> bytes:
        self._set_touch_up()
        return self._build_frame()

    def build_disable_sleep_command(self, enabled: bool) -> bytes:
        return bytes([0xFC, 0x01 if enabled else 0x00])

    def build_touch_calibration_write_command(
        self,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        *,
        factory: bool = False,
    ) -> bytes:
        values = (x_min, x_max, y_min, y_max)
        self._validate_calibration_values(values)
        header = 0xB6 if factory else 0xB3
        return bytes([header, *values])

    def build_touch_calibration_read_command(self) -> bytes:
        return bytes([0xB4])

    def build_touch_calibration_factory_reset_command(self) -> bytes:
        return bytes([0xB5])

    def build_keyboard_command(self, text: str) -> bytes:
        raise NotImplementedError("3DS protocol does not support keyboard input.")

    def build_keytype_command(self, key: KeyCode | SpecialKeyCode, op: KeyboardOp) -> bytes:
        raise NotImplementedError("3DS protocol does not support keyboard input.")
