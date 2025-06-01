
import cv2
from typing import Optional, Tuple

from .template_matcher import find_template, contains_template, MatchResult
from .ocr_engine import OCRProcessor
from .utils import ImagePreprocessor
from .exceptions import InvalidImageError


class ImageProcessor:
    """
    画像処理ラッパークラス
    対象画像をコンストラクタで受け取り、シンプルなAPIを提供
    """
    
    def __init__(self, image: cv2.typing.MatLike):
        """
        :param image: 処理対象の画像（OpenCV形式）
        """
        if image is None or image.size == 0:
            raise InvalidImageError("画像が無効です")
        self.image = image
        self._ocr_processor = None  # 遅延初期化
        self.preprocessor = ImagePreprocessor()
    
    def contains_template(self, 
                         template: cv2.typing.MatLike, 
                         threshold: float = 0.8,
                         method: int = cv2.TM_CCOEFF_NORMED,
                         preprocess: bool = False) -> bool:
        """
        指定されたテンプレートが画像内に含まれているかを判定
        
        :param template: テンプレート画像
        :param threshold: マッチング閾値
        :param method: マッチング手法
        :param preprocess: 前処理を行うか
        :return: テンプレートが含まれている場合True
        """
        source_img = self.image
        template_img = template
        
        if preprocess:
            source_img = self.preprocessor.enhance_for_template_matching(source_img)
            template_img = self.preprocessor.enhance_for_template_matching(template_img)
        
        return contains_template(source_img, template_img, threshold, method)
    
    def find_template(self,
                     template: cv2.typing.MatLike,
                     threshold: float = 0.8,
                     method: int = cv2.TM_CCOEFF_NORMED,
                     preprocess: bool = False) -> MatchResult:
        """
        テンプレートマッチングを実行し、結果を返す
        
        :param template: テンプレート画像
        :param threshold: マッチング閾値
        :param method: マッチング手法
        :param preprocess: 前処理を行うか
        :return: マッチング結果
        """
        source_img = self.image
        template_img = template
        
        if preprocess:
            source_img = self.preprocessor.enhance_for_template_matching(source_img)
            template_img = self.preprocessor.enhance_for_template_matching(template_img)
        
        return find_template(source_img, template_img, threshold, method)
    
    def get_text(self, 
                 language: str = 'ja',
                 region: Optional[Tuple[int, int, int, int]] = None,
                 preprocess: bool = True) -> str:
        """
        画像からテキストを認識し、最も信頼度の高い文字列を返す
        
        :param language: 認識言語 ('ja', 'en')
        :param region: 認識領域 (x, y, width, height) - 指定しない場合は全体
        :param preprocess: OCR用前処理を行うか
        :return: 認識されたテキスト（見つからない場合は空文字列）
        """
        # OCRプロセッサーの遅延初期化
        if self._ocr_processor is None or self._ocr_processor.language != language:
            self._ocr_processor = OCRProcessor(language=language)
        
        # 認識対象画像の決定
        target_image = self.image
        if region is not None:
            x, y, w, h = region
            target_image = self.image[y:y+h, x:x+w]
        
        # 前処理
        if preprocess:
            target_image = self.preprocessor.enhance_for_ocr(target_image)
        
        # OCR実行
        return self._ocr_processor.get_best_text(target_image)
    
    def get_digits(self, 
                   language: str = 'en',
                   region: Optional[Tuple[int, int, int, int]] = None,
                   preprocess: bool = True) -> str:
        """
        画像から数字のみを認識して返す
        
        :param language: 認識言語 ('ja', 'en')
        :param region: 認識領域 (x, y, width, height)
        :param preprocess: OCR用前処理を行うか
        :return: 認識された数字文字列
        """
        # OCRプロセッサーの遅延初期化
        if self._ocr_processor is None or self._ocr_processor.language != language:
            self._ocr_processor = OCRProcessor(language=language)
        
        # 認識対象画像の決定
        target_image = self.image
        if region is not None:
            x, y, w, h = region
            target_image = self.image[y:y+h, x:x+w]
        
        # 前処理
        if preprocess:
            target_image = self.preprocessor.enhance_for_ocr(target_image)
        
        # 数字抽出
        return self._ocr_processor.extract_digits(target_image)
    
    def find_text_region_with_template(self,
                                      template: cv2.typing.MatLike,
                                      roi_offset: Tuple[int, int, int, int] = (0, 0, 0, 0),
                                      language: str = 'ja',
                                      template_threshold: float = 0.8,
                                      preprocess: bool = True) -> str:
        """
        テンプレートマッチングでテキスト領域を特定し、OCR実行
        
        :param template: テンプレート画像
        :param roi_offset: マッチ位置からの相対オフセット (x_offset, y_offset, w_offset, h_offset)
        :param language: OCR認識言語
        :param template_threshold: テンプレートマッチングの閾値
        :param preprocess: 前処理を行うか
        :return: 認識されたテキスト
        """
        # テンプレートマッチング
        match = self.find_template(template, template_threshold, preprocess=preprocess)
        x, y, w, h = match.bounding_box
        
        # オフセット適用
        x_off, y_off, w_off, h_off = roi_offset
        roi = (x + x_off, y + y_off, w + w_off, h + h_off)
        
        # OCR実行
        return self.get_text(language, roi, preprocess)