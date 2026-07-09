# CLI の使い方

## 基本形

`nyxpy run` は workspace 内のマクロを実行します。コマンドは `.nyxpy/` がある workspace の中、またはその子ディレクトリで実行します。

```console
nyxpy run sample_macro --serial <serial-device> --capture "Capture Device"
```

リポジトリの内容を直接使う場合:

```console
uv run nyxpy run sample_macro --serial <serial-device> --capture "Capture Device"
```

`nyx-cli` でも同じ CLI 実行機能を使えます。

## 実行前に確認すること

| 確認項目 | 内容 |
|----------|------|
| workspace | `nyxpy init` 済みで `.nyxpy/` がある |
| マクロ | `macros/<macro_id>/` に配置されている |
| リソース | マクロが必要とする `resources/<macro_id>/` がある |
| controller backend | シリアル通信なら `serial`、専用 USB Bluetooth adapter なら `swbt` |
| シリアルデバイス | `serial` backend では OS 上のデバイス名を `--serial` に指定する |
| swbt adapter | `swbt` backend では `nyxpy swbt adapters` で候補を確認し、`--swbt-adapter` に指定する |
| キャプチャデバイス | GUI または OS の表示名を `--capture` に指定する |

## 主なオプション

| オプション | 内容 |
|------------|------|
| `--serial`, `-s` | シリアルデバイス名。例: Windows は `COM3`、macOS は `/dev/cu.usbmodem*`、Linux は `/dev/ttyACM*` |
| `--capture`, `-c` | キャプチャデバイス名または識別子 |
| `--protocol`, `-p` | 通信プロトコル。既定値は `CH552` |
| `--baud` | シリアルボーレート。未指定時は protocol の既定値 |
| `--controller` | controller backend。`serial` または `swbt` |
| `--swbt-adapter` | swbt 用 USB Bluetooth adapter 名。候補が 1 件でも自動採用しない |
| `--swbt-controller-type` | `pro-controller`、`joy-con-l`、`joy-con-r` |
| `--swbt-key-store` | pairing key store の path |
| `--swbt-timeout` | pair / reconnect の timeout 秒 |
| `--define` | マクロへ渡す `key=value` 形式の引数 |
| `--verbose` | 詳細ログを出す |
| `--silence` | コンソールログを最小限にする |

## swbt backend を使う

adapter 候補を表示します。

```console
nyxpy swbt adapters
nyxpy swbt adapters --json
```

初回は pairing を行い、controller type ごとに key store を分けます。

```console
nyxpy swbt pair --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
```

保存済み key store で reconnect します。

```console
nyxpy swbt reconnect --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
```

同じ NyX プロセスが管理している session を閉じます。

```console
nyxpy swbt disconnect --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
```

マクロ実行では `--controller swbt` を指定します。key store がない場合でも暗黙の pairing は行いません。

```console
nyxpy run sample_macro --controller swbt --swbt-adapter usb:0 --swbt-controller-type pro-controller --swbt-key-store .nyxpy/swbt/pro-controller-bond.json --capture "Capture Device"
```

## 終了時の見方

| 終了コード | 意味 |
|------------|------|
| `0` | マクロが完了した |
| `1` | 設定値や引数に問題がある |
| `2` | 実行中にエラーが発生した |
| `130` | ユーザ操作で中断された |

失敗時はコンソール表示に加えて `logs/` と `runs/` を確認してください。

## マクロ引数を渡す

`--define` は複数回指定できます。

```console
nyxpy run sample_macro --serial <serial-device> --capture "Capture Device" --define count=30 --define capture_name=debug/result.png
```

マクロ側が対応している引数名と値は、各マクロの説明を確認してください。

値に空白を含む場合は、利用している shell の規則に従って引用符で囲みます。

## workspace が見つからない場合

`nyxpy run` は `.nyxpy/` があるディレクトリを workspace として使います。見つからない場合は、対象ディレクトリで初期化します。

```console
nyxpy init
```

リポジトリの内容を直接使う場合:

```console
uv run nyxpy init
```

## 雛形を作る

自分でマクロを作る場合は、workspace 初期化後に `nyxpy create` を使います。

```console
nyxpy create sample_turbo
```

マクロ実装の詳細は [マクロ開発者向けドキュメント](../macro-development/README.md) を参照してください。
