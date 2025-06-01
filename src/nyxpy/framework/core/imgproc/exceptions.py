# filepath: e:\documents\VSCodeWorkspace\Project_NyX\src\nyxpy\framework\core\imgproc\exceptions.py

class ImageProcessingError(Exception):
    """画像処理に関連するエラーの基底クラス"""
    pass


class TemplateMatchingError(ImageProcessingError):
    """テンプレートマッチング処理でのエラー"""
    pass


class OCRError(ImageProcessingError):
    """OCR処理でのエラー"""
    pass


class InvalidImageError(ImageProcessingError):
    """無効な画像データエラー"""
    pass


class ThresholdNotMetError(ImageProcessingError):
    """閾値を満たさないエラー"""
    pass


class OCREngineNotFoundError(OCRError):
    """OCRエンジンが見つからないエラー"""
    pass


class OCRProcessingError(OCRError):
    """OCR処理中のエラー"""
    pass
