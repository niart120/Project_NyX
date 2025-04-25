"""
スティック関連の定数

このモジュールはコントローラーの左右スティックの位置を表す定数を定義します。
"""
import math

class LStick():
    """
    コントローラーの左スティックの位置を表すクラス
    """
    def __init__(self, rad:float, magnification:float, is_degree = False):
        """
        左スティックの位置を初期化します
        
        Args:
            rad: スティックの角度（ラジアン、またはis_degree=Trueの場合は度）
            magnification: スティックの傾き（0.0から1.0）
            is_degree: 角度が度数法（True）かラジアン（False）かを指定
        """
        if is_degree: 
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

# 一般的なスティック位置の定義
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
    """
    コントローラーの右スティックの位置を表すクラス
    """
    def __init__(self, rad:float, magnification:float, is_degree = False):
        """
        右スティックの位置を初期化します
        
        Args:
            rad: スティックの角度（ラジアン、またはis_degree=Trueの場合は度）
            magnification: スティックの傾き（0.0から1.0）
            is_degree: 角度が度数法（True）かラジアン（False）かを指定
        """
        if is_degree: 
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

# 一般的なスティック位置の定義
RStick.RIGHT = RStick((0/8)*math.tau, 1.0)
RStick.UPRIGHT = RStick((1/8)*math.tau, 1.0)
RStick.UP = RStick((2/8)*math.tau, 1.0)
RStick.UPLEFT = RStick((3/8)*math.tau, 1.0)
RStick.LEFT = RStick((4/8)*math.tau, 1.0)
RStick.DOWNLEFT = RStick((5/8)*math.tau, 1.0)
RStick.DOWN = RStick((6/8)*math.tau, 1.0)
RStick.DOWNRIGHT = RStick((7/8)*math.tau, 1.0)
RStick.CENTER = RStick(0.0, 0.0)