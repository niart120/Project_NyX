"""
共通型定義

このモジュールはシステム全体で使用される共通型を定義します。
"""

from .controller import Button, Hat, ThreeDSButton, TouchState
from .stick import LStick, RStick

# キーとして許容する型
KeyType = Button | Hat | LStick | RStick | ThreeDSButton | TouchState
