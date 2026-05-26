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
  __main__.py    — `nyxpy` console script の入口
  py.typed       — PEP 561 の型情報 marker
  framework/
    core/
      api/       — 外部通知 API
      constants/ — ボタン・座標・画面サイズなどの定数
      hardware/  — キャプチャ、シリアル、プロトコル、デバイス探索
      imgproc/   — 画像処理・OCR
      io/        — runtime port、resource store、artifact store
      logger/    — ログ event、dispatcher、sink、backend
      macro/     — MacroBase、Command、registry、scaffold
      runtime/   — runtime builder、runner、execution context
      settings/  — workspace/global/secrets 設定
  gui/           — PySide6 GUI
  cli/           — `nyxpy run` の CLI 実装
  templates/     — `nyxpy create` 用 scaffold template
macros/
  {macro_id}/    — ローカル作業用マクロ。Git 管理外だが pytest 対象
resources/
  {macro_id}/    — ローカル作業用リソース。Git 管理外
docs/             — GitHub Pages で公開する利用者・マクロ開発者・API docs
examples/
  macros/        — 公開用マクロ本体
    shared/      — 公開用マクロ間共通部品
    {macro_id}/  — 公開用マクロパッケージ
  resources/     — 公開用マクロの設定ファイル・画像リソース
  tests/         — 公開用マクロの単体・性能テスト
tests/
  unit/          — 単体テスト
  gui/           — GUI テスト (pytest-qt)
  hardware/      — 実機必要テスト (@pytest.mark.realdevice)
  integration/   — 結合テスト
  perf/          — パフォーマンステスト
spec/
  macro/         — マクロ仕様書
  framework/     — フレームワーク再設計・詳細仕様
  docs/          — ドキュメント整備仕様
  agent/         — エージェント向け作業仕様・完了記録
```

**依存方向の制約:**
```
macros/xxx/           →  nyxpy.framework.*           OK
macros/xxx/           →  macros/shared/*             OK
macros/xxx/           →  macros/yyy/*                NG (マクロ間の直接依存禁止)
examples/macros/xxx/  →  nyxpy.framework.*           OK
examples/macros/xxx/  →  examples/macros/shared/*    OK
examples/macros/xxx/  →  examples/macros/yyy/*       NG (マクロ間の直接依存禁止)
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
- Python 3.12+ のため、`TYPE_CHECKING` 配下の型や未定義名を注釈で参照する場合など、実行時評価を遅延する必要がある場合だけ `from __future__ import annotations` を使う
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

```console
uv run nyxpy gui                # GUI 起動
uv run nyxpy run <macro_id>     # CLI でマクロ実行
uv run pytest                   # 全テスト
uv run pytest tests/unit/       # 単体テストのみ
uv run ruff check .             # リント
uv run ruff format .            # フォーマット
uv run ty check src/nyxpy --output-format concise --no-progress  # 型チェック
uv run vulture src tests examples macros --min-confidence 80      # 未使用コード候補の検出
```

`nyx-cli` は `nyxpy run`、`nyx-gui` は `nyxpy gui` の alias として扱う。

## コミットルール

- [Conventional Commits](https://www.conventionalcommits.org/) に準拠する
- フォーマット: `<type>(<scope>): <subject>`
  - `<scope>` は省略可
- 許可される type:
  - `feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert`
- subject は日本語で記述・末尾句点なし
