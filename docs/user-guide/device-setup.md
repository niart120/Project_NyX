# デバイス設定

NyX はゲーム画面を取得するキャプチャデバイスと、コントローラー入力を送るシリアル通信デバイスを使います。

## 接続前の確認

| 機材 | 確認すること |
|------|--------------|
| キャプチャデバイス | Switch の映像が OS または別のキャプチャソフトで認識されている |
| シリアル通信デバイス | OS 上でシリアルポートとして認識されている |
| USB 接続 | ハブ経由で不安定な場合は PC 本体の USB ポートに接続する |

## GUI で設定する

GUI を起動します。

```console
nyxpy gui
```

リポジトリの内容を直接使う場合は `uv run nyxpy gui` を使います。

初回起動時または設定変更時に、画面左側の `設定` ボタンまたはメニューの `File` → `Settings` から設定画面を開きます。

| 項目 | 内容 |
|------|------|
| Capture Source | 通常のキャプチャカードは `camera`、画面上のウィンドウを取り込む場合は `window` |
| Camera / Window | 取り込み対象のデバイス名またはウィンドウ名 |
| Backend | 迷う場合は `auto` |
| Capture FPS | キャプチャ取得頻度。安定しない場合は 30 または 15 に下げる |
| Serial Device | CH552 などのコントローラー送信用デバイス |
| Protocol | 既定値は `CH552` |
| Baud Rate | protocol の既定値を使う。CH552 の既定値は `9600` |
| Preview FPS | GUI プレビューの更新頻度 |

設定は workspace の `.nyxpy/global.toml` に保存されます。

## CLI で指定する

CLI 実行では `--serial` と `--capture` を指定します。シリアルデバイス名は OS によって異なるため、汎用手順では `<serial-device>` と書きます。

```console
nyxpy run sample_macro --serial <serial-device> --capture "Capture Device"
```

必要に応じて protocol と baud rate を指定します。

```console
nyxpy run sample_macro --serial <serial-device> --capture "Capture Device" --protocol CH552 --baud 9600
```

| OS | シリアルデバイス名の例 |
|----|------------------------|
| Windows | `COM3` |
| macOS | `/dev/cu.usbmodem*` |
| Linux | `/dev/ttyACM*` |

キャプチャデバイス名は OS やドライバで表示が変わります。GUI の設定画面で表示される名前を確認してから `--capture` に指定してください。

## 主な設定ファイル

```text
.nyxpy/
  global.toml
  secrets.toml
```

`global.toml` にはデバイス名、キャプチャ方式、ログ設定などの通常設定を保存します。`secrets.toml` は通知用 token や webhook URL などの秘密情報を保存します。`secrets.toml` の内容は公開リポジトリへ含めないでください。

## キャプチャ方式

`capture_source_type` は `camera` または `window` を指定できます。通常のキャプチャカードは `camera` を使います。ウィンドウキャプチャを使う場合は、対象ウィンドウ名と backend の設定も必要です。

| 設定 | 用途 |
|------|------|
| `camera` | USB キャプチャカードなど、カメラデバイスとして認識される入力 |
| `window` | OS 上の特定ウィンドウを取り込む入力 |
| `auto` backend | NyX が利用可能な方式を選ぶ |
| `mss` backend | OS 横断の画面キャプチャ方式 |
| `windows_graphics_capture` backend | Windows のウィンドウキャプチャ方式 |

プレビューが黒画面になる、または更新が止まる場合は、他アプリがキャプチャデバイスを占有していないか確認し、`Capture FPS` や `Preview FPS` を下げてください。
