# Testing / rollout plan

swbt backend は、設定 model、adapter discovery、session、port、runtime integration、GUI 接続操作、実機接続の順に導入する。

## 導入順序

1. `swbt-python>=0.2.0,<0.3.0` を通常依存として追加する。
2. `nyxpy.framework.core.hardware.swbt` package を追加する。
3. `SwbtControllerType` / `SwbtControllerModel` / capabilities / `SwbtControllerConfig` を `config.py` に定義する。
4. `ControllerOutputPort.imu(...)` と `Command.imu(...)` を既定 unsupported として追加する。
5. `SwbtAdapterDiscoveryService` を追加し、CLI `nyxpy swbt adapters` を実装する。
6. `SwbtControllerSession` と fake session を追加する。
7. `NyxSwbtInputMapper` に button / D-pad / stick / IMU mapping を追加する。
8. `SwbtControllerOutputPort` を追加する。
9. `SwbtControllerOutputPortFactory` を追加し、macro 用 port と GUI lifetime port の両方を生成できるようにする。
10. runtime builder の構成起点で serial / swbt の factory 選択を行う。
11. CLI `nyxpy swbt pair` / `nyxpy swbt reconnect` / `nyxpy swbt disconnect` を追加する。
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
[ ] adapter refresh が pairing / reconnect / report loop を開始しない
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
[ ] key store 未指定時に `.nyxpy/swbt/<controller>-bond.json` を使う
[ ] 実機 test が `@pytest.mark.realdevice` と環境変数 gate で制御される
[ ] 実機 evidence が `tmp/hardware/swbt/<timestamp>/` に残る
```

## リスクと対策

| リスク | 対策 |
|---|---|
| adapter 名が接続状態で変わる | `list_adapters()` の結果で `aliases` と VID/PID も表示する |
| key store に複数候補が入る | controller type と対象機器ごとに file を分け、`InvalidKeyStoreError` を明示表示する |
| GUI manual input と macro runtime が競合する | macro start 前に GUI lifetime port を release/close する |
| IMU command が非対応 backend で silent no-op になる | 共通 default を `NotImplementedError` にする |
| Joy-Con type で存在しない入力を送る | `SwbtControllerModel.capabilities` で mapper が拒否する |
| 短い押下が report loop に載らない | 実機 test で最小 dur を確認し、ドキュメントへ反映する |
| diagnostics が GUI の通常機能として肥大化する | swbt diagnostics writer を `LoggerPort.technical(...)` に流し、GUI / CLI / settings には path を出さない |

## 実機確認 checklist

```text
Adapter discovery
  [ ] adapter が 1 件以上表示される
  [ ] aliases / VID/PID が表示される
  [ ] refresh だけでは pairing 待ち受けが開始されない

Pair / reconnect
  [ ] Pro Controller で pair 成功
  [ ] 同じ key store で reconnect 成功
  [ ] Joy-Con L で pair/reconnect 成功
  [ ] Joy-Con R で pair/reconnect 成功
  [ ] invalid key store が明確に表示される
  [ ] disconnect が factory-managed cached session を閉じる

Macro input
  [ ] Button.A press/release
  [ ] 16ms / 33ms / 50ms の短い押下を確認
  [ ] D-pad diagonal
  [ ] left stick / right stick
  [ ] Command.imu(...) による IMU neutral / gyro frame
  [ ] release all / close neutral

GUI manual input
  [ ] reconnect 後に virtual controller が有効になる
  [ ] button down/up が反映される
  [ ] D-pad が反映される
  [ ] stick が反映される
  [ ] macro start 前に GUI lifetime port が閉じられる
  [ ] GUI に IMU 操作 UI がない
```

## local_026 時点の実機未確定項目

unit、CLI、GUI の非実機 gate では mapping と lifecycle 境界を確認できる。次の項目は Switch、専用 USB Bluetooth adapter、operator がそろった環境で確定するまで未検証として扱う。

```text
[ ] Pro Controller / Joy-Con L / Joy-Con R の pair / reconnect
[ ] Stick.UP が Switch 画面上で上方向として反映されること
[ ] 16ms / 33ms / 50ms short press の安定性
[ ] public flush / send_current 相当 API が必要かどうか
```

実機で short press が取りこぼされる場合、この文書と利用者向け docs に最小推奨 duration を反映する。実機確認前の段階では、NyX は swbt backend 固有の最小押下時間を保証しない。
