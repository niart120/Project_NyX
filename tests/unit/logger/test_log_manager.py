import pytest
from loguru import logger
from framework.core.logger.log_manager import log_manager

@pytest.fixture(autouse=True)
def capture_logs():
    # すべてのロガーハンドラを一旦クリアし、一時的なシンク（出力先）を追加する。
    # ここではログメッセージをリストに格納するシンクを使用。
    captured_logs = []
    def sink(message):
        captured_logs.append(message.strip())
    logger.remove()  # 既存のハンドラをすべて削除
    logger.add(sink, level="DEBUG")  # DEBUG レベル以上のログをキャプチャするシンクを追加
    yield captured_logs
    # テスト終了後のクリーンアップ処理：一時的なシンクを削除し、他のテストに影響しないようにする。
    logger.remove()

def test_log_manager_console_logging(capture_logs):
    # log_manager.log が適切なフォーマットでログを出力することを確認するテスト。
    log_manager.log("INFO", "Test message", component="UnitTest")
    # キャプチャされたログのいずれかが "[UnitTest]" を含み、かつ "Test message" を含んでいることを検証。
    assert any("UnitTest" in msg and "Test message" in msg for msg in capture_logs)
    ## キャプチャされたログのいずれかが "INFO" レベルであることを確認。
    assert any("INFO" in msg for msg in capture_logs)
    # キャプチャされたログのいずれかが "Test message" を含んでいることを確認。
    assert any("Test message" in msg for msg in capture_logs)
    

def test_log_manager_set_level(capture_logs):
    # ログレベルを WARNING に設定し、DEBUG レベルのメッセージが出力されないことを確認する。
    log_manager.set_level("WARNING") #Fixme: 内部的にロガーハンドラを削除しているため、期待した動作をしない。
    log_manager.log("DEBUG", "This should NOT appear", component="UnitTest")  # このメッセージはキャプチャされないはず
    log_manager.log("WARNING", "This should appear", component="UnitTest")  # このメッセージはキャプチャされるはず
    # DEBUG レベルのメッセージがキャプチャされていないことを確認。
    assert not any("This should NOT appear" in msg for msg in capture_logs)
    # WARNING レベルのメッセージがキャプチャされていることを確認。
    assert any("This should appear" in msg for msg in capture_logs)
    # キャプチャされたログのいずれかが "WARNING" レベルであることを確認。
    assert any("WARNING" in msg for msg in capture_logs)

def test_log_manager_add_handler(capture_logs):
    # add_handler を使用してカスタムのシンク（出力先）を追加し、
    # そこにログが正しく送信されることを確認する。
    custom_logs = []
    def custom_sink(message):
        custom_logs.append(message.strip())
    log_manager.add_handler(custom_sink)  # カスタムシンクを追加
    log_manager.log("INFO", "Custom sink test", component="UnitTest")
    # キャプチャされたログのいずれかが "Custom sink test" を含んでいることを確認。
    assert any("Custom sink test" in msg for msg in capture_logs)
    # カスタムシンクに送信されたログのいずれかが "Custom sink test" を含んでいることを確認。
    assert any("Custom sink test" in msg for msg in custom_logs)
    # キャプチャされたログのいずれかが "UnitTest" を含んでいることを確認。
    assert any("UnitTest" in msg for msg in capture_logs)
    
