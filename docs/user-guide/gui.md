# GUI の使い方

## 起動

配布パッケージを使う場合:

```console
nyxpy gui
```

リポジトリの内容を直接使う場合:

```console
uv run nyxpy gui
```

`nyx-gui` でも同じ GUI を起動できます。

起動すると、コマンドを実行したディレクトリまたは親ディレクトリから workspace が探されます。workspace がない場所で起動した場合は、その場所が新しい workspace として初期化されます。既存 workspace を使う場合は、対象ディレクトリへ移動してから起動してください。

## 初回の流れ

1. workspace で `nyxpy init` を実行する。
2. キャプチャデバイスと controller backend 用デバイスを接続する。`serial` ならシリアル通信デバイス、`swbt` なら専用 USB Bluetooth adapter を使う。
3. `nyxpy gui` を起動する。
4. `設定` でキャプチャデバイスと controller backend を選ぶ。
5. `リロード` でマクロ一覧を更新する。
6. 実行するマクロを選んで `実行` を押す。

![NyX GUI の画面例](../assets/sample_macro_screenshot.png)

画面例では、左側にマクロ一覧と操作ボタン、中央にプレビュー、下部にコントローラー表示とマクロログ、右側にツールログが表示されています。

## 画面の見方

| 領域 | 用途 |
|------|------|
| マクロ一覧 | workspace の `macros/` から読み込んだマクロを表示する |
| `リロード` | マクロを追加・更新した後に一覧を読み直す |
| `実行` | 選択中のマクロを開始する |
| `実行` 横のメニュー | `--define` 相当のパラメータを GUI から入力して実行する |
| `停止` | 実行中のマクロへ中断を要求する |
| `スナップショット` | 現在のプレビュー画像を `snapshots/` に保存する |
| `設定` | デバイス、通知、ログ、表示設定を変更する |
| マクロログ | マクロ実行中の利用者向けログを表示する |
| ツールログ | デバイス接続や設定反映など、NyX 本体側のログを表示する |

## controller backend の設定

`設定` のデバイス設定で `Controller Backend` を選びます。

| backend | 使うもの |
|---------|----------|
| `serial` | CH552 などのシリアル通信デバイス |
| `swbt` | Bumble が直接開く専用 USB Bluetooth adapter |

`swbt` を選んだ場合は、次の項目を設定します。

| 項目 | 内容 |
|------|------|
| Controller | `Pro Controller`、`Joy-Con L`、`Joy-Con R` |
| Adapter | `リロード` で候補を取得し、使う adapter を選ぶ |
| Key Store | pairing key の保存先 |
| Pair | 初回 pairing を実行する |
| Reconnect | 保存済み key store で再接続する |
| Disconnect | GUI が管理する swbt session を閉じる |
| Status | `GamepadStatus.connection_state` に基づく GUI session の状態 |

adapter は候補が 1 件でも自動採用されません。`Pair` と `Reconnect` の前に明示的に選んでください。保存済み alias が候補に一致した場合は代表名へ正規化されます。候補の更新に失敗した場合、保存済み値と更新前の選択は消去されません。

adapter 更新、`Pair`、`Reconnect`、`Disconnect`、マクロ開始は background worker で処理されます。処理中は対象操作が無効になり、GUI の表示更新は処理完了後に行われます。

`Pair` または `Reconnect` の完了後、実際の接続状態が `connected` で、手動入力用 controller port を取得できた場合だけ、下部の仮想コントローラーから button / D-pad / stick を送れます。送信に失敗した場合はエラーを表示し、失敗した port を切り離します。その後は `Reconnect` してください。

controller port がない間、接続処理中、マクロ実行中は GUI の仮想コントローラー操作自体が無効になります。マクロ開始時に GUI の手動入力用 controller を解放し、マクロ用 controller に切り替えます。マクロ完了後に手動入力を使う場合は、必要に応じて `Reconnect` を実行してください。

## マクロの配置

利用者が実行するマクロは workspace の `macros/` と `resources/` に置きます。

```text
macros/sample_macro/
  macro.py

resources/sample_macro/
  settings.toml
  assets/
```

`examples/macros` と `examples/resources` は参照用サンプルです。利用者の配置先ではありません。

マクロを配置した後に GUI を開いている場合は、`リロード` を押して一覧を更新します。マクロが表示されない場合は、[トラブルシューティング](troubleshooting.md) の「マクロが見つからない」を確認してください。

## パラメータ付きで実行する

`実行` ボタン右側のメニューから `パラメータ付きで実行` を選ぶと、マクロへ渡す `key=value` を入力できます。入力できる項目名と値はマクロごとに異なるため、マクロ配布元の説明を確認してください。

## プレビューとスナップショット

GUI のプレビュー領域にキャプチャ中の画面が表示されます。スナップショットは workspace の `snapshots/` に保存されます。

プレビューが表示されない場合は、[トラブルシューティング](troubleshooting.md) の「プレビューが表示されない」を確認してください。

## ログを確認する

GUI のログ欄に加えて、workspace の `logs/` と `runs/` に実行ログが保存されます。Issue や相談にログを貼る場合は、通知 URL、token、個人名、端末固有の情報が含まれていないか確認してください。
