# インストール

## 必要なもの

| 項目 | 内容 |
|------|------|
| uv | [uv 公式のインストール手順](https://docs.astral.sh/uv/getting-started/installation/)に従って導入する |
| キャプチャデバイス | Switch の映像を PC に取り込む |
| シリアル通信デバイス | CH552 プロトコルなど NyX が対応する方式で入力を送る |
| swbt 用 USB Bluetooth adapter | swbt backend を使う場合だけ必要。PC 内蔵 Bluetooth ではなく Bumble が直接開ける専用 adapter を使う |
| Git | リポジトリの内容を直接使う場合だけ使う |

NyX は uv が管理する Python 環境で動作します。Python 本体を個別に導入する手順は不要です。

swbt backend は `nyxpy-fw` の通常依存として導入されます。swbt 用の extra 指定や追加同期手順は不要です。

uv の導入確認:

```console
uv --version
```

## パッケージで導入する

配布パッケージ `nyxpy-fw` を使う場合は `uv tool install` で CLI / GUI を導入します。

```console
uv tool install nyxpy-fw
nyxpy --help
```

`nyxpy --help` で `run`, `init`, `create`, `docs`, `gui` が表示されれば導入できています。

更新する場合:

```console
uv tool upgrade nyxpy-fw
```

マクロが追加の外部ライブラリを必要とする場合、`uv tool install` で作られる隔離環境にもその依存が必要です。必要な依存はマクロ配布元の手順を確認してください。

## リポジトリの内容を直接使う

リポジトリの内容を直接使う場合は、取得したディレクトリで `uv run nyxpy ...` を実行します。

```console
git clone https://github.com/niart120/Project_NyX.git
cd Project_NyX
uv sync
uv run nyxpy --help
```

GUI を起動します。

```console
uv run nyxpy gui
```

`uv run nyx-gui` でも同じ GUI を起動できます。

```console
uv run nyx-gui
```

## workspace の初期化

マクロを実行する作業ディレクトリで workspace を初期化します。

```console
nyxpy init
```

リポジトリの内容を直接使う場合は `uv run` を付けます。

```console
uv run nyxpy init
```

`nyxpy init` は確認用の `sample_macro` も生成します。サンプルなしの空 workspace にする場合:

```console
nyxpy init --blank
```

リポジトリの内容を直接使う場合:

```console
uv run nyxpy init --blank
```

初期化後は次のディレクトリが作成されます。

```text
.nyxpy/
macros/
resources/
logs/
runs/
snapshots/
```

## ドキュメントを確認する

インストール後は `nyxpy docs` で公開ドキュメントの URL とローカル API 参照方法を確認できます。

```console
nyxpy docs
```

リポジトリの内容を直接使う場合:

```console
uv run nyxpy docs
```
