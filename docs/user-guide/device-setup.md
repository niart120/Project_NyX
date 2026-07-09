# デバイス設定

NyX はゲーム画面を取得するキャプチャデバイスと、コントローラー入力を送る controller backend を使います。controller backend は、シリアル通信デバイスを使う `serial` と、専用 USB Bluetooth adapter を使う `swbt` から選べます。

## 接続前の確認

| 機材 | 確認すること |
|------|--------------|
| キャプチャデバイス | Switch の映像が OS または別のキャプチャソフトで認識されている |
| シリアル通信デバイス | `serial` backend を使う場合、OS 上でシリアルポートとして認識されている |
| swbt 用 USB Bluetooth adapter | `swbt` backend を使う場合、PC 内蔵 Bluetooth ではなく専用 adapter を接続する |
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
| Controller Backend | `serial` または `swbt` |
| Serial Device | CH552 などのコントローラー送信用デバイス |
| Protocol | 既定値は `CH552` |
| Baud Rate | protocol の既定値を使う。CH552 の既定値は `9600` |
| swbt Controller | `Pro Controller`、`Joy-Con L`、`Joy-Con R` から選ぶ |
| swbt Adapter | `リロード` で候補を取得し、使う adapter を明示的に選ぶ。候補が 1 件でも自動選択しない |
| swbt Key Store | pairing key の保存先。未指定時は `.nyxpy/swbt/<controller>-bond.json` |
| swbt Connection | `Pair`、`Reconnect`、`Disconnect` を実行する |
| Preview FPS | GUI プレビューの更新頻度 |

設定は workspace の `.nyxpy/global.toml` に保存されます。

`Pair` は初回 pairing で key store を作ります。2 回目以降は `Reconnect` を使います。`Disconnect` は NyX の同一プロセスが管理している swbt session を閉じる操作で、Switch 側や別プロセスの接続状態までは保証しません。

## CLI で指定する

CLI 実行で `serial` backend を使う場合は `--serial` と `--capture` を指定します。シリアルデバイス名は OS によって異なるため、汎用手順では `<serial-device>` と書きます。

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

`swbt` backend を使う場合は、先に adapter を確認して pairing または reconnect を実行します。

```console
nyxpy swbt adapters
nyxpy swbt pair --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
nyxpy swbt reconnect --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
```

マクロ実行時は controller backend を明示します。`swbt` は保存済み key store に基づいて reconnect し、暗黙の pairing は行いません。

```console
nyxpy run sample_macro --controller swbt --swbt-adapter usb:0 --swbt-controller-type pro-controller --swbt-key-store .nyxpy/swbt/pro-controller-bond.json --capture "Capture Device"
```

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
