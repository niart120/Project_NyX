from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .command import Command

if TYPE_CHECKING:
    from nyxpy.framework.core.settings.schema import SettingsSchema


class MacroBase(ABC):
    # GUI 用メタデータ: マクロの説明文とタグ
    description: str = ""
    tags: list[str] = []
    args_schema: "SettingsSchema | None" = None

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
