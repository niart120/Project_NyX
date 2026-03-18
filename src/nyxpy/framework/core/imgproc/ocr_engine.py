
import cv2
from typing import ClassVar, Dict, List
from dataclasses import dataclass
from threading import Lock

from .exceptions import OCREngineNotFoundError, OCRProcessingError


@dataclass
class OCRResult:
    """OCR認識結果"""
    text: str
    confidence: float


class OCRProcessor:
    """シンプルなOCR処理クラス

    通常のインスタンス生成 (``OCRProcessor(language)``) に加え、
    ``get_instance(language)`` で言語ごとにキャッシュされた
    シングルトンインスタンスを取得できる。
    PaddleOCR のモデルロード・初回推論コストを複数箇所で共有したい場合は
    ``get_instance`` の利用を推奨する。
    """

    _instances: ClassVar[Dict[str, "OCRProcessor"]] = {}
    _lock: ClassVar[Lock] = Lock()

    @classmethod
    def get_instance(cls, language: str = "ja") -> "OCRProcessor":
        """言語ごとにキャッシュされたインスタンスを返す。

        同じ ``language`` に対しては常に同一インスタンスが返される。
        スレッドセーフ。

        :param language: 認識言語 ('ja', 'en')
        :return: キャッシュ済みの OCRProcessor
        """
        if language not in cls._instances:
            with cls._lock:
                # ダブルチェックロッキング
                if language not in cls._instances:
                    cls._instances[language] = cls(language)
        return cls._instances[language]

    @classmethod
    def clear_cache(cls) -> None:
        """キャッシュを全クリアする (テスト用)。"""
        with cls._lock:
            cls._instances.clear()
    
    def __init__(self, language: str = 'ja'):
        """
        :param language: 認識言語 ('ja', 'en')
        """
        self.language = language
        self._ocr_engine = None
        self._init_engine()
    
    def _init_engine(self):
        """OCRエンジンの初期化"""
        try:
            from paddleocr import PaddleOCR
            # 言語マッピング
            lang_map = {'ja': 'japan', 'en': 'en'}
            paddle_lang = lang_map.get(self.language, 'japan')
            
            # PaddleOCRの初期化
            # NOTE: use_angle_cls / show_log は新版で廃止されたため使用しない
            # OCR.yaml のデフォルトはいずれも True のため、ゲーム画面用に
            # 向き分類をすべて無効化して固定する
            self._ocr_engine = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                lang=paddle_lang,
            )
        except ImportError:
            raise OCREngineNotFoundError("PaddleOCRがインストールされていません")
        except Exception as e:
            raise OCREngineNotFoundError(f"PaddleOCRの初期化に失敗しました: {e}")
    
    def recognize_text(self, image: cv2.typing.MatLike) -> List[OCRResult]:
        """
        テキスト認識実行
        
        :param image: 認識対象画像
        :return: 認識結果のリスト
        """
        if image is None or image.size == 0:
            return []
            
        try:
            # 呼び出し時にも向き分類を明示的に無効化する
            # (OCR.yaml デフォルトが True のため、コンストラクタ設定だけでは
            # predict() のキーワード引数で上書きされる可能性があるため)
            results = self._ocr_engine.predict(
                image,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )

            ocr_results = []
            if results:
                for item in results:
                    rec_texts = item.get('rec_texts', [])
                    rec_scores = item.get('rec_scores', [])
                    for text, score in zip(rec_texts, rec_scores):
                        ocr_results.append(OCRResult(text=text, confidence=score))
            
            return ocr_results
            
        except Exception as e:
            raise OCRProcessingError(f"OCR処理中にエラーが発生しました: {e}")
    
    def get_best_text(self, image: cv2.typing.MatLike) -> str:
        """
        最も信頼度の高いテキストを取得
        
        :param image: 認識対象画像
        :return: 最も信頼度の高いテキスト（見つからない場合は空文字列）
        """
        results = self.recognize_text(image)
        if results:
            best_result = max(results, key=lambda r: r.confidence)
            return best_result.text
        return ""
    
    def extract_digits(self, image: cv2.typing.MatLike) -> str:
        """
        画像から数字のみを認識して返す
        
        :param image: 認識対象画像
        :return: 認識された数字文字列
        """
        text = self.get_best_text(image)
        # 数字のみを抽出
        digits = ''.join(filter(str.isdigit, text))
        return digits
