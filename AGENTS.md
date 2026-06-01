# Project NyX Agent Guide

ユーザとの対話は日本語で行うこと。

## 概要

NyX は、Nintendo Switch 向け自動化ツールの開発フレームワークです。PC に接続したキャプチャデバイスからゲーム画面を取得し、シリアル通信デバイス経由でコントローラー操作を自動化します。GUI、CLI、マクロ API、ログ、実行成果物保存を提供します。

## Agent Skills

Project NyX の agent skill は `.agents/skills` を正本として管理します。`.github/skills` には重複配置しません。Windows 環境を想定し、symlink 前提の配置は使いません。

## プロジェクト構造

```text
src/nyxpy/
  __main__.py    - `nyxpy` console script の入口
  py.typed       - PEP 561 の型情報 marker
  framework/
    core/
      constants/ - ボタン・座標・画面サイズなどの定数
      hardware/  - キャプチャ、シリアル、プロトコル、デバイス探索
      imgproc/   - 画像処理・OCR
      io/        - runtime port、resource store、artifact store
      logger/    - ログ event、dispatcher、sink、backend
      macro/     - MacroBase、Command、registry、scaffold
      notifications/ - Discord / Bluesky などの外部通知 adapter
      runtime/   - runtime builder、runner、execution context
      settings/  - workspace/global/secrets 設定
  gui/           - PySide6 GUI
  cli/           - `nyxpy run` の CLI 実装
  templates/     - `nyxpy create` 用 scaffold template
macros/
  {macro_id}/    - ローカル作業用マクロ。Git 管理外だが pytest 対象
resources/
  {macro_id}/    - ローカル作業用リソース。Git 管理外
docs/            - GitHub Pages で公開する利用者・マクロ開発者・API docs
examples/
  macros/        - 公開用マクロ本体
    shared/      - 公開用マクロ間共通部品
    {macro_id}/  - 公開用マクロパッケージ
  resources/     - 公開用マクロの設定ファイル・画像リソース
  tests/         - 公開用マクロの単体・性能テスト
tests/
  unit/          - 単体テスト
  gui/           - GUI テスト (pytest-qt)
  hardware/      - 実機必要テスト (@pytest.mark.realdevice)
  integration/   - 結合テスト
  perf/          - パフォーマンステスト
spec/
  macro/         - マクロ仕様書
  framework/     - フレームワーク再設計・詳細仕様
  docs/          - ドキュメント整備仕様
  agent/         - エージェント向け作業仕様・完了記録
.agents/skills/  - agent skill の正本
```

## 依存方向

```text
macros/xxx/           -> nyxpy.framework.*           OK
macros/xxx/           -> macros/shared/*             OK
macros/xxx/           -> macros/yyy/*                NG
examples/macros/xxx/  -> nyxpy.framework.*           OK
examples/macros/xxx/  -> examples/macros/shared/*    OK
examples/macros/xxx/  -> examples/macros/yyy/*       NG
```

マクロパッケージ同士は直接 import しません。複数マクロで使う処理は共有部品へ切り出します。

## コーディング規約

- 技術文書は事実ベース・簡潔に記述します。
- t_wada 氏の TDD 指針を意識します。
- Code は How、Tests は What、Commits は Why、Comments は Why not を担います。
- コメントは、コードだけでは読み取りにくい判断理由がある場合に限って追加します。

## 後方互換性ポリシー

- NyX のフレームワーク本体はアルファ版として扱います。再設計や cleanup では、設計の明確さと保守性を優先し、破壊的変更を許容します。
- レガシー API、互換 shim、旧 import path、旧設定経路は、ユーザから明示的に求められない限り移行期間を設けず削除します。
- 旧実装を残す場合は、後方互換性ではなく現行アーキテクチャ上の責務として必要な理由を仕様書またはコード上の変更説明に明記します。
- `DeprecationWarning` や alias を追加して段階廃止するより、呼び出し元・テスト・ドキュメントを同じ変更内で正 API へ更新します。

## Python

- Python `>=3.12` を使います。
- パッケージ管理と Python 実行は `uv` 経由に統一します。
- Python スクリプトは `python ...` ではなく `uv run python ...` で実行します。
- 依存追加は `uv add <pkg>`、dev 依存は `uv add --dev <pkg>` を使います。
- 型注釈は Python 3.12+ の構文を使います。
  - `X | None`
  - `list[X]` / `dict[K, V]`
  - `tuple[int, str]`
- `from __future__ import annotations` は、実行時評価を遅延する必要がある場合だけ使います。
- ランタイムに不要な型 import は `if TYPE_CHECKING:` に置きます。

## テストと検証

- lint は `ruff`、テストは `pytest` を使います。
- 副作用のないロジック関数は `Command` なしで単体テスト可能にします。
- 実機要件のテストには `@pytest.mark.realdevice` を指定します。
- 変更範囲に応じて、ruff、ty、pytest を実行します。

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest
```

よく使う個別コマンド:

```console
uv run nyxpy gui
uv run nyxpy run <macro_id>
uv run pytest tests/unit/
uv run vulture src tests examples macros --min-confidence 80
```

`nyx-cli` は `nyxpy run`、`nyx-gui` は `nyxpy gui` の alias として扱います。

## コミットルール

Conventional Commits に準拠します。

```text
<type>(<scope>): <subject>
```

`scope` は省略可です。type は `feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert` を使います。subject は日本語で記述し、末尾句点は付けません。
