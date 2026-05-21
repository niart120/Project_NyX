"""画像処理 API の例外型。"""

# filepath: e:\documents\VSCodeWorkspace\Project_NyX\src\nyxpy\framework\core\imgproc\exceptions.py


class ImageProcessingError(Exception):
    """画像処理に関連するエラーの基底クラス。"""

    pass


class TemplateMatchingError(ImageProcessingError):
    """テンプレートマッチング処理でのエラー。"""

    pass


class OCRError(ImageProcessingError):
    """OCR 処理でのエラー。"""

    pass


class InvalidImageError(ImageProcessingError):
    """無効な画像データを受け取った場合のエラー。"""

    pass


class ThresholdNotMetError(ImageProcessingError):
    """テンプレートマッチング結果が閾値を満たさない場合のエラー。"""

    pass


class OCREngineNotFoundError(OCRError):
    """OCR エンジンを初期化できない場合のエラー。"""

    pass


class OCRProcessingError(OCRError):
    """OCR 処理中のエラー。"""

    pass
