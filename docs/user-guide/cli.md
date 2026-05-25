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
| シリアルデバイス | OS 上のデバイス名を `--serial` に指定する |
| キャプチャデバイス | GUI または OS の表示名を `--capture` に指定する |

## 主なオプション

| オプション | 内容 |
|------------|------|
| `--serial`, `-s` | シリアルデバイス名。例: Windows は `COM3`、macOS は `/dev/cu.usbmodem*`、Linux は `/dev/ttyACM*` |
| `--capture`, `-c` | キャプチャデバイス名または識別子 |
| `--protocol`, `-p` | 通信プロトコル。既定値は `CH552` |
| `--baud` | シリアルボーレート。未指定時は protocol の既定値 |
| `--define` | マクロへ渡す `key=value` 形式の引数 |
| `--verbose` | 詳細ログを出す |
| `--silence` | コンソールログを最小限にする |

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
