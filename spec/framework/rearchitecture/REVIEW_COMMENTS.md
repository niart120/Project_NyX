# フレームワーク再設計ドキュメント 残レビューコメント

> **対象**: `spec\framework\rearchitecture\*.md`  
> **観点**: `framework-spec-writing` の必須構成、公開 API の一貫性、依存方向、後方互換性、スレッド安全性、テストゲート、移行可能性

## 1. 総評

再設計ドキュメント群に対する機械的な整合修正は反映済みである。本ファイルには、公開 API の意味論や実装方針の選択を伴うためユーザー判断が必要なコメントだけを残す。

## 2. 判断待ち

### J-01 概要の未決事項と詳細仕様の確定記述が衝突している

- **対象**: `FW_REARCHITECTURE_OVERVIEW.md:278-285`, `ERROR_CANCELLATION_LOGGING.md:376-384`, `DEPRECATION_AND_MIGRATION.md:165`
- **問題**: Overview では `DefaultCommand.stop()` の例外送出、`MacroDefinition` の class 参照保持、singleton の runtime 登録が未決である。一方で、詳細仕様では `Command.stop(raise_immediately=False)` を既定にし、即時例外送出を廃止候補として扱っている。
- **影響**: 実装者が Overview と詳細仕様のどちらを正とするか判断できない。キャンセル互換の挙動は既存マクロの破壊範囲に直結する。
- **判断事項**: `DefaultCommand.stop()` の既定挙動、`MacroDefinition` の class 参照保持、singleton の runtime 登録方針を確定する。

### J-02 `cleanup_warnings` の文字列形式が後続処理に弱い

- **対象**: `RUNTIME_AND_IO_PORTS.md:618`, `RUNTIME_AND_IO_PORTS.md:325-326`
- **問題**: Port close 失敗を `"<port_name>: <ExceptionType>: <message>"` の文字列で保持する設計である。
- **影響**: message に `:` が含まれると機械的な解析が難しい。GUI/CLI 表示やログ構造化の際に再パースが必要になる。
- **判断事項**: `cleanup_warnings` を現行の `tuple[str, ...]` のまま維持するか、`CleanupWarning` dataclass などの構造化型へ変更するかを決める。
