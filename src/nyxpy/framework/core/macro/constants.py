import math
from enum import IntEnum
from typing import Union

class Button(IntEnum):
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

class Hat(IntEnum):
    UP = 0x00
    UPRIGHT = 0x01
    RIGHT = 0x02
    DOWNRIGHT = 0x03
    DOWN = 0x04
    DOWNLEFT = 0x05
    LEFT = 0x06
    UPLEFT = 0x07
    CENTER = 0x08

class LStick():
    def __init__(self, rad:float, magnification:float, is_degree = False):
        if is_degree == True: 
            rad = math.radians(rad) # 入力を度数法として解釈
        self.rad = rad
        self.mag = magnification
        if magnification > 1.0:
            self.mag = 1.0
        if magnification < 0:
            self.mag = 0.0

        # 小数点演算誤差を考慮する必要は無い
        self.x = math.ceil(127.5 * math.cos(rad) * self.mag + 127.5) 
        self.y = 255 - math.ceil(127.5 * math.sin(rad) * self.mag + 127.5) #y軸のみ反転を考慮する

LStick.RIGHT = LStick((0/8)*math.tau, 1.0)
LStick.UPRIGHT = LStick((1/8)*math.tau, 1.0)
LStick.UP = LStick((2/8)*math.tau, 1.0)
LStick.UPLEFT = LStick((3/8)*math.tau, 1.0)
LStick.LEFT = LStick((4/8)*math.tau, 1.0)
LStick.DOWNLEFT = LStick((5/8)*math.tau, 1.0)
LStick.DOWN = LStick((6/8)*math.tau, 1.0)
LStick.DOWNRIGHT = LStick((7/8)*math.tau, 1.0)
LStick.CENTER = LStick(0.0, 0.0)

class RStick():
    def __init__(self, rad:float, magnification:float, is_degree = False):
        if is_degree == True: 
            rad = math.radians(rad) # 入力を度数法として解釈
        self.rad = rad
        self.mag = magnification
        if magnification > 1.0:
            self.mag = 1.0
        if magnification < 0:
            self.mag = 0.0

        # 小数点演算誤差を考慮する必要は無い
        self.x = math.ceil(127.5 * math.cos(rad) * self.mag + 127.5) 
        self.y = 255 - math.ceil(127.5 * math.sin(rad) * self.mag + 127.5) #y軸のみ反転を考慮する

RStick.RIGHT = RStick((0/8)*math.tau, 1.0)
RStick.UPRIGHT = RStick((1/8)*math.tau, 1.0)
RStick.UP = RStick((2/8)*math.tau, 1.0)
RStick.UPLEFT = RStick((3/8)*math.tau, 1.0)
RStick.LEFT = RStick((4/8)*math.tau, 1.0)
RStick.DOWNLEFT = RStick((5/8)*math.tau, 1.0)
RStick.DOWN = RStick((6/8)*math.tau, 1.0)
RStick.DOWNRIGHT = RStick((7/8)*math.tau, 1.0)
RStick.CENTER = RStick(0.0, 0.0)

# キーとして許容する型
KeyType = Union[Button, Hat, LStick, RStick]

# キーボード操作の種類を定義する列挙型
class KeyboardOp(IntEnum):
    PRESS = 1
    RELEASE = 2
    SPECIAL_PRESS = 3
    SPECIAL_RELEASE = 4
    ALL_RELEASE = 5
    PUSH = 6 # UNUSED
    SPECIAL_PUSH = 7 # UNUSED

# キーボードの通常キーのキーコードを定義
class KeyCode(int):
    def __new__(cls, char: str = None):
        # 空文字又は Noneの時は0x00として扱う
        if char is None or len(char) == 0:
            char = chr(0x00)
        elif len(char) > 1:
            raise ValueError(f"KeyCode must be a single character, got '{char}'")

        ascii_code = ord(char)
        if ascii_code > 127:
            raise ValueError(f"Character '{char}' is not in ASCII range")
        
        instance = super().__new__(cls, ascii_code)
        instance.char = char
        return instance
        
    def __str__(self):
        return self.char

# キーボードの特殊キーのキーコードを定義
class SpecialKeyCode(IntEnum):
    """
    キーボードの特殊キーのキーコードを定義します。
    特殊キー（ENTER, ESCAPE, BACKSPACE, TAB, SPACEなど）を定義します。
    また、日本語キーボード固有の半角・全角なども含みます
    """
    # 特殊キー
    ENTER = 0x28
    ESCAPE = 0x29
    BACKSPACE = 0x2A
    TAB = 0x2B
    SPACE = 0x22
    
    # JPキーボード固有
    HANZEN = 0x35
    BLACKSLASH = 0x87
    HIRAGANA = 0x88
    YEN = 0x89
    HENKAN = 0x8A
    MUHENKAN = 0x8B

    # 方向キー
    ARROW_RIGHT = 0x4F
    ARROW_LEFT = 0x50
    ARROW_DOWN = 0x51
    ARROW_UP = 0x52
    
    def __str__(self):
        return self.value
