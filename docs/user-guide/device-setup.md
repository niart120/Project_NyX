# デバイス設定

NyX はゲーム画面を取得するキャプチャデバイスと、コントローラー入力を送るシリアル通信デバイスを使います。

## GUI で設定する

GUI を起動します。

```powershell
nyxpy gui
```

初回起動時または設定変更時に、次を選択します。

| 項目 | 内容 |
|------|------|
| Capture device | Switch の映像を取得するキャプチャデバイス |
| Serial device | CH552 などのコントローラー送信用デバイス |
| Serial protocol | 既定値は `CH552` |
| FPS | プレビューやキャプチャ取得の頻度 |

設定は workspace の `.nyxpy\global.toml` に保存されます。

## CLI で指定する

CLI 実行では `--serial` と `--capture` を指定します。

```powershell
nyxpy run sample_macro --serial COM3 --capture "Capture Device"
```

必要に応じて protocol と baud rate を指定します。

```powershell
nyxpy run sample_macro --serial COM3 --capture "Capture Device" --protocol CH552 --baud 9600
```

## 主な設定ファイル

```text
.nyxpy\
  global.toml
  secrets.toml
```

`global.toml` にはデバイス名、キャプチャ方式、ログ設定などの通常設定を保存します。`secrets.toml` は通知用 token や webhook URL などの秘密情報を保存します。`secrets.toml` の内容は公開リポジトリへ含めないでください。

## キャプチャ方式

`capture_source_type` は `camera` または `window` を指定できます。通常のキャプチャカードは `camera` を使います。ウィンドウキャプチャを使う場合は、対象ウィンドウ名と backend の設定も必要です。
