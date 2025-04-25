"""
共通型定義

このモジュールはシステム全体で使用される共通型を定義します。
"""

from typing import Union
from .controller import Button, Hat
from .stick import LStick, RStick

# キーとして許容する型
KeyType = Union[Button, Hat, LStick, RStick]
