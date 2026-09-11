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
