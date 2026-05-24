# CLI の使い方

## 基本形

`nyxpy run` は workspace 内のマクロを実行します。

```powershell
nyxpy run sample_macro --serial COM3 --capture "Capture Device"
```

リポジトリから起動する場合:

```powershell
uv run nyxpy run sample_macro --serial COM3 --capture "Capture Device"
```

`nyx-cli` は `nyxpy run` の alias です。新しい手順では `nyxpy run` を主導線にします。

## 主なオプション

| オプション | 内容 |
|------------|------|
| `--serial`, `-s` | シリアルデバイス名。例: `COM3` |
| `--capture`, `-c` | キャプチャデバイス名または識別子 |
| `--protocol`, `-p` | 通信プロトコル。既定値は `CH552` |
| `--baud` | シリアルボーレート。未指定時は protocol の既定値 |
| `--define` | マクロへ渡す `key=value` 形式の引数 |
| `--verbose` | 詳細ログを出す |
| `--silence` | コンソールログを最小限にする |

## マクロ引数を渡す

`--define` は複数回指定できます。

```powershell
nyxpy run sample_macro --serial COM3 --capture "Capture Device" --define count=30 --define capture_name=debug/result.png
```

マクロ側が対応している引数名と値は、各マクロの説明を確認してください。

## workspace が見つからない場合

`nyxpy run` は `.nyxpy\` があるディレクトリを workspace として使います。見つからない場合は、対象ディレクトリで初期化します。

```powershell
nyxpy init
```

## 雛形を作る

自分でマクロを作る場合は、workspace 初期化後に `nyxpy create` を使います。

```powershell
nyxpy create sample_turbo
```

マクロ実装の詳細は [マクロ開発者向けドキュメント](../macro-development/README.md) を参照してください。
