# swbt 連携

この文書群は、Project_NyX から `swbt-python` を controller backend として利用するための設計方針を定義する。

`swbt-python` は NX 互換の仮想 Bluetooth HID controller を Python から扱うための library である。Project_NyX では、Bluetooth adapter の列挙、pairing、保存済み pairing key に基づく reconnect、入力 report の送信を controller backend の実装として扱う。マクロ作者から見える通常 API は `Command`、GUI の仮想コントローラーから見える境界は既存の `ControllerOutputPort` に止める。

## 最小構成

```toml
[controller]
backend = "swbt"

[controller.swbt]
controller_type = "pro-controller"
adapter = "usb:0"
key_store_path = ".nyxpy/swbt/pro-controller-bond.json"
connect_timeout_sec = 30.0
report_period_us = 8000
```

`controller_type` は settings / CLI / GUI の境界でだけ文字列として扱う。runtime 内部では `SwbtControllerType` と `SwbtControllerModel` に正規化し、`Literal[...]` や raw string key による controller class dispatch を残さない。

`swbt-python` は通常依存である。利用者に swbt 用の extra 指定や追加同期手順を求めない。

`adapter` が空文字または未指定のまま接続操作を行った場合は、候補が 1 件でも自動採用せず `NYX_SWBT_ADAPTER_NOT_SELECTED` とする。`key_store_path` が未指定なら `.nyxpy/swbt/<controller>-bond.json` を使う。

## 入力反映の基本方針

swbt backend は、GUI 仮想コントローラー専用の入力 session を追加しない。

現行の GUI はすでに次の経路で十分に抽象化されている。

```text
GUI widget
  -> VirtualControllerPane
  -> VirtualControllerModel
  -> ControllerOutputPort
```

swbt 対応後もこの経路を維持する。

```text
GUI widget
  -> VirtualControllerPane
  -> VirtualControllerModel
  -> ControllerOutputPort
  -> SwbtControllerOutputPort
  -> hardware.swbt.SwbtControllerSession
  -> swbt-python controller
```

serial backend では次のままになる。

```text
GUI widget
  -> VirtualControllerPane
  -> VirtualControllerModel
  -> ControllerOutputPort
  -> SerialControllerOutputPort
  -> SerialProtocolInterface
  -> SerialComm
```

`SwbtControllerSession` は GUI manual input 用の上位機能ではない。`swbt-python` の async controller lifecycle と `InputState.apply()` を同期 port 実装から扱うための backend 内部部品である。`status()` は同期 API であり、pair / reconnect 後の `connection_state` を接続判定に使う。

## GUI の範囲

GUI の swbt 設定画面に置く機能は、実機運用に必要なものに絞る。

| 機能 | 目的 |
|---|---|
| デバイス一覧取得 / 更新 | `list_adapters()` で利用可能な dedicated USB Bluetooth adapter 候補を表示する |
| コントローラー種別指定 | Pro Controller / Joy-Con L / Joy-Con R を選ぶ |
| ペアリング | 選択した adapter、controller type、key store path で pairing する |
| pairing key に基づく reconnect | 保存済み key store を使って reconnect する |
| 仮想コントローラー manual input | 既存 `VirtualControllerModel` から `ControllerOutputPort` へ button / D-pad / stick を送る |

GUI と CLI の間で値を受け渡すための clipboard 機能、CLI command 生成、CLI 実行履歴との連携、diagnostics folder を開く導線、controller color editor は持たせない。

manual input は GUI の仮想コントローラー操作として扱う。マクロ生成や CLI 補助ではなく、接続確認、メニュー操作、実機状態の調整に使う直接入力である。IMU 操作 UI は含めない。

## IMU 入力

`Command` と `ControllerOutputPort` には IMU 入力命令を追加する。

```python
cmd.imu(IMUFrame.gyro(x=100, y=0, z=0))
cmd.imu(IMUFrame.neutral())
```

swbt backend は `swbt.IMUFrame` と `InputState.with_imu(...)` へ変換して送信する。IMU を扱わない backend は silent no-op にせず、既定実装で `NotImplementedError` を送出する。

GUI manual input では IMU を直接操作しない。preset gesture、pose editor、raw frame editor、replay / recording は対象外とする。

## 主要な設計判断

| 項目 | 方針 |
|---|---|
| package | `nyxpy.framework.core.hardware.swbt` に swbt 固有実装を集約する |
| module 名 | package で namespace を切るため `swbt_*.py` にはしない |
| controller type | `SwbtControllerType` / `SwbtControllerModel` で扱い、文字列は設定境界で解決する |
| adapter refresh | Python API の `list_adapters()` を直接呼ぶ |
| pairing | 明示操作として扱い、通常の macro run では勝手に pairing しない |
| reconnect | key store に保存済み pairing 情報があることを前提にする |
| disconnect | factory lifetime を維持する GUI から cached session を明示的に閉じる。fresh factory を作る CLI command は提供しない |
| input | NyX state から `InputState` を構成し、`apply(state)` を使う |
| manual input | 既存 `VirtualControllerModel` と `ControllerOutputPort` 経路を使う |
| unsupported input | silent no-op にせず明示的に失敗させる |
| diagnostics | swbt diagnostics writer を NyX の `LoggerPort.technical(...)` へ流す。GUI / CLI / settings に path は出さない |

## 文書一覧

| 文書 | 内容 |
|---|---|
| [architecture.md](architecture.md) | package 配置、依存方向、import policy |
| [abstraction-audit.md](abstraction-audit.md) | 余計な抽象レイヤーを入れていないかの自己検証 |
| [public-api.md](public-api.md) | Project_NyX が使う `swbt-python` 公開 API |
| [controller-models.md](controller-models.md) | controller type の domain model と registry |
| [adapter-discovery.md](adapter-discovery.md) | `list_adapters()` と `AdapterInfo` の扱い |
| [runtime-composition.md](runtime-composition.md) | runtime builder、factory、GUI lifetime controller |
| [controller-session.md](controller-session.md) | `SwbtControllerSession` の責務と connection lifecycle |
| [manual-input.md](manual-input.md) | GUI 仮想コントローラー manual input |
| [imu-command.md](imu-command.md) | `Command.imu(...)` と backend 対応方針 |
| [controller-port-contract.md](controller-port-contract.md) | `ControllerOutputPort` と swbt input API の対応 |
| [input-mapping.md](input-mapping.md) | Button / Hat / Stick / IMU の mapping と controller type 制約 |
| [configuration-cli-gui.md](configuration-cli-gui.md) | settings、CLI、GUI の仕様 |
| [testing.md](testing.md) | unit / session / CLI / GUI / 実機 test |
| [testing-rollout.md](testing-rollout.md) | 導入順序、完了条件、リスク |

## 対象範囲

対象に含めるもの:

- swbt backend の controller 出力
- dedicated USB Bluetooth adapter の列挙
- Pro Controller / Joy-Con L / Joy-Con R の選択
- pairing と key store への保存
- 保存済み pairing key に基づく reconnect
- GUI が管理する cached session の disconnect
- `ControllerOutputPort` からの button / D-pad / stick / IMU 入力
- GUI 仮想コントローラーによる manual input

対象に含めないもの:

- 3DS touch、keyboard、sleep control を swbt backend で代替すること
- 左右 Joy-Con を 1 つの controller として扱うこと
- GUI から CLI 用の値を生成・コピーすること
- GUI で swbt diagnostics や controller colors を編集すること
- CLI / GUI / settings に diagnostics path を公開すること
- GUI manual input から IMU gesture / pose / raw frame を送ること
- PC の通常 Bluetooth stack をそのまま使うこと
