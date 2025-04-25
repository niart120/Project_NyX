"""
コントローラーボタン関連の定数

このモジュールはコントローラーのボタンおよびHAT（十字キー）関連の定数を定義します。
"""

from enum import IntEnum


class Button(IntEnum):
    """
    コントローラーのボタンを表す定数
    """

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
    """
    コントローラーの方向キー（HAT）を表す定数
    """

    UP = 0x00
    UPRIGHT = 0x01
    RIGHT = 0x02
    DOWNRIGHT = 0x03
    DOWN = 0x04
    DOWNLEFT = 0x05
    LEFT = 0x06
    UPLEFT = 0x07
    CENTER = 0x08
