
import cv2
from typing import Tuple
from dataclasses import dataclass

from .exceptions import TemplateMatchingError, InvalidImageError, ThresholdNotMetError


@dataclass
class MatchResult:
    """テンプレートマッチングの結果"""
    position: Tuple[int, int]  # (x, y)
    confidence: float
    bounding_box: Tuple[int, int, int, int]  # (x, y, width, height)


def find_template(source_image: cv2.typing.MatLike, 
                  template_image: cv2.typing.MatLike,
                  threshold: float = 0.8,
                  method: int = cv2.TM_CCOEFF_NORMED) -> MatchResult:
    """
    テンプレートマッチングを実行し、最良の結果を返す

    :param source_image: 検索対象の画像
    :param template_image: テンプレート画像
    :param threshold: マッチング閾値（0.0-1.0）
    :param method: マッチング手法（cv2.TM_* 定数）
    :return: マッチング結果
    :raises InvalidImageError: 画像データが無効な場合
    :raises ThresholdNotMetError: 閾値を満たす結果が見つからない場合
    """
    if source_image is None or template_image is None:
        raise InvalidImageError("Source image or template image is None")

    if source_image.size == 0 or template_image.size == 0:
        raise InvalidImageError("Source image or template image is empty")

    # 画像サイズチェック
    if (template_image.shape[0] > source_image.shape[0] or 
        template_image.shape[1] > source_image.shape[1]):
        raise InvalidImageError("Template image is larger than source image")

    try:
        # テンプレートマッチング実行
        result = cv2.matchTemplate(source_image, template_image, method)
        
        # 最大値または最小値とその位置を取得
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            match_val = min_val
            match_loc = min_loc
            # SQDIFF系は値が小さいほど良いマッチ
            confidence = 1.0 - match_val if method == cv2.TM_SQDIFF_NORMED else 1.0 / (1.0 + match_val)
        else:
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            match_val = max_val
            match_loc = max_loc
            confidence = match_val

        # 閾値チェック
        if confidence < threshold:
            raise ThresholdNotMetError(
                f"Template matching confidence {confidence:.3f} is below threshold {threshold:.3f}"
            )

        # バウンディングボックス計算
        h, w = template_image.shape[:2]
        bounding_box = (match_loc[0], match_loc[1], w, h)

        return MatchResult(
            position=match_loc,
            confidence=confidence,
            bounding_box=bounding_box
        )

    except cv2.error as e:
        raise TemplateMatchingError(f"OpenCV template matching failed: {e}")


def contains_template(source_image: cv2.typing.MatLike,
                     template_image: cv2.typing.MatLike,
                     threshold: float = 0.8,
                     method: int = cv2.TM_CCOEFF_NORMED) -> bool:
    """
    指定されたテンプレートが画像内に含まれているかを判定
    
    :param source_image: 検索対象の画像
    :param template_image: テンプレート画像
    :param threshold: マッチング閾値（0.0-1.0）
    :param method: マッチング手法（cv2.TM_* 定数）
    :return: テンプレートが含まれている場合True
    """
    try:
        find_template(source_image, template_image, threshold, method)
        return True
    except (ThresholdNotMetError, InvalidImageError, TemplateMatchingError):
        return False
