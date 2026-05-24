# インストール

## 必要なもの

- Python 3.12 以上、3.14 未満
- [uv](https://github.com/astral-sh/uv)
- キャプチャデバイス
- CH552 プロトコルなど NyX が対応するシリアル通信デバイス

uv が未導入の場合は、PowerShell でインストールします。

```powershell
pip install uv
```

## 公開後の導入手順

配布パッケージ `nyxfw` は公開準備中です。公開後は `uv tool install` で CLI / GUI を導入します。

```powershell
uv tool install nyxfw
nyxpy --help
```

マクロが追加の外部ライブラリを必要とする場合、`uv tool install` で作られる隔離環境にもその依存が必要です。必要な依存はマクロ配布元の手順を確認してください。

## リポジトリから使う

公開前に動作確認する場合や、NyX 本体を修正する場合はリポジトリを取得します。

```powershell
git clone https://github.com/niart120/Project_NyX.git
Set-Location .\Project_NyX
uv sync
uv run nyxpy --help
```

GUI を起動します。

```powershell
uv run nyxpy gui
```

旧来の alias も使えます。

```powershell
uv run nyx-gui
```

## workspace の初期化

マクロを実行する作業ディレクトリで workspace を初期化します。

```powershell
nyxpy init
```

リポジトリから起動している場合は `uv run` を付けます。

```powershell
uv run nyxpy init
```

`nyxpy init` は確認用の `sample_macro` も生成します。サンプルなしの空 workspace にする場合:

```powershell
nyxpy init --blank
```

## ドキュメントを確認する

インストール後は `nyxpy docs` で公開ドキュメントの URL とローカル API 参照方法を確認できます。

```powershell
nyxpy docs
```
