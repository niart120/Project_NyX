
"""
画像処理モジュール

このモジュールは、OpenCVの画像形式オブジェクトを受け取って
テンプレートマッチングとOCR処理を行うためのシンプルなAPIを提供します。
"""

__version__ = "0.1.0"

# 主要クラスと関数のインポート
from .processor import ImageProcessor
from .template_matcher import find_template, contains_template, MatchResult
from .ocr_engine import OCRProcessor, OCRResult
from .utils import ImagePreprocessor
from .exceptions import (
    ImageProcessingError,
    TemplateMatchingError,
    OCRError,
    InvalidImageError,
    ThresholdNotMetError,
    OCREngineNotFoundError,
    OCRProcessingError
)

__all__ = [
    # メインクラス
    'ImageProcessor',
    
    # テンプレートマッチング関数
    'find_template',
    'contains_template',
    'MatchResult',
    
    # OCR関連
    'OCRProcessor',
    'OCRResult',
    
    # ユーティリティ
    'ImagePreprocessor',
    
    # 例外クラス
    'ImageProcessingError',
    'TemplateMatchingError',
    'OCRError',
    'InvalidImageError',
    'ThresholdNotMetError',
    'OCREngineNotFoundError',
    'OCRProcessingError'
]