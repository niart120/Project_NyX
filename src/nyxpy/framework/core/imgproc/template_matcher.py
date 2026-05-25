"""OpenCV による template matching helper。"""

from dataclasses import dataclass

import cv2

from .exceptions import InvalidImageError, TemplateMatchingError, ThresholdNotMetError


@dataclass
class MatchResult:
    """テンプレートマッチングの結果。"""

    position: tuple[int, int]  # (x, y)
    confidence: float
    bounding_box: tuple[int, int, int, int]  # (x, y, width, height)


def find_template(
    source_image: cv2.typing.MatLike,
    template_image: cv2.typing.MatLike,
    threshold: float = 0.8,
    method: int = cv2.TM_CCOEFF_NORMED,
) -> MatchResult:
    """テンプレートマッチングを実行し、最良の一致を返します。

    Args:
        source_image: 検索対象の画像。
        template_image: テンプレート画像。
        threshold: マッチング閾値。範囲は 0.0-1.0。
        method: マッチング手法。`cv2.TM_*` 定数。

    Returns:
        マッチング結果。

    Raises:
        InvalidImageError: 画像データが無効な場合。
        ThresholdNotMetError: 閾値を満たす結果が見つからない場合。
        TemplateMatchingError: OpenCV の処理に失敗した場合。

    """
    if source_image is None or template_image is None:
        raise InvalidImageError("Source image or template image is None")

    if source_image.size == 0 or template_image.size == 0:
        raise InvalidImageError("Source image or template image is empty")

    # 画像サイズチェック
    if (
        template_image.shape[0] > source_image.shape[0]
        or template_image.shape[1] > source_image.shape[1]
    ):
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
            confidence = (
                1.0 - match_val if method == cv2.TM_SQDIFF_NORMED else 1.0 / (1.0 + match_val)
            )
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
        match_position = (int(match_loc[0]), int(match_loc[1]))
        bounding_box = (match_position[0], match_position[1], w, h)

        return MatchResult(
            position=match_position, confidence=confidence, bounding_box=bounding_box
        )

    except cv2.error as e:
        raise TemplateMatchingError(f"OpenCV template matching failed: {e}")


def contains_template(
    source_image: cv2.typing.MatLike,
    template_image: cv2.typing.MatLike,
    threshold: float = 0.8,
    method: int = cv2.TM_CCOEFF_NORMED,
) -> bool:
    """指定されたテンプレートが画像内に含まれるかを判定します。

    Args:
        source_image: 検索対象の画像。
        template_image: テンプレート画像。
        threshold: マッチング閾値。範囲は 0.0-1.0。
        method: マッチング手法。`cv2.TM_*` 定数。

    Returns:
        テンプレートが含まれている場合は `True`。閾値未達は `False`。

    """
    try:
        find_template(source_image, template_image, threshold, method)
        return True
    except ThresholdNotMetError:
        return False
