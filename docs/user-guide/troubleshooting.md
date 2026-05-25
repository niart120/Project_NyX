# トラブルシューティング

## デバイスが認識されない

確認するもの:

- キャプチャデバイスとシリアルデバイスが PC に接続されている。
- OS 側でデバイスが認識されている。
- 別の USB ポートに差し替えても同じ症状になるか。
- `--serial` に指定した COM port が正しい。

CLI では指定値を明示します。

```console
nyxpy run sample_macro --serial COM3 --capture "Capture Device"
```

## プレビューが表示されない

確認するもの:

- キャプチャソフトなど他アプリが同じデバイスを占有していない。
- GUI の設定で別のキャプチャデバイスを選ぶと表示されるか。
- `capture_source_type` と `capture_backend` の設定が実際の取得方法に合っているか。
- FPS を下げると安定するか。

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

## マクロ実行が失敗する

確認するもの:

- マクロに必要な `resources/<macro_id>/settings.toml` や画像資材がある。
- `--define key=value` の key と値がマクロの説明と一致している。
- 実機が必要なマクロを dummy 設定で実行していない。
- ログに表示されたエラーが設定値、デバイス、画像資材のどれに関係しているか。

ログは workspace の `logs/` と `runs/` に保存されます。

## 通知が届かない

確認するもの:

- `.nyxpy/secrets.toml` の `enabled` が `true`。
- webhook URL や password が正しい。
- ネットワークが外部サービスへ接続できる。
- マクロ側が `cmd.notify(...)` を呼んでいる。

秘密情報を Issue やログに貼らないでください。
