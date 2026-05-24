# 利用者向けガイド

NyX を使って既存マクロを実行する人向けの入口です。Python のコードを書く手順は [マクロ開発者向けドキュメント](../macro-development/README.md) に分けています。

## 最短手順

配布パッケージ `nyxfw` は公開準備中です。公開後は次の流れを主導線にします。

```powershell
uv tool install nyxfw
nyxpy init
nyxpy gui
```

現時点で動作確認する場合は、リポジトリを取得して次のように起動します。

```powershell
git clone https://github.com/niart120/Project_NyX.git
Set-Location .\Project_NyX
uv sync
uv run nyxpy init
uv run nyxpy gui
```

`nyxpy init` は `.nyxpy\`, `macros\`, `resources\`, `logs\`, `runs\`, `snapshots\` を用意し、確認用の `sample_macro` も生成します。空の作業領域だけを作る場合は `nyxpy init --blank` を使います。

## 目的別のページ

| 文書 | 内容 |
|------|------|
| [インストール](installation.md) | Python / uv、公開後の `uv tool install`、リポジトリ取得、初回起動 |
| [デバイス設定](device-setup.md) | キャプチャデバイス、シリアルデバイス、プロトコル、設定ファイル |
| [GUI の使い方](gui.md) | GUI 起動、マクロ選択、プレビュー、スナップショット |
| [CLI の使い方](cli.md) | `nyxpy run`、`--serial`、`--capture`、`--define` |
| [通知設定](notifications.md) | Discord / Bluesky 通知と秘密情報の扱い |
| [トラブルシューティング](troubleshooting.md) | デバイス未検出、プレビュー不可、マクロ実行失敗、ログ確認 |

## 作業ディレクトリ

NyX は、コマンドを実行したディレクトリまたは親ディレクトリから `.nyxpy\` を探して workspace を決めます。マクロを実行する前に、対象 workspace の中で `nyxpy init` を済ませてください。

```text
your-workspace\
  .nyxpy\
    global.toml
    secrets.toml
  macros\
  resources\
  logs\
  runs\
  snapshots\
```

既存マクロを追加する場合は、マクロ配布元の手順に従って `macros\` と `resources\` へ配置します。自分でマクロを作る場合は、`nyxpy create <macro_id>` で雛形を生成できます。
