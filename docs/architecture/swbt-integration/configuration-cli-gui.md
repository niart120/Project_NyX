# 設定、依存関係、CLI、GUI

この文書は、swbt backend を利用者が選べるようにするための設定形式、依存関係、CLI command、GUI 項目を定義する。

設定 model、controller 種別 model、adapter refresh は `nyxpy.framework.core.hardware.swbt` package に置く。

## 依存関係

`swbt-python==0.6.0` は通常依存として固定する。`[project.optional-dependencies].swbt` は作らない。lockfile 上の Bumble は `0.0.233` とする。

NyX はすでに serial backend のために PySerial を通常依存として持つ。swbt backend も controller backend の正式な選択肢として扱い、利用者に swbt 用の extra 指定や追加同期手順を要求しない。

## settings

serial backend:

```toml
[controller]
backend = "serial"

[controller.serial]
device = "COM3"
protocol = "CH552"
baudrate = 9600
```

swbt backend:

```toml
[controller]
backend = "swbt"

[controller.swbt]
controller_type = "pro-controller"
adapter = "usb:0"
profile_path = ".nyxpy/swbt/pro-controller-profile.json"
connect_timeout_sec = 30.0
```

`controller.backend` は `serial` または `swbt` を指定する。capture backend / capture source とは独立して扱う。

`controller_type` は `pro-controller`、`joy-con-l`、`joy-con-r` のいずれか。settings parser で `SwbtControllerType` に parse し、`SwbtControllerModel` に変換する。

`adapter` は swbt が開く USB Bluetooth adapter 名である。空文字または未指定のまま pair / reconnect / run を試みた場合は、候補数に関係なく `NYX_SWBT_ADAPTER_NOT_SELECTED` とする。adapter 候補が 1 件だけでも自動採用しない。

`profile_path` は swbt-python schema v2 pairing profile である。明示されない場合は controller type ごとに `.nyxpy/swbt/<controller>-profile.json` を使う。相対 path はコマンドを実行した子 directory ではなく workspace root を基準に解決する。

```text
.nyxpy/swbt/pro-controller-profile.json
.nyxpy/swbt/joy-con-l-profile.json
.nyxpy/swbt/joy-con-r-profile.json
```

`connect_timeout_sec` は接続操作ごとのtimeoutである。swbt backendは直接送信型へ統一し、送信周期の設定は持たない。

`operation_timeout_sec` と `reset_on_port_create` は settings に出さない。operation timeout は session / factory の内部既定値とし、port 作成時の neutral は常に試みる。

## CLI

追加する CLI:

```console
nyxpy swbt adapters [--json]
nyxpy swbt pair [--adapter usb:0] [--controller-type pro-controller] [--profile .nyxpy/swbt/pro-controller-profile.json]
nyxpy swbt reconnect [--adapter usb:0] [--controller-type pro-controller] [--profile .nyxpy/swbt/pro-controller-profile.json]
```

`pair` と `reconnect` は workspace settings を読み、CLI option が指定された場合だけ上書きする。解決後に adapter が空なら `NYX_SWBT_ADAPTER_NOT_SELECTED` とする。指定 adapter は discovery 結果の `name` / `aliases` から代表 `name` へ正規化する。不一致と曖昧 alias はそれぞれ `NYX_SWBT_ADAPTER_NOT_FOUND` / `NYX_SWBT_ADAPTER_AMBIGUOUS` とする。候補が 1 件でも未指定値を補わない。`profile_path` が未指定なら controller type から既定値を補う。

旧設定を読み込んだ場合は旧 path を新 profile の path として流用せず、controller type ごとの既定 profile path へ切り替える。旧 JSON は変換・削除・上書きしない。schema v1 も読み込まず、利用者へ再ペアリングを要求する。

run option:

```console
nyxpy run sample_macro --controller swbt --swbt-adapter usb:0 --swbt-controller-type pro-controller
```

`--controller serial|swbt` は controller backend の選択だけを扱う。capture backend / capture source の選択とは独立している。

`--serial` と `--capture` は parser 上の必須 option にしない。未指定時は settings に fallback し、解決後の設定を検証する。

`swbt` の CLI に `status` と `disconnect` は提供しない。CLI は command ごとに fresh factory を作る別 process であり、前回 process の cached session を disconnect できない。接続を閉じる操作は同じ factory lifetime を持つ GUI の「切断」 で行う。

失敗時は利用者向け本文と `NYX_SWBT_*` error code の両方をコンソールへ出す。

CLI は GUI 連携用の command copy や clipboard 出力を持たない。

## GUI 項目

GUI swbt panel に置く項目:

| 項目 | 必須 | 内容 |
|---|---:|---|
| controller backend selector | yes | serial / swbt |
| controller type | yes | Pro Controller / Joy-Con L / Joy-Con R |
| adapter combo | yes | `list_adapters()` の結果 |
| refresh adapters | yes | adapter 列挙だけ行う |
| 接続操作 | yes | 「ペアリング」「接続」「切断」「キャンセル」を常設し、有効・無効だけを変更 |

プロファイルの選択欄と独立した状態行は設けない。GUI は設定の `profile_path` を使用し、未指定ならタイプごとの既定パスへ保存する。タイプ変更時は既定パスだけを追従させ、明示されたカスタムパスは保持する。CLI の `--profile` は引き続き操作対象の指定に使用できる。

設定画面と接続メニューは同じ有効状態の判定を使う。未接続時は「ペアリング」を有効にし、プロファイルがあれば「接続」も有効にする。接続中は「切断」、ペアリング・再接続処理中は「キャンセル」だけを有効にする。キャンセル要求後と切断処理中は全操作を無効にする。ラベルや操作の並びは変更しない。

登録済みでも「ペアリング」は同じパスのプロファイルを更新し、別名ファイルを増やさない。失敗・キャンセル後は接続状態とプロファイルの存在を再評価する。再接続失敗から自動でペアリングへ切り替えない。

capture backend / capture source の選択 UI は controller backend と独立させる。controller backend を変更しても preview frame source は再作成しない。capture backend を変更しても manual controller port は再作成しない。

GUI に置かない項目:

- CLI command preview
- clipboard copy
- CLI history 連携
- diagnostics editor
- diagnostics folder open button
- controller color editor
- auto pairing suggestion
- IMU preset / pose / raw editor
- IMU recorder / replay

## GUI operation

| operation | enabled when | success | failure |
|---|---|---|---|
| アダプター再検索 | 未接続・操作中でなく macro 未実行 | combo を更新。settings は変更しない | 選択を保持しツールログへ記録 |
| ペアリング / 接続 | backend `swbt`、adapter 選択済み、未接続、操作中でなく macro 未実行 | manual controller を注入し「切断」を有効化 | 操作を戻しツールログへ記録 |
| 切断 | connected、操作中でなく macro 未実行 | `release()` 後に `close()`、factory session を閉じ、controller `None` | controller を外しツールログへ記録 |
| Macro run start | not pairing/reconnecting | `VirtualControllerModel.set_controller(None)` 後に旧 manual port を release/close して runtime start | close 失敗時は実行を止める |

adapter refresh、pair、reconnect、disconnect、manual port 作成、macro start は worker thread で実行する。widget 更新は main thread に戻す。`pair()` / `reconnect()` の戻り値は `None` なので、成功は操作後の `status.connection_state == "connected"` と manual port の準備完了で判断する。

接続済み・接続操作中・macro 実行中は backend、adapter、controller type の変更を禁止する。接続操作中は設定画面の「適用」「OK」も無効にする。接続ボタンを押すと現在の選択を保存して即時実行する。設定画面の「キャンセル」は実行済みの接続操作と保存を巻き戻さない。接続操作をせずに設定画面をキャンセルした場合は編集値を保存しない。

adapter refresh の候補が 1 件でも combo で自動選択しない。保存済み adapter が discovery 結果の alias に一致する場合は代表 `name` へ正規化する。

接続操作の失敗理由・エラーコードは既存ツールログへ一度だけ記録し、状態行・ステータスバー・エラーダイアログに重複表示しない。複合例外は各原因を本文へ含める。キャンセルは失敗として記録しない。ペアリング開始時の Switch 側の「持ちかた／順番を変える」を開く案内もツールログに出す。

## GUI manual input

GUI manual input は既存仮想コントローラー UI で行う。

```text
VirtualControllerModel
  -> ControllerOutputPort
  -> SwbtControllerOutputPort
```

GUI view model は `SwbtControllerSession` や `InputState` を直接扱わない。

manual input widget は controller port が存在し、macro 非実行、lifecycle worker 非実行の場合だけ有効にする。port 操作が失敗した場合は利用者向け error を表示し、失敗した port を model から外す。

## Settings validation

| field | validation |
|---|---|
| `controller.backend` | `serial` or `swbt` |
| `controller.swbt.controller_type` | `resolve_controller_model(...)` で解決できる |
| `controller.swbt.adapter` | 保存時は空を許容する。接続操作時に空なら `NYX_SWBT_ADAPTER_NOT_SELECTED` |
| `controller.swbt.profile_path` | `Path | None`。`None` なら controller type から既定値を補う。親 directory は pair 前に作成 |
| `connect_timeout_sec` | `> 0` |

旧 flat key の `serial_device`、`serial_baud`、`serial_protocol` は廃止する。settings parser は新しい `[controller.serial]` を正とし、旧 key への fallback は持たない。

## エラー案内（GUI はツールログ、CLI はコンソール）

| code | 表示 |
|---|---|
| `NYX_SWBT_ADAPTER_DISCOVERY_FAILED` | adapter discovery failed |
| `NYX_SWBT_ADAPTER_NOT_SELECTED` | adapter を選択させる |
| `NYX_SWBT_ADAPTER_NOT_FOUND` | 選択 adapter が見つからない |
| `NYX_SWBT_ADAPTER_AMBIGUOUS` | adapter alias が複数候補に一致している |
| `NYX_SWBT_CONTROLLER_TYPE_UNSUPPORTED` | controller type を選択させる |
| `NYX_SWBT_PROFILE_NOT_FOUND` | 「ペアリング」で profile を新規作成する |
| `NYX_SWBT_PROFILE_ALREADY_EXISTS` | 既存 profile で Pair を再試行するか path を変更させる |
| `NYX_SWBT_PROFILE_INVALID` | schema と profile path を確認させる |
| `NYX_SWBT_PROFILE_CONTROLLER_MISMATCH` | controller type と profile の対応を確認させる |
| `NYX_SWBT_PROFILE_KEY_DATA_INVALID` | 別 path で再ペアリングさせる |
| `NYX_SWBT_ADAPTER_IDENTITY_RECOVERY_REQUIRED` | USB Bluetooth ドングルを抜き差しさせる |
| `NYX_SWBT_CONNECTION_TIMED_OUT` | target device の pairing/reconnect 操作を確認させる |
| `NYX_SWBT_CONNECTION_FAILED` | connection failed |
| `NYX_SWBT_INPUT_UNSUPPORTED` | 選択 controller type ではその入力を扱えない |
| `NYX_SWBT_INPUT_INVALID` | 入力値または型が不正 |
| `NYX_IMU_FRAME_COUNT_INVALID` | IMU frame 数が 1 または 3 ではない |
