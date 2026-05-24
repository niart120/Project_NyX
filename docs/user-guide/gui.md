# GUI の使い方

## 起動

配布パッケージを使う場合:

```powershell
nyxpy gui
```

リポジトリから起動する場合:

```powershell
uv run nyxpy gui
```

`nyx-gui` は `nyxpy gui` の alias です。

## 初回の流れ

1. workspace で `nyxpy init` を実行する。
2. キャプチャデバイスとシリアルデバイスを接続する。
3. `nyxpy gui` を起動する。
4. 設定画面でデバイスを選ぶ。
5. 実行するマクロを選んで開始する。

## マクロの配置

利用者が実行するマクロは workspace の `macros\` と `resources\` に置きます。

```text
macros\sample_macro\
  macro.py

resources\sample_macro\
  settings.toml
  assets\
```

`examples\macros` と `examples\resources` は参照用サンプルです。利用者の配置先ではありません。

## プレビューとスナップショット

GUI のプレビュー領域にキャプチャ中の画面が表示されます。スナップショットは workspace の `snapshots\` に保存されます。

プレビューが表示されない場合は、[トラブルシューティング](troubleshooting.md) の「プレビューが表示されない」を確認してください。
