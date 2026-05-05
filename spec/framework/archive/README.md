# フレームワーク設計ドキュメントアーカイブ

このディレクトリは、旧 `docs` 配下にあった設計系 Markdown を移設したアーカイブである。後続のリアーキテクチャ検討で参照できるよう、現行ソースコードと明確に矛盾する API 名、リンク、設定キーを更新している。

## 移設元と移設先

| 移設元 | 移設先 | 主な対象 |
|--------|--------|----------|
| `docs/architecture.md` | `spec/framework/archive/architecture.md` | 全体アーキテクチャ |
| `docs/macro_design.md` | `spec/framework/archive/macro_design.md` | マクロ実行基盤 |
| `docs/hardware_design.md` | `spec/framework/archive/hardware_design.md` | シリアル通信・キャプチャ管理 |
| `docs/protocol_design.md` | `spec/framework/archive/protocol_design.md` | シリアルプロトコル抽象化 |
| `docs/protocol/*.md` | `spec/framework/archive/protocol/*.md` | CH552 / PokeCon プロトコル詳細 |
| `docs/logging_design.md` | `spec/framework/archive/logging_design.md` | ログ管理 |
| `docs/notification_system.md` | `spec/framework/archive/notification_system.md` | 外部通知 |
| `docs/gui/*.md` | `spec/framework/archive/gui/*.md` | GUI 要件・技術選定 |

`docs/assets/` は README の画像参照先として残している。

## 現行コード上の正本

| 領域 | 正本となるソース |
|------|------------------|
| マクロ実行基盤 | `src/nyxpy/framework/core/macro/` |
| ハードウェア抽象化 | `src/nyxpy/framework/core/hardware/` |
| プロトコル選択 | `src/nyxpy/framework/core/hardware/protocol_factory.py` |
| 画像処理・OCR | `src/nyxpy/framework/core/imgproc/` |
| ログ管理 | `src/nyxpy/framework/core/logger/log_manager.py` |
| 設定永続化 | `src/nyxpy/framework/core/settings/` |
| 外部通知 | `src/nyxpy/framework/core/api/` |
| GUI | `src/nyxpy/gui/` |

## 再設計時の注意点

| 論点 | 現状 |
|------|------|
| 通知設定 | `create_notification_handler_from_settings` は `SecretsSettings` 互換の `get()` を前提に `notification.discord.*` / `notification.bluesky.*` を読む。CLI 側では `GlobalSettings` を渡している箇所があり、再設計時の確認対象である。 |
| シングルトン | `singletons.py` は `serial_manager` / `capture_manager` / `global_settings` / `secrets_settings` を管理する。`LogManager` は `log_manager.py` 内でグローバル生成される。 |
| GUI 状態管理 | 専用の `DeviceModel` クラスは現行コードに存在しない。GUI は `singletons.py` の Manager、`EventBus`、`VirtualControllerModel` を組み合わせている。 |
| プロトコル | `ProtocolFactory` は `CH552` / `PokeCon` / `3DS` を登録し、プロトコル別の既定ボーレートと対応ボーレートを持つ。 |
| マクロ API | `MacroBase.initialize(cmd, args)`、`Command.type()`、`Command.notify()`、3DS 向け `touch` / `disable_sleep` が現行 API に含まれる。 |
