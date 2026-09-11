# swbt 実機検証の残課題

## 目的

`local_026` で整備・記録したDirect送信型swbt backendについて、未確定の画面反映を専用実機環境で確定する。実装済みのPair / Reconnect・入力送信・docsを再実装する作業ではない。

## 前提

- Switch、CSR8510 A10相当の専用USB Bluetooth adapter、キャプチャ入力、operatorを用意する。
- `NYX_REALDEVICE=1`、`NYX_SWBT=1`、adapter、controller type、controller別profileを明示する。
- 各実行のmetadata、Direct report trace、operator confirmation、summaryをevidence directoryへ保存する。

## 確定対象

| 対象 | 判定 | 証跡 |
|---|---|---|
| Joy-Con Lの`SL` / `SR` | 各入力の押下・解放が画面へ反映される | Direct reportとoperator confirmation |
| Joy-Con Rの`SL` / `SR` | 各入力の押下・解放が画面へ反映される | Direct reportとoperator confirmation |
| Pro Controller D-padの右成分 | `UPRIGHT`が上だけでなく右成分を含むと区別できる画面で確認する | Direct reportとoperator confirmation |
| short press | 16ms、33ms、50msを同一条件で複数回試行し、duration別の成功数を記録する | 試行ごとのDirect reportとoperator confirmation |
| 推奨duration | short pressの結果から、再現性の根拠を持つ値だけを利用者docsへ記載する。安定値が得られなければ保証しない | 集計summaryとdocs差分 |
| GUI manual input | reconnect後の有効化、button、D-pad、stick、macro開始前のlifetime port解放を画面で確認する | GUI操作記録とoperator confirmation |

## 完了条件

- すべての確定対象にpass / fail / skipと根拠を残す。
- 推奨durationを保証できない場合、その結論と条件をdocsへ明記する。
- `docs/architecture/swbt-integration/testing-rollout.md` の実機チェックリストを結果と一致させる。
- `uv run pytest tests -m "not realdevice and not swbt"` と `uv run mkdocs build --strict` が成功する。

## 2026-09-11 実機結果

CSR8510 A10（`usb:0`）、swbt-python 0.5.4、Bumble 0.0.233、Switch 2で確認した。PairはHOMEの「コントローラー」から「持ちかた/順番を変える」を開いている間に実行する。単にコントローラー画面を開いているだけではSwitchから接続要求が来ず、Pairはtimeoutする。

| 対象 | 結果 | 証跡 |
|---|---|---|
| Joy-Con Lの`SL` / `SR` | pass | `local029-joy-con-l-side-buttons-confirmed` |
| Joy-Con Rの`SL` / `SR` | pass | `local029-joy-con-r-side-buttons-confirmed` |
| Pro Controllerの`UPRIGHT` | pass。右上として反映 | `local029-pro-controller-dpad-short-press-confirm` |
| Pro ControllerのA短押し | 16ms、33ms、50msを各5回送信し、各5回を認識 | `local029-pro-controller-dpad-short-press-confirm` |

この構成では16msを最小の確認済みdurationとする。ただしBluetooth環境やSwitch画面の状態をまたぐ一般保証ではないため、利用者向けdocsで固定の最小値として保証しない。

GUI manual inputは、Reconnect後の有効化、button / D-pad / stickの画面反映、macro開始前のGUI lifetime port解放をoperatorが確認した。IMU操作UIは存在しない。

GUIにschema v1の一時profileを指定してReconnectしたところ、`NYX_SWBT_PROFILE_INVALID` が表示され、manual inputは無効のままになった。既存profileには触れず、検証用fileは確認後に削除した。

以上により、この仕様の確定対象と完了条件を満たした。
