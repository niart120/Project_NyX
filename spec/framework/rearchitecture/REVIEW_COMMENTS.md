# フレームワーク再設計ドキュメント レビューコメント

> **対象**: `spec\framework\rearchitecture\*.md`  
> **観点**: フレームワーク仕様書テンプレート、依存方向、後方互換性、実装可能性、テスト可能性、文書間整合性

## 1. 総評

再設計の分割方針、互換ゲート、Ports/Adapters 化、GUI/CLI 移行の方向性は具体化されている。レビューで指摘した文書間の正本、型、責務、イベント名の曖昧さは対応済みである。

`MacroExecutor` の削除方針、マクロメタデータ型の整理、`ExecutionContext` / `RunResult` / `RunLogContext` の所有文書、キャンセル API、ログ event / error code、settings と Resource File I/O の責務境界は仕様へ反映済みである。

## 2. 全体指摘

全体指摘は対応済み。

## 3. ファイル別指摘

全件対応済み。

## 4. 実装前に完了させるべき最小修正

全件対応済み。
