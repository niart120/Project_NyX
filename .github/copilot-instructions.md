# Project NyX

## はじめに

ユーザとの対話は日本語で行うこと。

## 概要
NyX は、Nintendo Switch 向け自動化ツールの開発フレームワークです。PCに接続したキャプチャデバイスからゲーム画面を取得し、シリアル通信デバイスを介してコントローラー操作を自動化できます。

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

## プロジェクト構造

```
src/nyxpy/
  framework/     — フレームワーク本体 (MacroBase, Command, imgproc, ロガー等)
  gui/           — PySide6 GUI
  cli/           — CLI エントリポイント
macros/
  shared/        — マクロ間共通部品 (timer, image_utils, ocr_utils)
  {macro_name}/  — マクロパッケージ (macro.py, config.py, recognizer.py 等)
static/
  {macro_name}/  — 設定ファイル (settings.toml) ・画像リソース
tests/
  unit/          — 単体テスト
  gui/           — GUI テスト (pytest-qt)
  hardware/      — 実機必要テスト (@pytest.mark.realdevice)
  integration/   — 結合テスト
  perf/          — パフォーマンステスト
spec/macro/      — マクロ仕様書
```

**依存方向の制約:**
```
macros/xxx/  →  nyxpy.framework.*   OK
macros/xxx/  →  macros/shared/*     OK
macros/xxx/  →  macros/yyy/*        NG (マクロ間の直接依存禁止)
```

## コーディング規約

- 技術文書は事実ベース・簡潔に記述
- t_wada氏が推奨するテスト駆動開発(TDD)指針/コーディング指針を遵守
  - Code → How
  - Tests → What
  - Commits → Why
  - Comments → Why not

## 後方互換性ポリシー

- NyX のフレームワーク本体はアルファ版として扱う。再設計や cleanup では、設計の明確さと保守性を優先し、破壊的変更を許容する。
- レガシー API、互換 shim、旧 import path、旧設定経路は、ユーザから明示的に求められない限り移行期間を設けず削除する。
- 旧実装を残す場合は、後方互換性ではなく現行アーキテクチャ上の責務として必要な理由を仕様書またはコード上の変更説明に明記する。
- `DeprecationWarning` や alias を追加して段階廃止するより、呼び出し元・テスト・ドキュメントを同じ変更内で正 API へ更新する。

## Python コーディング規約

### 環境
- Python `>=3.12` / パッケージ管理は `uv`
- 依存追加: `uv add <pkg>` / dev 依存: `uv add --dev <pkg>`

### リント・フォーマット
- **ruff** を使用する（`pyproject.toml` の `[tool.ruff]` を参照）
- リント: `uv run ruff check .`
- フォーマット: `uv run ruff format .`

### 型ヒント
- Python 3.12+ のため、前方参照以外で `from __future__ import annotations` は不要
- モダン構文を使用する:
  - `X | None` — not `Optional[X]`
  - `list[X]` / `dict[K, V]` — not `List[X]` / `Dict[K, V]`
  - `tuple[int, str]` — not `Tuple[int, str]`
- ランタイムに不要な型インポートは `if TYPE_CHECKING:` ブロック内に置く

### テスト
- **pytest** を使用する
- 副作用のないロジック関数は `Command` なしで単体テスト可能にする
- 実機要件のテストには `@pytest.mark.realdevice` を指定する

## よく使うコマンド

```powershell
uv run nyx-gui                  # GUI 起動
uv run nyx-cli                  # CLI 起動
uv run pytest                   # 全テスト
uv run pytest tests/unit/       # 単体テストのみ
uv run ruff check .             # リント
uv run ruff format .            # フォーマット
```

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
