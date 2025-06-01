
import cv2
from typing import Tuple, Optional


class ImagePreprocessor:
    """画像前処理ユーティリティ"""
    
    @staticmethod
    def enhance_contrast(image: cv2.typing.MatLike,
                        clip_limit: float = 2.0,
                        tile_grid_size: Tuple[int, int] = (8, 8)) -> cv2.typing.MatLike:
        """
        コントラスト強化（CLAHE）
        
        :param image: 入力画像
        :param clip_limit: クリップ制限値
        :param tile_grid_size: タイルグリッドサイズ
        :return: コントラスト強化された画像
        """
        # グレースケール変換
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
            
        # CLAHE適用
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        enhanced = clahe.apply(gray)
        
        # 元画像と同じチャンネル数に戻す
        if len(image.shape) == 3:
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
            
        return enhanced
    
    @staticmethod
    def denoise(image: cv2.typing.MatLike, strength: int = 7) -> cv2.typing.MatLike:
        """
        ノイズ除去
        
        :param image: 入力画像
        :param strength: ノイズ除去強度
        :return: ノイズ除去された画像
        """
        if len(image.shape) == 3:
            return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)
        else:
            return cv2.fastNlMeansDenoising(image, None, strength, 7, 21)
    
    @staticmethod
    def sharpen(image: cv2.typing.MatLike,
               kernel_size: int = 5,
               sigma: float = 1.0,
               amount: float = 1.0) -> cv2.typing.MatLike:
        """
        シャープニング（アンシャープマスク）
        
        :param image: 入力画像
        :param kernel_size: カーネルサイズ
        :param sigma: ガウシアンぼかしのシグマ値
        :param amount: シャープニング強度
        :return: シャープニングされた画像
        """
        blurred = cv2.GaussianBlur(image, (kernel_size, kernel_size), sigma)
        sharpened = cv2.addWeighted(image, 1.0 + amount, blurred, -amount, 0)
        return sharpened
    
    @staticmethod
    def binarize(image: cv2.typing.MatLike,
                threshold: Optional[int] = None,
                adaptive: bool = True,
                inverse: bool = False) -> cv2.typing.MatLike:
        """
        二値化処理
        
        :param image: 入力画像
        :param threshold: 閾値（Noneの場合は自動決定）
        :param adaptive: 適応的閾値処理を使用するか
        :param inverse: 反転するか
        :return: 二値化された画像
        """
        # グレースケール変換
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
            
        # 閾値処理の種類を設定
        thresh_type = cv2.THRESH_BINARY_INV if inverse else cv2.THRESH_BINARY
        
        if adaptive:
            # 適応的閾値処理
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, thresh_type, 11, 2)
        else:
            # 固定閾値処理
            if threshold is None:
                # 大津の方法で自動閾値決定
                threshold, binary = cv2.threshold(
                    gray, 0, 255, thresh_type | cv2.THRESH_OTSU)
            else:
                # 指定閾値で処理
                _, binary = cv2.threshold(gray, threshold, 255, thresh_type)
                
        return binary
    
    @staticmethod
    def enhance_for_template_matching(image: cv2.typing.MatLike) -> cv2.typing.MatLike:
        """
        テンプレートマッチング用の前処理
        
        :param image: 入力画像
        :return: 前処理された画像
        """
        # マッチングに適した前処理
        processed = ImagePreprocessor.denoise(image, strength=5)
        processed = ImagePreprocessor.enhance_contrast(processed)
        return processed
    
    @staticmethod
    def enhance_for_ocr(image: cv2.typing.MatLike) -> cv2.typing.MatLike:
        """
        OCR用の前処理
        
        :param image: 入力画像
        :return: 前処理された画像
        """
        # OCRに適した前処理
        processed = ImagePreprocessor.denoise(image, strength=5)
        processed = ImagePreprocessor.sharpen(processed, amount=0.5)
        processed = ImagePreprocessor.enhance_contrast(processed)
        return processed
