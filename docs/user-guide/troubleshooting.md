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

## swbt adapter が使えない

症状:

- `NYX_SWBT_ADAPTER_NOT_SELECTED` が表示される。
- `nyxpy swbt adapters` に adapter が表示されない。
- pair または reconnect が timeout する。

確認するもの:

- PC 内蔵 Bluetooth ではなく、Bumble が直接開ける専用 USB Bluetooth adapter を接続している。
- `nyxpy swbt adapters` で表示された adapter 名または alias を指定している。
- GUI の `swbt Adapter` で候補を選んでいる。候補が 1 件でも NyX は自動選択しない。
- OS や別アプリが同じ adapter を使用していない。
- USB ハブを避け、PC 本体の USB ポートに接続している。

adapter 一覧を JSON で確認します。

```console
nyxpy swbt adapters --json
```

## swbt pair / reconnect が失敗する

症状:

- pair が timeout する。
- reconnect が失敗する。
- `NYX_SWBT_KEY_STORE_INVALID` または key store 関連のエラーが出る。

確認するもの:

- Switch 側が controller の pairing を受け付ける画面になっている。
- `--swbt-controller-type` と実機が一致している。
- controller type ごとに別の key store を使っている。
- key store を手で編集していない。
- 初回は `nyxpy swbt pair`、2 回目以降は `nyxpy swbt reconnect` を使っている。

```console
nyxpy swbt pair --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
nyxpy swbt reconnect --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json
```

`nyxpy run --controller swbt` は暗黙に pairing しません。key store がない場合は、先に pair を実行してください。

## swbt 入力が反映されない

症状:

- Joy-Con L で右 stick、Joy-Con R で左 stick を送ると失敗する。
- 3DS touch、keyboard、sleep control が swbt backend で失敗する。
- 短い `cmd.press(..., dur=...)` が画面上で取りこぼされる。
- マクロ実行中または実行直後に GUI の仮想コントローラー操作が反映されない。

確認するもの:

- 送っている入力が controller type の capability に含まれている。
- swbt backend が扱うのは Switch controller の button / D-pad / stick / IMU であり、3DS touch や keyboard は代替しない。
- 16ms など短い押下は実機・adapter・report 周期の影響を受ける。安定しない場合は `dur=0.05` 以上から確認する。
- マクロ実行中は GUI の手動入力用 controller が解放される。実行後に GUI から手動入力する場合は `Reconnect` を実行する。
- GUI の `Disconnect` は NyX の同一プロセスが管理している session を閉じる操作であり、Switch 側の接続一覧を必ず消す操作ではない。

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
