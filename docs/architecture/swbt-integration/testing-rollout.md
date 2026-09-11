# Testing / rollout plan

swbt backend は、設定 model、adapter discovery、session、port、runtime integration、GUI 接続操作、実機接続の順に導入する。

## 導入順序

1. `swbt-python==0.5.4` を通常依存として固定する。
2. `nyxpy.framework.core.hardware.swbt` package を追加する。
3. `SwbtControllerType` / `SwbtControllerModel` / capabilities / `SwbtControllerConfig` を `config.py` に定義する。
4. `ControllerOutputPort.imu(...)` と `Command.imu(...)` を既定 unsupported として追加する。
5. `SwbtAdapterDiscoveryService` を追加し、CLI `nyxpy swbt adapters` を実装する。
6. `SwbtControllerSession` と fake session を追加する。
7. `NyxSwbtInputMapper` に button / D-pad / stick / IMU mapping を追加する。
8. `SwbtControllerOutputPort` を追加する。
9. `SwbtControllerOutputPortFactory` を追加し、macro 用 port と GUI lifetime port の両方を生成できるようにする。
10. runtime builder の構成起点で serial / swbt の factory 選択を行う。
11. CLI `nyxpy swbt pair` / `nyxpy swbt reconnect` を追加する。別 process の cached session を閉じられない CLI `disconnect` は追加しない。
12. GUI に adapter refresh、controller type、pair、reconnect、disconnect を追加する。
13. 既存 `VirtualControllerModel` へ swbt port が差し込まれることを確認する。
14. 実機 test で Pro Controller / Joy-Con L / Joy-Con R の接続と入力を確認する。

## 完了条件

```text
[ ] swbt 固有実装が nyxpy.framework.core.hardware.swbt に収まっている
[ ] swbt_*.py という module が増えていない
[ ] hardware/swbt/manual.py が存在しない
[ ] SwbtManualInputSession が存在しない
[ ] SwbtGamepadService と SwbtControllerSession が二重化していない
[ ] runtime config に controller_type 文字列 field が残っていない
[ ] Literal による controller 種別分岐がない
[ ] CLI / GUI choices が supported_controller_models() から導出される
[ ] list_adapters() が GUI / CLI から使える
[ ] adapter refresh が controller の open / pairing / reconnect を開始しない
[ ] macro run で pairing が暗黙実行されない
[ ] Command.imu(...) が追加されている
[ ] 非対応 backend の imu(...) が NotImplementedError になる
[ ] swbt backend が IMUFrame を InputState.with_imu(...) に入れられる
[ ] GUI manual input が既存 VirtualControllerModel -> ControllerOutputPort 経路を使う
[ ] GUI model が swbt を import しない
[ ] GUI manual input と macro runtime が同じ adapter を同時に開かない
[ ] GUI に clipboard / CLI command 生成がない
[ ] GUI に diagnostics editor / controller color editor がない
[ ] GUI manual input に IMU gesture / pose / raw frame editor がない
[ ] Joy-Con type ごとの unsupported input が明確に失敗する
[ ] close 時に neutral を試みる
[ ] swbt が通常依存であり、`[project.optional-dependencies].swbt` がない
[ ] adapter 未指定時に自動採用せず `NYX_SWBT_ADAPTER_NOT_SELECTED` になる
[ ] pairing profile 未指定時に `.nyxpy/swbt/<controller>-profile.json` を使う
[ ] 相対 pairing profile path が workspace root 基準で解決される
[ ] pair / reconnect 後の接続判定が `GamepadStatus.connection_state` に基づく
[ ] GUI の swbt lifecycle と macro start が worker thread で実行される
[ ] GUI manual input が port なし、macro 実行中、lifecycle 操作中に無効になる
[ ] swbt diagnostics が production の technical log へ流れる
[ ] 実機 test が `@pytest.mark.realdevice` と環境変数 gate で制御される
[ ] 実機 evidence が `tmp/hardware/swbt/<timestamp>/` に残る
```

## リスクと対策

| リスク | 対策 |
|---|---|
| adapter 名が接続状態で変わる | `list_adapters()` の結果で `aliases` と VID/PID も表示する |
| pairing profile に複数候補が入る | controller type と対象機器ごとに file を分け、`InvalidKeyStoreError` を明示表示する |
| GUI manual input と macro runtime が競合する | macro start 前に GUI lifetime port を release/close する |
| IMU command が非対応 backend で silent no-op になる | 共通 default を `NotImplementedError` にする |
| Joy-Con type で存在しない入力を送る | `SwbtControllerModel.capabilities` で mapper が拒否する |
| 短い押下がSwitch側で認識されない | Direct送信のtraceと画面観察を分け、確認済みの最小durを文書へ反映する |
| diagnostics が GUI の通常機能として肥大化する | production composition root から writer を注入して `LoggerPort.technical(...)` に流し、GUI / CLI / settings には path を出さない |

## 実機確認 checklist

```text
Adapter discovery
  [ ] adapter が 1 件以上表示される
  [ ] aliases / VID/PID が表示される
  [ ] refresh だけでは pairing 待ち受けが開始されない

Pair / reconnect
  [x] Pro Controller で pair 成功
  [x] 同じ pairing profile で reconnect 成功
  [x] Joy-Con L で pair/reconnect 成功
  [x] Joy-Con R で pair/reconnect 成功
  [x] invalid pairing profile が明確に表示される
  [x] GUI Disconnect が factory-managed cached session を閉じる

Macro input
  [x] Button.A press/release
  [x] 16ms / 33ms / 50ms のA短押しを各5回確認（同一構成での最小確認値は16ms。一般保証ではない）
  [x] D-pad input を確認（`UPRIGHT` は右上として反映）
  [x] left stick / right stick
  [x] Command.imu(...) による IMU neutral / gyro frame を送信し、切断・想定外入力がないことを確認（gyro 値自体の画面上の反映は未確認）
  [x] release all / close neutral

GUI manual input
  [x] reconnect 後に virtual controller が有効になる
  [x] button down/up が反映される
  [x] D-pad が反映される
  [x] stick が反映される
  [x] macro start 前に GUI lifetime port が閉じられる
  [x] GUI に IMU 操作 UI がない
```

## local_029 実機確認結果

unit、CLI、GUI の非実機 gate では mapping と lifecycle 境界を確認する。次の項目は Switch、専用 USB Bluetooth adapter、operatorを使って確認した。

```text
[x] Pro Controller / Joy-Con L / Joy-Con R の pair / reconnect
[x] NyX `0..255`、Y-down から `Stick.normalized`、Y-up への変換が実機で上方向に反映されること
[x] Joy-Con L / Rの`SL` / `SR` とPro Controller D-padの右成分
[x] Direct送信型short pressの再現性（16ms / 33ms / 50msを各5回）
[x] GUI manual inputの画面反映
[x] schema v1 pairing profileで `NYX_SWBT_PROFILE_INVALID` が表示され、manual inputが無効のままになること
```

座標変換規則自体は単体テストで固定する。Switch 画面では左右 stick の上方向と、D-padの`UPRIGHT`が右上として反映されることを確認した。

Direct送信型の実機確認では、CSR8510 A10、swbt-python 0.5.4、Bumble 0.0.233、Switch 2で16ms・33ms・50msのA短押しを各5回認識した。16msはこの構成での最小確認値だが、Bluetooth環境や画面状態をまたぐ最小値としては保証しない。
