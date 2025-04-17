from abc import ABC, abstractmethod
from .command import Command

class MacroBase(ABC):
    # GUI 用メタデータ: マクロの説明文とタグ
    description: str = ""
    tags: list[str] = []

    @abstractmethod
    def initialize(self, cmd: Command, args: dict) -> None:
        """
        マクロ実行前の初期化処理を実装する。
        """
        pass

    @abstractmethod
    def run(self, cmd: Command) -> None:
        """
        マクロのメイン処理を実装する。
        """
        pass

    @abstractmethod
    def finalize(self, cmd: Command) -> None:
        """
        マクロ実行後のクリーンアップ処理を実装する。
        """
        pass
