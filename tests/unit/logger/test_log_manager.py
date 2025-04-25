import pytest
from loguru import logger
from nyxpy.framework.core.logger.log_manager import LogManager


class TestLogManager:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        # テストごとに新しい LogManager のインスタンスを生成する
        self.log_manager = LogManager()
        # カスタムハンドラのログ収集先リスト
        self.log_records = []
        yield
        # テスト後に loguru のハンドラをすべて削除してクリーンアップ
        logger.remove()

    def handler(self, record):
        self.log_records.append(record)

    def dummy_handler(self, record):
        pass

    def test_log_method(self):
        # カスタムハンドラを追加して log() メソッドの出力を検証する
        self.log_manager.add_handler(self.handler, level="DEBUG")
        # ログメッセージを記録
        self.log_manager.log("DEBUG", "debug message", "UnitTest")

        # ハンドラによりメッセージが記録されることを検証
        assert len(self.log_records) == 1
        assert any(
            "debug message" in msg and "UnitTest" in msg for msg in self.log_records
        )

    def test_set_level_changes_all_handlers(self):
        # カスタムハンドラを追加してログレベル設定の変更を検証
        self.log_manager.add_handler(self.handler, level="DEBUG")
        # すべてのハンドラのレベルを INFO に変更
        self.log_manager.set_level("INFO")
        # DEBUG レベルのメッセージは出力されないはず
        self.log_manager.log("DEBUG", "デバッグメッセージ", "UnitTest")
        self.log_manager.log("INFO", "情報メッセージ", "UnitTest")
        # INFO レベルのメッセージは出力されるはず
        assert not any("デバッグメッセージ" in m for m in self.log_records)
        assert any("情報メッセージ" in m for m in self.log_records)

    def test_set_custom_handler_level_error(self):
        # 未登録のハンドラに対して例外が発生するか検証

        # カスタムハンドラを追加
        with pytest.raises(ValueError) as exc_info:
            self.log_manager.set_custom_handler_level(self.dummy_handler, "INFO")
        assert "指定されたハンドラは登録されていません" in str(exc_info.value)

    def test_remove_handler(self):
        # カスタムハンドラの削除動作を検証

        # ハンドラを追加
        self.log_manager.add_handler(self.handler, level="DEBUG")
        # 追加後、メッセージがキャプチャできることを確認
        self.log_manager.log("DEBUG", "初回メッセージ", "UnitTest")
        assert any("初回メッセージ" in msg for msg in self.log_records)
        # キャプチャしたログをクリアし、ハンドラを削除
        self.log_records.clear()
        self.log_manager.remove_handler(self.handler)
        self.log_manager.log("DEBUG", "削除後メッセージ", "UnitTest")
        # 削除後はハンドラが動作しないので、ログは記録されないはず
        assert not self.log_records
