"""1 枚の画像に対する画像処理 API。"""

import cv2

from .exceptions import InvalidImageError
from .ocr_engine import OCRProcessor
from .template_matcher import MatchResult, contains_template, find_template
from .utils import ImagePreprocessor


class ImageProcessor:
    """1 枚の OpenCV 画像に対する画像処理 API。

    テンプレートマッチング、OCR、用途別前処理をまとめて呼び出す入口です。
    `image` が `None` または空画像の場合は `InvalidImageError` を送出します。
    """

    def __init__(self, image: cv2.typing.MatLike):
        """処理対象の画像を保持します。

        Args:
            image: 処理対象の画像。OpenCV 形式。

        """
        if image is None or image.size == 0:
            raise InvalidImageError("画像が無効です")
        self.image = image
        self.preprocessor = ImagePreprocessor()

    def contains_template(
        self,
        template: cv2.typing.MatLike,
        threshold: float = 0.8,
        method: int = cv2.TM_CCOEFF_NORMED,
        preprocess: bool = False,
    ) -> bool:
        """指定されたテンプレートが画像内に含まれるかを判定します。

        Args:
            template: テンプレート画像。
            threshold: マッチング閾値。
            method: マッチング手法。
            preprocess: 前処理を行うか。

        Returns:
            テンプレートが含まれている場合は `True`。

        """
        source_img = self.image
        template_img = template

        if preprocess:
            source_img = self.preprocessor.enhance_for_template_matching(source_img)
            template_img = self.preprocessor.enhance_for_template_matching(template_img)

        return contains_template(source_img, template_img, threshold, method)

    def find_template(
        self,
        template: cv2.typing.MatLike,
        threshold: float = 0.8,
        method: int = cv2.TM_CCOEFF_NORMED,
        preprocess: bool = False,
    ) -> MatchResult:
        """テンプレートマッチングを実行し、最良の一致を返します。

        Args:
            template: テンプレート画像。
            threshold: マッチング閾値。
            method: マッチング手法。
            preprocess: 前処理を行うか。

        Returns:
            マッチング結果。

        """
        source_img = self.image
        template_img = template

        if preprocess:
            source_img = self.preprocessor.enhance_for_template_matching(source_img)
            template_img = self.preprocessor.enhance_for_template_matching(template_img)

        return find_template(source_img, template_img, threshold, method)

    def get_text(
        self,
        language: str = "ja",
        region: tuple[int, int, int, int] | None = None,
        preprocess: bool = False,
    ) -> str:
        """画像からテキストを認識し、最も信頼度の高い文字列を返します。

        Args:
            language: 認識言語。`"ja"` または `"en"`。
            region: 認識領域 `(x, y, width, height)`。指定しない場合は全体。
            preprocess: OCR 用前処理を行うか。

        Returns:
            認識されたテキスト。見つからない場合は空文字列。

        """
        # OCRプロセッサーの取得（言語ごとにキャッシュされたシングルトン）
        ocr = OCRProcessor.get_instance(language)

        # 認識対象画像の決定
        target_image = self.image
        if region is not None:
            x, y, w, h = region
            target_image = self.image[y : y + h, x : x + w]

        # 前処理
        if preprocess:
            target_image = self.preprocessor.enhance_for_ocr(target_image)

        # OCR実行
        return ocr.get_best_text(target_image)

    def get_digits(
        self,
        language: str = "en",
        region: tuple[int, int, int, int] | None = None,
        preprocess: bool = False,
    ) -> str:
        """画像から数字のみを認識して返します。

        Args:
            language: 認識言語。`"ja"` または `"en"`。
            region: 認識領域 `(x, y, width, height)`。指定しない場合は全体。
            preprocess: OCR 用前処理を行うか。

        Returns:
            認識された数字文字列。

        """
        # OCRプロセッサーの取得（言語ごとにキャッシュされたシングルトン）
        ocr = OCRProcessor.get_instance(language)

        # 認識対象画像の決定
        target_image = self.image
        if region is not None:
            x, y, w, h = region
            target_image = self.image[y : y + h, x : x + w]

        # 前処理
        if preprocess:
            target_image = self.preprocessor.enhance_for_ocr(target_image)

        # 数字抽出
        return ocr.extract_digits(target_image)

    def find_text_region_with_template(
        self,
        template: cv2.typing.MatLike,
        roi_offset: tuple[int, int, int, int] = (0, 0, 0, 0),
        language: str = "ja",
        template_threshold: float = 0.8,
        preprocess: bool = False,
    ) -> str:
        """テンプレートマッチングでテキスト領域を特定し、OCR を実行します。

        Args:
            template: テンプレート画像。
            roi_offset: マッチ位置からの相対オフセット
                `(x_offset, y_offset, w_offset, h_offset)`。
            language: OCR 認識言語。
            template_threshold: テンプレートマッチングの閾値。
            preprocess: 前処理を行うか。

        Returns:
            認識されたテキスト。

        """
        # テンプレートマッチング
        match = self.find_template(template, template_threshold, preprocess=preprocess)
        x, y, w, h = match.bounding_box

        # オフセット適用
        x_off, y_off, w_off, h_off = roi_offset
        roi = (x + x_off, y + y_off, w + w_off, h + h_off)

        # OCR実行
        return self.get_text(language, roi, preprocess)
