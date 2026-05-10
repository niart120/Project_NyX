---
name: framework-spec-writing
description: "フレームワーク本体 (src/nyxpy/framework/) の仕様書を新規作成・レビュー・修正するスキル。Use when: ユーザが「フレームワークの仕様書」「framework spec」「コア機能の設計書」「Command / MacroBase / imgproc / logger 等の仕様」と言ったとき、または spec/agent/ 配下でフレームワーク関連の Markdown を扱うとき。フレームワーク層の公開 API・内部設計・テスト方針を所定フォーマットで執筆する。マクロ (macros/) の仕様書には macro-spec-writing スキルを使うこと。"
argument-hint: "[モジュール名またはファイルパス] [new|review|fix]"
---

# フレームワーク仕様書執筆スキル

Project NyX のフレームワーク本体 (`src/nyxpy/framework/`) に対する仕様書を、リポジトリ規約に従って執筆・レビュー・修正するためのスキル。

## いつ使うか

- フレームワークの新機能・リファクタリングの仕様書を作成するとき
- 既存フレームワーク仕様書のレビュー・修正を行うとき
- `spec/agent/` 配下でフレームワーク関連の Markdown を編集するとき
- `src/nyxpy/framework/` のモジュール設計を文書化するとき

## 対象外（macro-spec-writing を使うべきケース）

- `macros/` 配下のマクロパッケージの仕様書
- `macros/shared/` 共通部品の仕様書（ただし共通部品がフレームワーク層に昇格する場合は本スキル）

## ディレクトリ規約

### 新規執筆（spec/agent/ 経由）

```
spec/agent/wip/local_{連番}/FEATURE_NAME.md    # 着手中
spec/agent/complete/local_{連番}/FEATURE_NAME.md  # 完了済み
```

- ファイル名は **大文字スネークケース**（例: `CAPTURE_PIPELINE.md`, `LOG_MANAGER_V2.md`）
- 完了後は `wip` → `complete` にディレクトリ移動

### 永続化（spec/ 配下）

機能が安定したら以下にも配置を検討する:

```
spec/framework/{module_name}/spec.md        # メイン仕様書
spec/framework/{module_name}/補助ドキュメント.md  # 補足（任意）
```

- `{module_name}` は `src/nyxpy/framework/core/` 配下のパッケージ名と対応させる
  - 例: `macro`, `hardware`, `imgproc`, `logger`, `settings`, `api`, `utils`

## 必須セクション構成

以下の 6 セクションを **必ず** 含める。

```markdown
# {機能名} 仕様書

## 1. 概要
### 1.1 目的
### 1.2 用語定義
### 1.3 背景・問題
### 1.4 期待効果
### 1.5 着手条件

## 2. 対象ファイル
| ファイル | 変更種別 | 変更内容 |

## 3. 設計方針

## 4. 実装仕様

## 5. テスト方針

## 6. 実装チェックリスト
```

## 各セクションの記述規約

### 1. 概要

#### 1.1 目的
1〜3 文で機能の目的を明記。フレームワーク層の責務を明確にする。

#### 1.2 用語定義
**表形式で統一。** フレームワーク仕様で頻出する用語例:

| 用語 | 定義 |
|------|------|
| Command | マクロがハードウェア操作（ボタン入力・キャプチャ・ログ）を行うための高レベル API |
| MacroBase | ユーザ定義マクロの抽象基底クラス。`initialize` / `run` / `finalize` ライフサイクルを持つ |
| CancellationToken | スレッドセーフなマクロ中断メカニズム |
| ImageProcessor | テンプレートマッチング・OCR を統合した画像処理ファサード |
| LogManager | loguru ベースの統合ログ管理シングルトン |
| SerialProtocolInterface | シリアル通信プロトコルの抽象インターフェース |
| CaptureDeviceInterface | キャプチャデバイスの抽象インターフェース |

マクロ固有の用語（frame, advance 等）や、新機能固有の用語があれば追加する。

#### 1.3 背景・問題
現状の課題やリファクタリング動機を簡潔に記述する。

#### 1.4 期待効果
**表形式で定量的に記載。**

| 指標 | 現状 | 目標 |
|------|------|------|
| API 呼び出し回数 | ── | ── |
| テストカバレッジ | ── | ── |

定量化が困難な場合は定性的な記述でも可とするが、測定可能な基準を優先する。

#### 1.5 着手条件
- 前提となる他の仕様や機能を列挙する
- 既存テストが通ること、など

### 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/xxx/yyy.py` | 新規 | ── |
| `tests/unit/test_xxx.py` | 新規 | ── |

変更種別は `新規` / `変更` / `削除` のいずれか。

### 3. 設計方針

以下を必要に応じて含める:

- **アーキテクチャ上の位置づけ**: 変更対象が全体アーキテクチャのどこに位置するか
- **公開 API 方針**: 新規 API の合理性、既存 API との整合性
- **後方互換性**: 破壊的変更の有無と移行計画
- **レイヤー構成**: モジュール分割方針、依存方向
- **性能要件**: 表形式で定量的に記載
- **並行性・スレッド安全性**: 必要に応じてロック戦略やスレッドモデルを記述

### 4. 実装仕様

- **公開インターフェース**: クラス図またはシグネチャ一覧を Python コードブロックで記載
- **内部設計**: 必要に応じてシーケンス図や状態遷移を記述
- **設定パラメータ**: 4 列の表形式

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `xxx` | `str` | `""` | ── |

- **エラーハンドリング**: カスタム例外の定義と発生条件
- **シングルトン管理**: 新規グローバル singleton は原則追加しない。既存 singleton を残す場合は互換目的ではなく現行責務として必要な理由を明記

### 5. テスト方針

テストケースを表形式で列挙:

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_xxx` | ── |
| 結合 | `test_xxx_integration` | ── |
| ハードウェア | `test_xxx_device` | `@pytest.mark.realdevice` |
| パフォーマンス | `test_xxx_perf` | ── |

テスト配置ルール:
- `tests/unit/` — 純粋ロジックの単体テスト
- `tests/integration/` — 複数モジュールの結合テスト
- `tests/hardware/` — 実機必要テスト（`@pytest.mark.realdevice`）
- `tests/perf/` — パフォーマンステスト

### 6. 実装チェックリスト

```markdown
- [ ] 公開 API のシグネチャ確定
- [ ] 内部実装
- [ ] 既存テストが破壊されないことの確認
- [ ] ユニットテスト作成・パス
- [ ] 統合テスト作成・パス
- [ ] 型ヒントの整合性チェック（pyright / ruff）
- [ ] ドキュメントコメント（公開 API のみ）
```

完了時は `[x]` でマーク。

## フレームワーク設計原則

仕様書を書く際は、以下の原則を設計方針セクションに反映すること。

### インターフェース駆動設計

- ハードウェア依存を **ABC（抽象基底クラス）** で隔離する
  - `SerialCommInterface`, `CaptureDeviceInterface`, `SerialProtocolInterface`
- テスト用 Dummy 実装（`DummySerialComm`, `DummyCaptureDevice`）を用意し、実機なしでテスト可能にする
- 新しい外部依存を追加する際は、まずインターフェースを定義する

```python
# Good: インターフェースで抽象化
class NewDeviceInterface(ABC):
    @abstractmethod
    def connect(self) -> None: ...

# Bad: 具象クラスに直接依存
class MacroBase:
    def __init__(self):
        self.device = ConcreteDevice()  # テスト困難
```

### 依存方向の制約

```
macros/xxx/  →  nyxpy.framework.*   OK （フレームワーク依存）
nyxpy.framework.*  →  macros/xxx/   NG （逆依存禁止）
nyxpy.gui  →  nyxpy.framework.*     OK （GUI がフレームワークを使う）
nyxpy.framework.*  →  nyxpy.gui     NG （フレームワークが GUI に依存しない）
```

フレームワーク層は **下位レイヤー**（ハードウェア抽象・ユーティリティ）にのみ依存し、上位レイヤー（GUI・CLI・マクロ）には依存しない。

### シングルトンの管理

- 新規グローバル singleton は原則追加しない
- Runtime、Port、settings store、secrets store、device manager は composition root またはテスト fixture が lifetime を所有する
- 既存 `singletons.py` への依存は cleanup 対象として扱い、互換目的で延命しない

### 後方互換性

- Project NyX のフレームワーク本体はアルファ版として扱い、再設計や cleanup では破壊的変更を許容する
- レガシー API、互換 shim、旧 import path、旧設定経路は、ユーザから明示的に求められない限り移行期間を設けず削除する
- `warnings.warn()`、旧名 alias、import 互換 module を追加して旧実装を延命しない
- 旧実装を残す場合は、後方互換性ではなく現行アーキテクチャ上の責務として必要な理由を仕様書に明記する

### スレッド安全性

- `CancellationToken` はスレッドセーフに設計されている（`threading.Event` ベース）
- `AsyncCaptureDevice` はフレームキャッシュに `threading.Lock` を使用
- シングルトンへのアクセスが複数スレッドから行われる場合はロック戦略を明記する

## 記述スタイルガイド

- **言語**: 日本語で記述。技術用語（Command, MacroBase, ABC, OCR 等）は英語のまま使用
- **文体**: 事実ベース・簡潔に。「である」調
- **コードブロック**: 言語指定付き（```python, ```toml など）
- **数式**: インラインは `code span` で記載
- **表**: パイプテーブル記法。ヘッダ行の後に区切り行 `|---|` を必ず入れる
- **リンク**: 相対パスで他の仕様書やコードを参照

## フレームワークモジュール一覧

仕様書のスコープ設定に使える。対象モジュールを選ぶ際の参考にすること。

| パッケージ | 主要クラス / 関数 | 責務 |
|------------|-------------------|------|
| `core/macro/` | `MacroBase`, `Command`, `MacroExecutor`, `@check_interrupt` | マクロ実行基盤 |
| `core/hardware/` | `SerialComm`, `AsyncCaptureDevice`, `CH552SerialProtocol`, `StaticResourceIO` | ハードウェア抽象化 |
| `core/imgproc/` | `ImageProcessor`, `TemplateMatcher`, `OCRProcessor` | 画像処理・OCR |
| `core/logger/` | `LogManager` | 統合ログ管理 |
| `core/settings/` | `GlobalSettings`, `SecretsSettings` | 設定永続化 |
| `core/api/` | `NotificationHandler`, `DiscordNotification`, `BlueskyNotification` | 外部通知 |
| `core/utils/` | `CancellationToken`, ヘルパー関数 | 共通ユーティリティ |
| `core/constants/` | `Button`, `Hat`, `LStick`, `RStick`, `KeyType` | 定数定義 |
| `core/singletons.py` | `serial_manager`, `capture_manager`, `global_settings` | グローバルインスタンス |

## 執筆手順

### 新規作成 (new)

1. **スコープ確認**: 変更対象のフレームワークモジュールを特定する
2. **現状調査**: 対象モジュールのソースコードを読み、公開 API・内部構造を把握する
3. **関連ドキュメント確認**: `spec/framework/archive/` 配下の旧設計ドキュメントを参考情報として参照する
   - [spec/framework/archive/architecture.md](../../../spec/framework/archive/architecture.md) — 全体アーキテクチャ
   - [spec/framework/archive/logging_design.md](../../../spec/framework/archive/logging_design.md) — ロガー設計
   - [spec/framework/archive/protocol_design.md](../../../spec/framework/archive/protocol_design.md) — プロトコル設計
   - [spec/framework/archive/macro_design.md](../../../spec/framework/archive/macro_design.md) — マクロ基盤設計
   - [spec/framework/archive/notification_system.md](../../../spec/framework/archive/notification_system.md) — 通知システム設計
   - 現行仕様は `src/nyxpy/framework/` のソースコードを正とする
4. **影響範囲分析**: GUI・CLI・既存マクロへの影響を洗い出す
5. **テンプレート展開**: [テンプレートファイル](./template.md) をコピーし各セクションを埋める
6. **後方互換チェック**: 既存の公開 API を変更する場合は移行ガイドを記述
7. **テスト方針策定**: Dummy 実装で単体テスト可能かを確認

### レビュー (review)

1. 対象ファイルを読み込む
2. 以下の観点でチェック:
   - 6 セクションすべてが存在するか
   - 用語定義が表形式か
   - 公開 API のシグネチャが Python コードブロックで記載されているか
   - 依存方向の制約が守られているか
   - 後方互換性への言及があるか（破壊的変更の場合）
   - テスト方針にテスト種別（unit / integration / hardware / perf）が明記されているか
   - 設計原則（インターフェース駆動・シングルトン管理・スレッド安全性）が反映されているか
3. 問題点を箇条書きで報告し修正案を提示

### 修正 (fix)

1. レビュー結果に基づき対象ファイルを編集
2. チェックリストの該当項目を `[x]` に更新
