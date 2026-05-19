# ツール利用者向け手順書整備 作業計画仕様書

> **文書種別**: 作業計画仕様。NyX を GUI/CLI で利用する人向けの手順書を整備するための方針と作業単位を定義する。
> **対象領域**: `README.md`, `docs\user-guide\`, `docs\assets\`
> **目的**: インストール、初回設定、GUI/CLI 実行、通知設定、トラブル対応を読者の操作順に整理する。
> **関連ドキュメント**: `README.md`, `spec/docs/MACRO_DEVELOPMENT_DOCUMENTATION_PLAN.md`, `spec/framework/rearchitecture/OBSERVABILITY_AND_GUI_CLI.md`

## 1. 概要

### 1.1 対象読者

NyX を使って既存マクロを実行するユーザを対象にする。Python の実装知識は前提にしない。必要な操作は PowerShell コマンド、GUI 操作、設定ファイル編集として説明する。

### 1.2 整理方針

README はプロジェクト概要と最短起動手順だけを持つ。詳細手順は `docs\user-guide\` に集約し、内部クラス名や Runtime / Port / Adapter などの設計用語は使わない。

## 2. 目標構成

| 文書 | 内容 | 主な移設元 |
|------|------|------------|
| `docs\user-guide\README.md` | 利用者向け目次、想定環境、最短手順 | `README.md` |
| `docs\user-guide\installation.md` | Python / uv / `uv tool install` / リポジトリ取得 / 起動確認 | `README.md` 2章 |
| `docs\user-guide\device-setup.md` | キャプチャデバイス、シリアルデバイス、プロトコル、初回設定 | `README.md` 3章・5章 |
| `docs\user-guide\gui.md` | GUI 起動、マクロ選択、実行、中断、プレビュー、スナップショット | `README.md` 3章 |
| `docs\user-guide\cli.md` | CLI 実行、主要オプション、`--define`、終了時の見方 | `README.md` 3章 |
| `docs\user-guide\notifications.md` | Discord / Bluesky 通知の設定と秘密情報の扱い | `README.md` 3章・5章 |
| `docs\user-guide\troubleshooting.md` | デバイス未検出、プレビュー不可、シリアル送信不可、ログ確認 | `README.md` 6章 |

## 3. 正本ルール

| 情報 | 正本 | 参照側の扱い |
|------|------|--------------|
| プロジェクト概要と最短起動 | `README.md` | 詳細手順へのリンクを置く |
| GUI/CLI の利用手順 | `docs\user-guide\` | README には短い例だけを置く |
| スクリーンショット等の画像 | `docs\assets\` | README と user guide から共通参照する |
| GUI/CLI の内部設計 | `spec\framework\rearchitecture\OBSERVABILITY_AND_GUI_CLI.md` | 利用者向け docs では再定義しない |

## 4. 執筆ルール

- PowerShell コマンド例を使う。
- Windows の実ファイル配置例は `\` を使う。
- 手順は実行順に書き、成功時に何が見えるかを示す。
- エラー対応は、症状、確認箇所、対処、ログ確認先の順で書く。
- Python クラス名や内部設計用語は、利用者が操作判断に使う場合だけ短く説明する。

## 5. 作業計画

### Phase 0: 現状棚卸し

| 作業 | 成果物 |
|------|--------|
| README の利用者向け節を抽出する | README 移設対応表 |
| 現行 GUI/CLI で利用者が触る設定項目を確認する | user guide 文書一覧の確定 |

### Phase 1: ナビゲーション整備

| 作業 | 成果物 |
|------|--------|
| `docs\user-guide\README.md` を作る | 利用者向け目次 |
| README を短くし、詳細文書へリンクする | README 改訂 |

### Phase 2: 手順書の整備

| 作業 | 成果物 |
|------|--------|
| インストールと初回起動を分離する | `installation.md` |
| デバイス設定を独立させる | `device-setup.md` |
| GUI と CLI の操作を分ける | `gui.md`, `cli.md` |
| 通知とトラブルシューティングを分ける | `notifications.md`, `troubleshooting.md` |

`installation.md` では、`uv tool install` をツール利用の主導線にする。ただし、マクロが NyX に含まれない外部ライブラリを import する場合は tool の隔離環境にもその依存が必要になるため、マクロ配布側の要件確認と、マクロ開発者向け手順へのリンクを置く。

### Phase 3: 重複削減とリンク検証

| 作業 | 成果物 |
|------|--------|
| README から詳細説明を削り、リンクへ置換する | README の重複削減 |
| docs から内部仕様の再定義を削る | docs と spec の責務分離 |
| 主要リンクとパス表記を確認する | リンク・表記の修正差分 |

## 6. 受け入れ条件

- README だけを読めば、利用者が次に読む手順書へ移動できる。
- 利用者向け手順は `docs\user-guide\` に集約されている。
- 利用者向け docs は内部設計仕様を再定義していない。
- PowerShell コマンド例と Windows パス例の表記が混在していない。

## 7. 未決事項

| 論点 | 判断候補 | ドラフト上の仮置き |
|------|----------|--------------------|
| 利用者向け docs の公開方法 | GitHub Pages / README からの相対リンクのみ | GitHub Pages に統一 |
| GUI 操作説明に画像をどこまで入れるか | 必須画面だけ / 全操作に画像 | 必須画面だけ |
