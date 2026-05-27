# 利用者向けガイド

NyX を使って既存マクロを実行する人向けの入口です。マクロを実装する手順は [マクロ開発者向けドキュメント](../macro-development/README.md) に分けています。

## 前提

| 項目 | 内容 |
|------|------|
| OS | Windows / macOS / Linux |
| 導入方法 | uv による導入 |
| 実行方法 | GUI または `nyxpy run` |
| 必要な機材 | キャプチャデバイス、シリアル通信デバイス |

NyX は uv が管理する Python 環境で動作します。Python の実装知識や Python 本体の手動インストールは不要です。

## 最短手順

配布パッケージ `nyxpy-fw` を使う場合:

```console
uv tool install nyxpy-fw
nyxpy init
nyxpy gui
```

リポジトリの内容を直接使う場合:

```console
git clone https://github.com/niart120/Project_NyX.git
cd Project_NyX
uv sync
uv run nyxpy init
uv run nyxpy gui
```

`nyxpy init` は `.nyxpy/`, `macros/`, `resources/`, `logs/`, `runs/`, `snapshots/` を用意し、確認用の `sample_macro` も生成します。空の作業領域だけを作る場合は `nyxpy init --blank` を使います。

## 基本の作業順

1. [インストール](installation.md) に従って `nyxpy` を実行できる状態にする。
2. マクロを実行するディレクトリで `nyxpy init` を実行する。
3. キャプチャデバイスとシリアル通信デバイスを接続する。
4. [デバイス設定](device-setup.md) でデバイス名と通信設定を確認する。
5. [GUI](gui.md) または [CLI](cli.md) でマクロを実行する。
6. 失敗した場合は [トラブルシューティング](troubleshooting.md) でログと設定を確認する。

## 目的別のページ

| 文書 | 内容 |
|------|------|
| [インストール](installation.md) | uv、`uv tool install`、リポジトリ取得、初回起動 |
| [デバイス設定](device-setup.md) | キャプチャデバイス、シリアルデバイス、プロトコル、設定ファイル |
| [GUI の使い方](gui.md) | GUI 起動、マクロ選択、プレビュー、スナップショット |
| [CLI の使い方](cli.md) | `nyxpy run`、`--serial`、`--capture`、`--define` |
| [通知設定](notifications.md) | Discord / Bluesky 通知と秘密情報の扱い |
| [トラブルシューティング](troubleshooting.md) | デバイス未検出、プレビュー不可、マクロ実行失敗、ログ確認 |

## 作業ディレクトリ

NyX は、コマンドを実行したディレクトリまたは親ディレクトリから `.nyxpy/` を探して workspace を決めます。マクロを実行する前に、対象 workspace の中で `nyxpy init` を済ませてください。パス表記は OS に依存しにくい `/` 区切りで示します。

```text
your-workspace/
  .nyxpy/
    global.toml
    secrets.toml
  macros/
  resources/
  logs/
  runs/
  snapshots/
```

既存マクロを追加する場合は、マクロ配布元の手順に従って `macros/` と `resources/` へ配置します。自分でマクロを作る場合は、`nyxpy create <macro_id>` で雛形を生成できます。

## 用語

| 用語 | 意味 |
|------|------|
| workspace | `.nyxpy/`, `macros/`, `resources/` などを持つ作業ディレクトリ |
| マクロ | NyX で実行する自動操作の単位 |
| キャプチャデバイス | Switch の画面を PC に取り込むデバイス |
| シリアル通信デバイス | Switch へコントローラー入力を送るデバイス |
