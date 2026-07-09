# swbt controller backend 実装計画 仕様書

## 1. 概要

### 1.1 目的

`swbt-python` を Project NyX の `ControllerOutputPort` backend として導入する。マクロ API は `Command` と `ControllerOutputPort` に閉じ、Bluetooth HID の接続、pairing、reconnect、入力変換、IMU 変換は `nyxpy.framework.core.hardware.swbt` package に集約する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| swbt backend | `swbt-python` を使って Nintendo Switch へ Bluetooth HID controller 入力を送る backend |
| controller backend | NyX の controller 出力方式。`serial` または `swbt` |
| `ControllerOutputPort` | Runtime が controller 入力を送る抽象 port |
| `SwbtControllerSession` | `swbt-python` の async controller lifecycle を同期 port から使う backend 内部部品 |
| `SwbtControllerModel` | Pro Controller / Joy-Con L / Joy-Con R の class、capabilities、既定 key store 名を束ねる定義 |
| `NyxSwbtInputMapper` | NyX の `Button`、`Hat`、`LStick`、`RStick`、`IMUFrame` を swbt の `InputState` へ変換する mapper |
| GUI manual input | GUI の既存 `VirtualControllerModel -> ControllerOutputPort` 経路から送る入力 |

### 1.3 背景・問題

現行 controller 出力は serial backend を前提にしており、`ControllerOutputPortFactory` も serial device と protocol に依存している。`swbt-python` は serial protocol ではなく、専用 USB Bluetooth adapter、pairing key、reconnect、周期 report loop を持つ controller 実装である。serial protocol の分岐として追加すると、adapter discovery、session lifetime、GUI manual input、runtime 実行の責務が混ざる。

`docs/architecture/swbt-integration/testing-rollout.md` は、設定 model、adapter discovery、session、port、runtime、GUI、実機検証の順に導入する方針を定めている。本仕様はその導入順序を Project NyX の `spec/agent/wip/local_022` から `local_026` へ分割する親計画である。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| swbt 実装配置 | 未導入 | `src/nyxpy/framework/core/hardware/swbt/` に集約する |
| swbt 依存 | 通常 install に存在しない | optional dependency `swbt-python>=0.2.0,<0.3.0` として導入する |
| backend 選択 | serial 前提 | runtime builder 構成時に `serial` / `swbt` の factory を選ぶ |
| IMU | command surface なし | `Command.imu(...)` と `ControllerOutputPort.imu(...)` を追加し、非対応 backend は `NotImplementedError` |
| GUI manual input | serial port を差し込む | 既存 `VirtualControllerModel` に swbt port を差し込む |
| 実機確認 | 未整備 | Pro Controller / Joy-Con L / Joy-Con R の pairing、reconnect、入力、neutral を確認する |

### 1.5 着手条件

- `docs/architecture/swbt-integration/` の設計文書を正とする。
- `swbt-python` は PyPI の最新公開版 `0.2.0` を対象にし、NyX 側の依存範囲は `>=0.2.0,<0.3.0` とする。
- 既存 serial backend は残すが、旧 factory 名や旧 import path の互換 shim は追加しない。
- `manual.py`、`SwbtManualInputSession`、`swbt_*.py` module は作らない。
- GUI から `swbt-python` を直接 import しない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/agent/wip/local_022/SWBT_CONTROLLER_FOUNDATION.md` | 変更 | dependency、controller model、settings、IMU command、adapter discovery の仕様 |
| `spec/agent/wip/local_023/SWBT_CORE_ADAPTER_SERVICE.md` | 変更 | session、mapper、port、factory、dummy session の仕様 |
| `spec/agent/wip/local_024/SWBT_RUNTIME_CLI_INTEGRATION.md` | 変更 | runtime builder、`nyxpy run`、`nyxpy swbt` CLI の仕様 |
| `spec/agent/wip/local_025/SWBT_GUI_SHARED_SERVICE.md` | 変更 | GUI backend 選択、adapter refresh、pair/reconnect/disconnect、manual input 排他の仕様 |
| `spec/agent/wip/local_026/SWBT_REALDEVICE_DOCS_CLOSEOUT.md` | 変更 | 実機検証、docs、完了判定の仕様 |
| `docs/architecture/swbt-integration/testing-rollout.md` | 変更 | 実装後に確定値、検証結果、残課題を反映する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

swbt backend は `ControllerOutputPort` の具象 backend である。`SerialProtocolInterface`、serial device discovery、GUI model、macro API へ swbt 固有処理を混ぜない。

```text
macro Command
  -> runtime ExecutionContext
  -> io ControllerOutputPort
       -> hardware.swbt.SwbtControllerOutputPort
            -> SwbtControllerSession
                 -> swbt-python
```

### 公開 API 方針

マクロ向けには `Command.imu(...)` だけを追加する。既存 `press` / `hold` / `release` は backend 非依存のまま維持する。CLI には `nyxpy swbt adapters`、`nyxpy swbt pair`、`nyxpy swbt reconnect` と、`nyxpy run --controller swbt` を追加する。

### 後方互換性

Project NyX のフレームワーク本体はアルファ版であり、旧 factory 名の alias や `DeprecationWarning` は追加しない。既存 workspace の `serial_device`、`serial_baud`、`serial_protocol` は読み込み元として扱い、新 `controller.serial.*` へ正規化する。

### レイヤー構成

`src/nyxpy/framework/core/hardware/swbt/` に swbt 専用実装を置く。`io/ports.py` には backend 共通 contract だけを置く。`gui` は framework の application service 経由で adapter 列挙と接続操作を呼び、`swbt-python` の型を widget 層へ漏らさない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| adapter refresh | Bluetooth controller open、pairing、report loop を開始しない |
| report period | 既定 `8000us` |
| macro runtime pairing | 暗黙 pairing をしない。保存済み key で reconnect だけを行う |
| swbt 未導入環境 | serial backend の import と通常テストが壊れない |

### 並行性・スレッド安全性

`SwbtControllerSession` が event loop thread と connection lock を所有する。GUI lifetime port と macro runtime port は同じ session を使い回せるが、同時入力は許可しない。macro start 前に GUI lifetime port を `release()` / `close()` してから runtime port を作る。

## 4. 実装仕様

### 子仕様分割

| 子仕様 | 対応範囲 | 依存 | 完了条件 |
|--------|----------|------|----------|
| `local_022` | swbt extra、controller model、settings、IMU command、adapter discovery | `local_021` | `hardware/swbt/config.py` と discovery API の仕様が確定し、IMU の共通 contract が定義されている |
| `local_023` | `SwbtControllerSession`、mapper、port、factory、dummy session | `local_022` | 実機なしで button、D-pad、stick、IMU、session lifecycle を検証できる |
| `local_024` | runtime builder、`nyxpy run`、`nyxpy swbt adapters/pair/reconnect` | `local_022`, `local_023` | swbt backend で serial protocol 生成を通らず、CLI から明示 pair/reconnect できる |
| `local_025` | GUI backend 選択、adapter refresh、pair/reconnect/disconnect、manual input 排他 | `local_024` | 既存 `VirtualControllerModel` に swbt port を差し込み、macro 実行中の manual input を止める |
| `local_026` | 実機検証、docs、完了記録 | `local_022` から `local_025` | Pro Controller / Joy-Con L / Joy-Con R の実機結果と docs 反映が残る |

### 完了条件 checklist への対応

| `testing-rollout.md` の条件 | 担当仕様 |
|-----------------------------|----------|
| `hardware/swbt` package に収める、`swbt_*.py` を増やさない | `local_022`, `local_023` |
| `SwbtControllerType` / `SwbtControllerModel` / capabilities / config | `local_022` |
| `Command.imu(...)`、非対応 backend の `NotImplementedError` | `local_022`, `local_023` |
| `list_adapters()` を GUI / CLI から使う | `local_022`, `local_024`, `local_025` |
| adapter refresh が pairing / reconnect / report loop を開始しない | `local_022`, `local_025` |
| macro run で pairing が暗黙実行されない | `local_023`, `local_024` |
| GUI manual input が `VirtualControllerModel -> ControllerOutputPort` 経路を使う | `local_025` |
| GUI manual input と macro runtime が同じ adapter を同時に開かない | `local_025` |
| GUI に diagnostics editor、controller color editor、IMU editor を置かない | `local_025` |
| Joy-Con type ごとの unsupported input が明確に失敗する | `local_022`, `local_023`, `local_026` |
| close 時に neutral を試みる | `local_023`, `local_025`, `local_026` |

### 未確定事項の扱い

stick Y 軸既定値、短押しの最小 duration、public flush 要否は実機検証で確定する。仕様作成時点では `report_period_us=8000` と NyX 現行 `LStick.x/y` / `RStick.x/y` を前提にし、実機結果で `local_023` または follow-up 仕様へ戻す。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| 静的 | `test_swbt_files_are_inside_hardware_package` | `swbt_*.py`、`hardware/swbt/manual.py`、`SwbtManualInputSession` がない |
| ユニット | `test_swbt_controller_models_and_capabilities` | controller type、capabilities、key store 既定値 |
| ユニット | `test_controller_output_port_imu_default_unsupported` | serial / dummy serial で `imu()` が `NotImplementedError` |
| ユニット | `test_swbt_mapper_rejects_joycon_unsupported_inputs` | Joy-Con L/R の存在しない stick / button を拒否する |
| 結合 | `test_runtime_swbt_does_not_create_serial_protocol` | swbt runtime が serial protocol を生成しない |
| GUI | `test_virtual_controller_uses_controller_output_port_for_swbt` | GUI model が swbt 具象型や `swbt-python` を import しない |
| ハードウェア | `test_swbt_pro_controller_realdevice` | Pro Controller の pair/reconnect/input/neutral |
| ハードウェア | `test_swbt_joycon_l_r_realdevice` | Joy-Con L / Joy-Con R の pair/reconnect/input/neutral |

通常 gate は実機を除外する。

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests -m "not realdevice and not swbt"
```

## 6. 実装チェックリスト

- [ ] `local_022` で swbt extra、controller model、settings、IMU、adapter discovery の仕様を実装可能な粒度にする。
- [ ] `local_023` で session、mapper、port、factory、dummy session の責務を二重化なしで定義する。
- [ ] `local_024` で `nyxpy run` と `nyxpy swbt` subcommand の入力、出力、エラーを定義する。
- [ ] `local_025` で GUI manual input の既存経路、接続操作、macro runtime との排他を定義する。
- [ ] `local_026` で実機検証、docs 反映、complete 移動条件を定義する。
- [ ] すべての子仕様が `docs/architecture/swbt-integration/testing-rollout.md` の完了条件へ対応していることを確認する。
- [ ] 実装後、未解決事項を `spec/dev-journal.md` または新規 wip 仕様へ分離してから `complete` へ移す。
