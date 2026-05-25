# トラブルシューティング

## デバイスが認識されない

症状:

- GUI の設定画面にデバイスが表示されない。
- CLI 実行時にシリアルデバイスまたはキャプチャデバイスを開けない。

確認するもの:

- キャプチャデバイスとシリアルデバイスが PC に接続されている。
- OS 側でデバイスが認識されている。
- 別の USB ポートに差し替えても同じ症状になるか。
- `--serial` に指定したシリアルデバイス名が正しい。

CLI では指定値を明示します。

```console
nyxpy run sample_macro --serial <serial-device> --capture "Capture Device"
```

| OS | シリアルデバイス名の例 |
|----|------------------------|
| Windows | `COM3` |
| macOS | `/dev/cu.usbmodem*` |
| Linux | `/dev/ttyACM*` |

GUI では `設定` 画面のリロードボタンでデバイス一覧を読み直します。別アプリがキャプチャデバイスを使っている場合は、そのアプリを閉じてから再確認してください。

## プレビューが表示されない

症状:

- GUI 中央のプレビューが黒画面のままになる。
- スナップショットに失敗する。
- CLI 実行中にフレーム取得エラーが出る。

確認するもの:

- キャプチャソフトなど他アプリが同じデバイスを占有していない。
- GUI の設定で別のキャプチャデバイスを選ぶと表示されるか。
- `capture_source_type` と `capture_backend` の設定が実際の取得方法に合っているか。
- FPS を下げると安定するか。

通常の USB キャプチャカードは `capture_source_type = "camera"` を使います。ウィンドウキャプチャを使う場合は、対象ウィンドウ名と backend を確認してください。

## マクロが見つからない

`macros/` 配下にマクロがあるか確認します。

```text
macros/sample_macro/
  macro.py
```

workspace が未初期化の場合:

```console
nyxpy init
```

新規雛形を作る場合:

```console
nyxpy create sample_macro
```

GUI を開いたままマクロを追加した場合は、マクロ一覧の `リロード` を押します。

## マクロ実行が失敗する

症状:

- CLI が `Macro execution failed` またはエラー内容を表示する。
- GUI のマクロログまたはツールログにエラーが出る。

確認するもの:

- マクロに必要な `resources/<macro_id>/settings.toml` や画像資材がある。
- `--define key=value` の key と値がマクロの説明と一致している。
- 実機が必要なマクロを dummy 設定で実行していない。
- ログに表示されたエラーが設定値、デバイス、画像資材のどれに関係しているか。

ログは workspace の `logs/` と `runs/` に保存されます。

## workspace が見つからない

症状:

- CLI で ``NyX workspace not found. Run `nyxpy init` in the project root.`` と表示される。

対処:

```console
nyxpy init
```

リポジトリの内容を直接使う場合:

```console
uv run nyxpy init
```

既存 workspace を使う場合は、`.nyxpy/` があるディレクトリへ移動してから実行します。

## 通知が届かない

確認するもの:

- `.nyxpy/secrets.toml` の `enabled` が `true`。
- webhook URL や password が正しい。
- ネットワークが外部サービスへ接続できる。
- マクロ側が `cmd.notify(...)` を呼んでいる。

秘密情報を Issue やログに貼らないでください。

## ログを共有するとき

Issue や相談でログを共有する場合は、次の情報を残すと原因を追いやすくなります。

| 情報 | 例 |
|------|----|
| 実行方法 | GUI / CLI |
| OS | Windows / macOS / Linux |
| 実行したコマンド | `nyxpy run ...` |
| マクロ名 | `sample_macro` |
| エラー本文 | コンソール、マクロログ、ツールログの該当部分 |

webhook URL、password、token、端末固有 ID は共有前に削除してください。
