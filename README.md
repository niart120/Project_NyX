# Project NyX

![Alpha Version Badge](https://img.shields.io/badge/Status-Alpha-orange)

NyX は、Nintendo Switch 向け自動化ツールの開発フレームワークです。PC に接続したキャプチャデバイスからゲーム画面を取得し、シリアル通信デバイスを介してコントローラー操作を自動化できます。

**注意: このソフトウェアは現在開発中のα版です。機能や設計が頻繁に変更される可能性があります。**

![GUI Screenshot](docs/assets/sample_macro_screenshot.png)

## 1. 概要

### 主な機能
- PySide6を使用したGUIインターフェース
- コマンドライン(CLI)インターフェース  
- Runtime / RunHandle によるマクロの実行・中断・結果管理
- リアルタイム画面プレビュー
- スナップショット機能
- 構造化ログとGUI表示イベントを分離するログ基盤
- キャプチャデバイス・シリアルデバイスの設定
- 外部通知システム (Discord, Bluesky)
- 設定の永続化 (.nyxpy/)

### 必要なハードウェア
- **キャプチャデバイス**: Nintendo Switchの画面を取得するためのキャプチャカード/ボード
- **シリアル通信デバイス**: CH552プロトコルをサポートするコントロール送信デバイス

## 2. インストールと起動

### 必要条件

- Python 3.12以上
- 対応OS: Windows/macOS/Linux
- 必要なハードウェア接続済み (キャプチャデバイス, シリアルデバイス)

Python のパッケージ管理には [uv](https://github.com/astral-sh/uv) を使用します。

### 公開後の導入

配布パッケージ `nyxfw` は公開準備中です。公開後は次の導線を使います。

```powershell
uv tool install nyxfw
nyxpy init
nyxpy gui
```

### リポジトリから起動

現時点で動作確認する場合や NyX 本体を修正する場合は、リポジトリをクローンして起動してください。

```powershell
git clone https://github.com/niart120/Project_NyX.git
Set-Location .\Project_NyX
uv sync
uv run nyxpy init
uv run nyxpy gui
```

詳細は [利用者向けガイド](docs/user-guide/README.md) を参照してください。

## 3. 使用方法

### GUI アプリケーションの起動

```powershell
nyxpy gui
```

リポジトリから起動する場合:

```powershell
uv run nyxpy gui
```

### 初回起動時

1. `nyxpy init` で workspace を初期化します。
2. デバイス設定ダイアログでキャプチャデバイスとシリアルデバイスを選択します。
3. デバイスが検出されない場合は、接続を確認して設定画面から再設定します。

### マクロの作成と実行

1. `macros\` と `resources\` にマクロを配置します。
2. GUIからマクロを選択
3. 実行ボタンをクリック
4. 必要に応じてパラメータを設定
5. ログペインでマクロの進行状況を確認

マクロを新規作成する場合は、`nyxpy create <macro_id>` で雛形を生成できます。詳細は [マクロ開発者向けドキュメント](docs/macro-development/README.md) を参照してください。

### プレビューとスナップショット

- 右側のペインにゲーム画面のリアルタイムプレビューが表示
- スナップショットボタンで現在のフレームを `snapshots\` フォルダに保存

### CLIでの実行

コマンドラインからマクロを直接実行することも可能です:

```powershell
nyxpy run sample_macro --serial COM3 --capture "Capture Device"
```

**主なオプション:**

| オプション | 内容 |
|------------|------|
| `--serial` | シリアルデバイス名 |
| `--capture` | キャプチャデバイス名または識別子 |
| `--protocol` | 通信プロトコル。既定値は `CH552` |
| `--verbose` | 詳細ログ出力 |
| `--silence` | ログ出力を最小限に抑制 |
| `--define` | マクロ変数の定義。例: `--define key=value` |

### 通知機能

マクロ実行完了時に外部サービスへ通知を送信できます:

- **Discord**: Webhook経由での通知
- **Bluesky**: AT Protocolを使用した投稿

通知設定は `.nyxpy\secrets.toml` で設定します。

### デバイス設定

- メニューの「File」→「Settings」から設定画面を開く
- キャプチャデバイス、FPS、シリアルデバイス、ボーレートを設定

## 4. マクロ開発

マクロ本体はローカル作業用の `macros\`、設定・画像資材は `resources\` に配置します。`examples\macros` と `examples\resources` は公開サンプルの参照先であり、利用者の配置先ではありません。

実装手順、雛形、AI エージェント向けの要点は [docs\macro-development\README.md](docs/macro-development/README.md) を参照してください。

## 5. 設定ファイル

`.nyxpy\global.toml` に基本設定が保存されます。GUI 上での変更は自動的に保存されます。

### 設定ファイルの構造
- **global.toml**: デバイス設定、シリアル通信設定など
- **secrets.toml**: 通知システムの認証情報など機密情報

### 主な設定項目
- `capture_device`: キャプチャデバイス名
- `serial_device`: シリアルデバイス名  
- `serial_baud`: シリアル通信のボーレート
- `serial_protocol`: 通信プロトコル (デフォルト: "CH552")

## 6. トラブルシューティング

### デバイスが認識されない場合
- デバイスのドライバが正常にインストールされているか確認
- 別のUSBポートに接続を試す
- スタートアップリストをクリアし、再試行

### プレビューが表示されない場合
- キャプチャデバイスが正常に機能しているか確認
- 設定ダイアログで別のデバイスを選択
- FPS設定を30に下げてみる

### マクロが動作しない場合
- ログを確認して具体的なエラーを特定
- シリアルデバイスの接続状態を確認
- 引数（パラメータ）が必要な場合は適切に設定

### クラッシュする場合
- ログファイル (`logs/logfile.log`) を確認
- Python および依存ライブラリのバージョンを確認
- GitHub Issuesで報告（ログを添付）

### ログに関する問題
- ログは自動的に `logs/` ディレクトリに保存されます
- ログレベル調整: CLI では `--verbose` / `--silence` オプション
- ログローテーション: 1MB で自動ローテーション

## 7. 今後の予定

- マクロ機能の拡張
    - マクロの中断・再開機能
    - 複数マクロの同時実行
- 通知システムの拡張
    - 追加の通知プラットフォーム対応
- パフォーマンス最適化
- 手動入力層の追加検討

## 8. ライセンス

このプロジェクトは [MIT License](LICENSE) の下でライセンスされています。

## 9. 貢献方法

フィードバックや貢献は大歓迎です！
- バグ報告や機能リクエストは GitHub Issues にお願いします
- コントリビューションは Pull Request で受け付けています

開発者向けの旧設計ドキュメントは `spec/framework/archive/` に移設しています。現行仕様を確認する場合は `src/nyxpy/` 配下の実装を正としてください。
