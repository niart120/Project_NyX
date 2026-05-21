"""マクロ実装の基底 class。"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .command import Command

if TYPE_CHECKING:
    from nyxpy.framework.core.settings.schema import SettingsSchema


class MacroBase(ABC):
    """NyX マクロの基底クラス。

    サブクラスは `initialize()`, `run()`, `finalize()` を実装します。
    `description` と `tags` は一覧表示や検索に使うメタデータです。
    `args_schema` に `SettingsSchema` を指定すると、実行引数は
    `initialize()` に渡る前に検証されます。
    """

    description: str = ""
    """一覧表示向けの短い説明文。"""

    tags: list[str] = []
    """検索・分類用のタグ。"""

    args_schema: "SettingsSchema | None" = None
    """実行引数を検証する schema。未指定の場合は raw args が渡ります。"""

    @abstractmethod
    def initialize(self, cmd: Command, args: dict) -> None:
        """マクロ実行前の初期化処理を実装します。

        設定値の変換、画像資材の読み込み、実行状態の初期化を行います。
        `args_schema` が設定されている場合、`args` は検証済みの辞書です。
        """
        pass

    @abstractmethod
    def run(self, cmd: Command) -> None:
        """マクロの本処理を実装します。

        コントローラー操作、待機、キャプチャ、通知、ログは `cmd` 経由で行います。
        """
        pass

    @abstractmethod
    def finalize(self, cmd: Command) -> None:
        """マクロ実行後の後片付けを実装します。

        押下状態の解除や終了ログなど、失敗時にも安全に実行できる処理を置きます。
        """
        pass
