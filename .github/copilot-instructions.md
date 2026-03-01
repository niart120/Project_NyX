# Project NyX

## はじめに

ユーザとの対話は日本語で行うこと。

### 主な機能
- PySide6を使用したGUIインターフェース
- コマンドライン(CLI)インターフェース  
- マクロの実行・管理
- リアルタイム画面プレビュー
- スナップショット機能
- 統合ログ管理システム (LogManager)
- キャプチャデバイス・シリアルデバイスの設定
- 外部通知システム (Discord, Bluesky)
- 設定の永続化 (.nyxpy/)

### 必要なハードウェア
- **キャプチャデバイス**: Nintendo Switchの画面を取得するためのキャプチャカード/ボード
- **シリアル通信デバイス**: CH552プロトコルをサポートするコントロール送信デバイス

## コーディング規約

- 技術文書は事実ベース・簡潔に記述
- t_wada氏が推奨するテスト駆動開発(TDD)指針/コーディング指針を遵守
  - Code → How
  - Tests → What
  - Commits → Why
  - Comments → Why not

## よく使うコマンド


## コミットルール

- [Conventional Commits](https://www.conventionalcommits.org/) に準拠する
- フォーマット: `<type>(<scope>): <subject>`
  - `<scope>` は省略可
- 許可される type:
  - `feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert`
- subject は日本語で記述・末尾句点なし

## シェルの前提

- コマンド例は **PowerShell（pwsh）構文**で書くこと。
- **bash / zsh / sh 前提のコマンドは出さない**（例: `export`, `VAR=value cmd`, `&&` 連結前提、`sed -i`, `cp -r`, `rm -rf` などのUnix系定番をそのまま出さない）。
- Windows 組み込みコマンドでも良いが、基本は **PowerShell のコマンドレット**を優先する。
