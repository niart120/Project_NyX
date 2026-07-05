# swbt-python 連携設計

この文書群は、Project_NyX に `swbt-python` を組み込み、Bluetooth HID 経由の NX 互換コントローラー入力を NyXPy の既存マクロ API から使えるようにするための設計です。

設計の中心は、`swbt-python` を `SerialProtocolInterface` に入れないことです。`swbt-python` はシリアル送信用 bytes を作る部品ではなく、Bluetooth HID デバイスとしての接続、pairing、reconnect、入力状態、周期 report loop を持つ部品です。NyXPy 側では `ControllerOutputPort` の具象実装として扱います。

## 目的

既存マクロを変更せず、次のような `Command` API をそのまま使える状態にします。

```python
cmd.press(Button.A, dur=0.06, wait=0.08)
cmd.hold(Button.ZL)
cmd.release()
frame = cmd.capture()
```

利用者は設定または CLI / GUI で controller backend を `serial` または `swbt` から選びます。マクロ、`DefaultCommand`、`ExecutionContext`、`MacroRuntime` は `ControllerOutputPort` だけへ依存します。

## 設計判断

| 判断 | 採用方針 |
|---|---|
| swbt の配置 | `ControllerOutputPort` の具象 adapter として追加する |
| serial protocol への追加 | しない |
| 実行時の振り分け port | 置かない |
| backend 選択 | runtime builder を作る構成起点で一度だけ行う |
| マクロ API | 変更しない |
| swbt import | `hardware/swbt_*` と `io/swbt_adapter.py` 付近へ閉じ込める |
| 依存追加 | `swbt` extra dependency として追加する |

「実行時の振り分け port を置かない」とは、`press()` や `release()` のたびに backend を見て分岐する `ControllerOutputPort` を作らない、という意味です。具象 port の選択は起動時に済ませ、実行中は `ControllerOutputPort` の抽象で隠蔽します。

## 文書構成

| 文書 | 読む場面 |
|---|---|
| [architecture.md](architecture.md) | どの層に何を置くかを確認する |
| [runtime-composition.md](runtime-composition.md) | factory 名、builder、manual input の扱いを決める |
| [controller-port-contract.md](controller-port-contract.md) | `press` / `hold` / `release` の意味を実装する |
| [swbt-service.md](swbt-service.md) | 非同期 `SwitchGamepad` を NyXPy の同期 API へ接続する |
| [input-mapping.md](input-mapping.md) | button、hat、stick の変換を書く |
| [configuration-cli-gui.md](configuration-cli-gui.md) | 設定ファイル、CLI、GUI を追加する |
| [testing-rollout.md](testing-rollout.md) | テストと段階導入を進める |

## 対象範囲

この設計で扱うもの:

- `swbt-python` を NyXPy の controller output backend として使うこと
- serial backend と swbt backend の切り替え
- 既存 `Command` API の互換性維持
- 初回 pairing と reconnect の設定
- adapter probe、diagnostics trace、実機テスト方針

この設計では扱わないもの:

- `swbt-python` の Bluetooth HID protocol 実装そのものの変更
- NyXPy マクロ API への新規高水準 action API 追加
- motion / IMU 入力を NyXPy の公開 API として設計すること
- 3DS touch / sleep control を swbt backend で代替すること

## 用語

| 用語 | 意味 |
|---|---|
| controller backend | NyXPy の controller 出力実装。`serial` または `swbt` |
| port | runtime が依存する抽象インターフェース |
| adapter | port を満たす具象実装 |
| service | 外部ライブラリや実デバイスの lifecycle を隠す部品 |
| 構成起点 | 設定を読み、具象 factory を選び、runtime builder へ注入する場所 |

## 参照元

- Project_NyX `ControllerOutputPort`: https://github.com/niart120/Project_NyX/blob/master/src/nyxpy/framework/core/io/ports.py
- Project_NyX `MacroRuntimeBuilder`: https://github.com/niart120/Project_NyX/blob/master/src/nyxpy/framework/core/runtime/builder.py
- Project_NyX `SerialProtocolInterface`: https://github.com/niart120/Project_NyX/blob/master/src/nyxpy/framework/core/hardware/protocol.py
- swbt-python public API: https://niart120.github.io/swbt-python/api/
- swbt-python usage guide: https://niart120.github.io/swbt-python/usage/
