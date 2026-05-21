---
name: macro-development
description: "Project NyX のマクロ実装・修正・レビューを行うスキル。USE WHEN: ユーザが「マクロを作って」「マクロを直して」「macros/ 配下を実装」「resources/ の設定を追加」「NyX の MacroBase / Command を使う」「examples/macros を参考にしたい」など、Nintendo Switch 自動化マクロのコード・設定・テストを扱う意図を示したとき。仕様書だけを書く場合は macro-spec-writing を使う。"
argument-hint: "[macro_id または作業内容]"
---

# NyX マクロ開発スキル

Project NyX のマクロを、リポジトリ規約と現行フレームワーク API に沿って実装・修正・レビューします。

## 最初に読むもの

リポジトリ内で作業している場合:

1. `docs\macro-development\agent-brief.md`
2. `docs\macro-development\README.md`
3. 必要に応じて `docs\macro-development\macro-template.md`

このスキルだけを外部エージェントに渡す場合は、同じ文書を raw URL から取得します。

```text
https://raw.githubusercontent.com/niart120/Project_NyX/main/docs/macro-development/agent-brief.md
https://raw.githubusercontent.com/niart120/Project_NyX/main/docs/macro-development/README.md
https://raw.githubusercontent.com/niart120/Project_NyX/main/docs/macro-development/macro-template.md
```

Phase 2 の詳細ページが未作成の間は、上記 3 文書、現行コード、既存 examples、テストを根拠にします。`spec\framework\rearchitecture` は移行元の参考資料であり、公開契約の正本として扱いません。

## 対象

- `macros\<macro_id>` のマクロ本体
- `resources\<macro_id>` の設定ファイルと画像資材
- `examples\macros`, `examples\resources`, `examples\tests` の公開サンプル
- 副作用のない設定変換・乱数計算・画像判定ロジックとそのテスト

仕様書だけを作成・レビューする場合は `macro-spec-writing` を使います。フレームワーク本体 (`src\nyxpy\framework`) の API 変更や仕様書には `framework-spec-writing` を使います。

## 実装手順

1. `agent-brief.md` を読み、配置・依存・公開 API・検証コマンドを確認します。
2. 既存マクロや examples から、入力・画像処理・乱数計算・通知の近い実装を探します。
3. マクロ本体は `MacroBase` の `initialize(cmd, args)`, `run(cmd)`, `finalize(cmd)` に分けます。
4. 設定値の変換や判定ロジックは `config.py` や独立関数へ分離し、`Command` なしでテストします。
5. 設定ファイルは `resources\<macro_id>\settings.toml` に置き、マクロ側は `settings_path = "resource:settings.toml"` を標準にします。
6. 画像資材は `resources\<macro_id>\assets` に置き、`cmd.load_img()` では資材ディレクトリからの相対パスを使います。
7. `cmd.capture()` の結果は `None` を確認してから shape 参照・画像処理・保存を行います。
8. 必要なテストを追加し、ruff と pytest で確認します。

## 依存方向

```text
macros\xxx           -> nyxpy.framework.*       OK
macros\xxx           -> macros\shared           OK
macros\xxx           -> macros\yyy              NG
examples\macros\xxx  -> examples\macros\shared  OK
examples\macros\xxx  -> examples\macros\yyy     NG
```

複数マクロで使う処理は共有部品に切り出します。共有部品はできるだけ `Command` に依存させず、引数と戻り値でやり取りします。

## パスと設定

- Windows のファイル表示や説明では `\` を使います。
- `macro.toml` や設定ファイルに保存する移植可能パスは `/` を使います。
- `resource:` パスは `resources\<macro_id>` からの相対指定にします。
- `project:` パスはプロジェクトルートからの相対指定にします。
- 旧 `static\<macro_name>` は標準探索されません。

## 完了条件

- `macros\<macro_id>` と `resources\<macro_id>` の対応が取れている。
- `macro.py` または `__init__.py` のどちらか一方に、そのファイルで定義した `MacroBase` 派生クラスが 1 つだけある。
- `cmd.capture()` の `None` を処理している。
- `finalize()` で押下状態の解放など必要な後片付けをしている。
- 副作用のないロジックに単体テストがある。
- PowerShell で次を実行し、変更範囲に応じて成功を確認している。

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest tests macros examples/tests
```

