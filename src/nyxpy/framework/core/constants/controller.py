"""コントローラーボタン関連の定数。"""

from dataclasses import dataclass
from enum import IntEnum


class Button(IntEnum):
    """コントローラーのボタンを表す定数"""

    Y = 0x0001
    B = 0x0002
    A = 0x0004
    X = 0x0008

    L = 0x0010
    R = 0x0020
    ZL = 0x0040
    ZR = 0x0080

    MINUS = 0x0100
    PLUS = 0x0200

    LS = 0x0400
    RS = 0x0800
    HOME = 0x1000
    CAP = 0x2000

    def __repr__(self):
        """列挙値名を含む表現を返します。"""
        return f"Button.{self.name}"


class Hat(IntEnum):
    """コントローラーの方向キー（HAT）を表す定数"""

    UP = 0x00
    UPRIGHT = 0x01
    RIGHT = 0x02
    DOWNRIGHT = 0x03
    DOWN = 0x04
    DOWNLEFT = 0x05
    LEFT = 0x06
    UPLEFT = 0x07
    CENTER = 0x08

    def __repr__(self):
        """列挙値名を含む表現を返します。"""
        return f"Hat.{self.name}"


class ThreeDSButton(IntEnum):
    """3DS 固有のボタンを表す定数。対応プロトコルでのみ使用できます。"""

    POWER = 0x2000

    def __repr__(self):
        """列挙値名を含む表現を返します。"""
        return f"ThreeDSButton.{self.name}"


@dataclass(frozen=True)
class TouchState:
    """3DS タッチパネルの入力状態。座標は 320x240 の touch 座標です。"""

    pressed: bool
    x: int = 0
    y: int = 0

    @classmethod
    def down(cls, x: int, y: int) -> "TouchState":
        """指定座標を押している状態を返します。"""
        return cls(True, x, y)

    @classmethod
    def up(cls) -> "TouchState":
        """タッチ入力を離した状態を返します。"""
        return cls(False)
