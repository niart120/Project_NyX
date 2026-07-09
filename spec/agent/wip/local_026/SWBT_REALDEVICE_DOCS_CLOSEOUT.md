# swbt 実機検証 / docs / closeout 仕様書

## 1. 概要

### 1.1 目的

swbt backend の実機検証、利用者向け docs 反映、完了記録を定義する。Pro Controller、Joy-Con L、Joy-Con R について adapter discovery、pairing、reconnect、button、D-pad、stick、IMU、neutral、short press を確認し、親計画 `local_021` と子仕様を complete へ移せる状態にする。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| 実機検証 | Switch、専用 USB Bluetooth adapter、`swbt-python` を使う hardware test |
| evidence directory | 実機検証の metadata、trace、operator confirmation、summary を保存する directory |
| diagnostics trace | swbt session の接続、pair/reconnect、report、neutral、disconnect の JSONL 証跡 |
| operator confirmation | Switch 画面を人が見て入力反映を `pass` / `fail` / `skip` で記録する確認 |
| short press | `Command.press(..., dur=...)` が swbt report loop に載る最小 duration の確認 |
| closeout | 実装結果、検証結果、docs、残課題を整理し、wip 仕様を complete へ移せる状態にする作業 |

### 1.3 背景・問題

単体テストと dummy session では、Bluetooth adapter、pairing key、Switch 側接続状態、Joy-Con capability、stick Y 軸、short press の取りこぼし、close 後の入力残留を確認できない。利用者 docs も serial backend 前提のままでは、swbt extra、専用 adapter、key store、pair/reconnect、GUI 操作、トラブル対応が分からない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 実機検証 | 未整備 | `realdevice` と `swbt` marker で通常 gate から分離 |
| controller 種別 | Pro Controller だけに偏り得る | Pro Controller / Joy-Con L / Joy-Con R を分けて記録 |
| IMU | 未確認 | `Command.imu(...)` の neutral / gyro frame を trace と必要な観察で確認 |
| short press | 未確認 | 16ms、33ms、50ms の反映と public flush 要否を判定 |
| docs | serial 前提 | install、device setup、CLI、GUI、command API、troubleshooting に swbt を反映 |
| closeout | wip に残る | 検証結果と残課題を反映して complete 移動可能にする |

### 1.5 着手条件

- `local_022` から `local_025` の実装と通常 gate が完了している。
- 実機検証環境で `uv sync --extra swbt` が済んでいる。
- Switch、専用 USB Bluetooth adapter、キャプチャ入力、operator がそろっている。
- 実機検証できない場合、`local_026` と親計画は complete へ移さない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | `swbt` pytest marker を追加する |
| `tests/conftest.py` | 変更 | `--swbt-adapter`、`--swbt-controller-type`、`--swbt-key-store`、`--swbt-diagnostics`、`--swbt-evidence-dir`、`--swbt-interactive`、`--swbt-short-press-ms` を追加する |
| `tests/hardware/test_swbt_controller_backend_realdevice.py` | 新規 | adapter、pair/reconnect、button、D-pad、stick、IMU、neutral、short press を検証する |
| `docs/user-guide/installation.md` | 変更 | `nyxpy-fw[swbt]` と `uv sync --extra swbt` を追加する |
| `docs/user-guide/device-setup.md` | 変更 | swbt adapter、key store、pair/reconnect 手順を追加する |
| `docs/user-guide/cli.md` | 変更 | `nyxpy swbt` と `nyxpy run --controller swbt` を追加する |
| `docs/user-guide/gui.md` | 変更 | backend selector、adapter refresh、pair、reconnect、disconnect を追加する |
| `docs/user-guide/troubleshooting.md` | 変更 | adapter 不検出、pair timeout、reconnect 失敗、unsupported input、入力残留、short press を追加する |
| `docs/macro-development/command-api.md` | 変更 | `Command.imu(...)` と swbt 非対応入力を説明する |
| `docs/architecture/swbt-integration/testing-rollout.md` | 変更 | 実機で確定した stick Y 軸、short press、flush 要否を反映する |
| `spec/agent/wip/local_021` から `local_026` | 変更 | 実装結果、検証結果、残課題を反映し、complete 移動可能にする |

## 3. 設計方針

### 実機検証の境界

実機検証は `tests/hardware/` に閉じ、全テストに `@pytest.mark.realdevice` と `@pytest.mark.swbt` を付ける。通常 gate では `-m "not realdevice and not swbt"` で除外する。

### 証跡保存

実機検証ごとに evidence directory を作る。既定値は `.nyxpy/swbt/hardware-artifacts/<日時>/` とする。

| ファイル | 内容 | commit 対象 |
|----------|------|-------------|
| `run-metadata.json` | OS、NyX commit、swbt-python version、controller type、adapter、key store、test command | 原則 commit しない |
| `swbt-trace.jsonl` | pair/reconnect/report/neutral/disconnect trace | 原則 commit しない |
| `operator-confirmation.jsonl` | 画面観察の `pass` / `fail` / `skip` | 原則 commit しない |
| `summary.md` | 検証結果、失敗条件、docs 反映先 | 必要な要約だけ complete 仕様へ転記 |

raw trace には adapter ID、OS path、個人 path が含まれ得る。PR と complete 仕様には判定に必要な要約だけを載せる。

### controller type 別確認

Pro Controller、Joy-Con L、Joy-Con R は別 key store を使う。Joy-Con L は right stick、Joy-Con R は left stick を unsupported として明確に失敗させる。unsupported input は実機確認の前に単体テストで固定し、実機では選択 controller type に存在する入力だけを確認する。

### stick Y 軸と short press

NyX 現行 `LStick.UP` / `RStick.UP` の `x/y` を swbt `Stick` へ変換した結果が Switch 画面で上方向として観察されるか確認する。逆なら `local_023` へ戻して mapper 既定を修正する。

`report_period_us=8000` では 16ms、33ms、50ms の Button.A short press を確認する。16ms 以上で trace と画面の両方が安定するなら public flush は不要とする。16ms 以上で pressed report が trace に出ない、または画面反映が安定しない場合、`swbt-python` 側の public flush / send_current 相当を残課題として記録する。

### docs 反映方針

serial backend を置き換えず、serial と swbt を並列に説明する。swbt backend は通常の PC Bluetooth 機能ではなく、Bumble から直接開く専用 USB Bluetooth adapter を使う前提で書く。

### closeout 方針

`local_021` から `local_026` は、実装結果、検証コマンド、実機結果、残課題が反映されるまで `wip` に残す。残課題が実装範囲外なら `spec/dev-journal.md` または新規 wip 仕様へ分離してから complete へ移す。

## 4. 実装仕様

### pytest option

```python
@dataclass(frozen=True, slots=True)
class SwbtRealDeviceOptions:
    adapter: str
    controller_type: str
    key_store_path: Path
    diagnostics_path: Path | None
    evidence_dir: Path
    timeout_sec: float = 30.0
    interactive: bool = False
    short_press_ms: tuple[int, ...] = (16, 33, 50)
```

| option | 型 | 既定値 | 説明 |
|--------|-----|--------|------|
| `--swbt-adapter` | `str` | `"usb:0"` | adapter 名 |
| `--swbt-controller-type` | `str` | `"pro-controller"` | controller type |
| `--swbt-key-store` | `Path` | `.nyxpy/swbt/<controller>-test-bond.json` | 実機テスト用 key store |
| `--swbt-diagnostics` | `Path | None` | evidence directory 内 `swbt-trace.jsonl` | diagnostics trace |
| `--swbt-timeout` | `float` | `30.0` | pair/reconnect timeout |
| `--swbt-evidence-dir` | `Path | None` | `.nyxpy/swbt/hardware-artifacts/<日時>/` | 証跡保存先 |
| `--swbt-interactive` | `bool` | `False` | operator confirmation を実行する |
| `--swbt-short-press-ms` | `list[int]` | `16,33,50` | short press duration |

### 実機テスト

| テスト | 自動判定 | manual confirmation | 検証内容 |
|--------|----------|---------------------|----------|
| `test_swbt_adapter_discovery_realdevice` | あり | なし | adapter が `list_adapters()` で見える |
| `test_swbt_pair_realdevice` | あり | Switch を接続画面に置く操作のみ | pairing 成功と key store 作成 |
| `test_swbt_reconnect_realdevice` | あり | なし | 保存済み key store で reconnect |
| `test_swbt_button_dpad_manual_realdevice` | trace は自動 | あり | Button、D-pad の反映 |
| `test_swbt_stick_manual_realdevice` | trace は自動 | あり | left / right stick と Y 軸 |
| `test_swbt_imu_realdevice` | trace は自動 | 必要に応じてあり | `Command.imu(IMUFrame.neutral())` と gyro frame |
| `test_swbt_neutral_after_close_realdevice` | trace は自動 | あり | close / cancel / failure 後に neutral |
| `test_swbt_short_press_duration_realdevice` | trace は自動 | あり | 16ms、33ms、50ms の short press |

### 実行コマンド

通常 gate:

```console
uv run pytest tests -m "not realdevice and not swbt"
```

adapter / pair / reconnect:

```console
uv run pytest tests/hardware -m "realdevice and swbt" --swbt-adapter usb:0 --swbt-controller-type pro-controller --swbt-key-store .nyxpy/swbt/pro-controller-test-bond.json
```

画面観察あり:

```console
uv run pytest tests/hardware -m "realdevice and swbt" -s --swbt-interactive --swbt-adapter usb:0 --swbt-controller-type pro-controller --swbt-key-store .nyxpy/swbt/pro-controller-test-bond.json
```

Joy-Con は key store を分ける。

```console
uv run pytest tests/hardware -m "realdevice and swbt" -s --swbt-interactive --swbt-controller-type joy-con-l --swbt-key-store .nyxpy/swbt/joy-con-l-test-bond.json
uv run pytest tests/hardware -m "realdevice and swbt" -s --swbt-interactive --swbt-controller-type joy-con-r --swbt-key-store .nyxpy/swbt/joy-con-r-test-bond.json
```

### docs 更新内容

| docs | 追加内容 |
|------|----------|
| `installation.md` | `nyxpy-fw[swbt]`、`uv sync --extra swbt` |
| `device-setup.md` | 専用 adapter、adapter discovery、key store、pair/reconnect |
| `cli.md` | `nyxpy swbt adapters/pair/reconnect`、`nyxpy run --controller swbt` |
| `gui.md` | backend selector、Refresh adapters、Pair、Reconnect、Disconnect |
| `troubleshooting.md` | adapter 不検出、timeout、key store 不正、unsupported input、入力残留、short press |
| `command-api.md` | `Command.imu(...)`、IMU frame 数、非対応 backend |
| `testing-rollout.md` | stick Y 軸、short press、public flush 要否 |

### エラーハンドリング

| 条件 | 記録 |
|------|------|
| adapter 不検出 | adapter 名、aliases、VID/PID の有無 |
| pair timeout | Switch 側状態、controller type、key store path |
| reconnect 失敗 | key store の有無、不正判定、controller type 不一致 |
| unsupported input | controller type、入力名、error code |
| short press 失敗 | duration、pressed report 有無、neutral report 有無、画面観察 |

### シングルトン管理

実機テストごとに factory / session を作り、test teardown で close する。global singleton は追加しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_swbt_realdevice_options_defaults` | pytest option の既定値 |
| ユニット | `test_swbt_evidence_writer_redacts_paths` | summary が個人 path を過剰に含まない |
| ユニット | `test_swbt_operator_confirmation_records_result` | operator confirmation JSONL |
| 結合 | `test_swbt_docs_examples_match_cli_parser` | docs の CLI 例が parser と一致 |
| 結合 | `test_mkdocs_build_includes_swbt_pages` | swbt docs 追加後の `mkdocs build --strict` |
| ハードウェア | `test_swbt_adapter_discovery_realdevice` | adapter discovery |
| ハードウェア | `test_swbt_pair_realdevice` | pairing と key store 作成 |
| ハードウェア | `test_swbt_reconnect_realdevice` | reconnect |
| ハードウェア | `test_swbt_button_dpad_manual_realdevice` | Button / D-pad |
| ハードウェア | `test_swbt_stick_manual_realdevice` | stick と Y 軸 |
| ハードウェア | `test_swbt_imu_realdevice` | IMU neutral / gyro |
| ハードウェア | `test_swbt_neutral_after_close_realdevice` | close 後 neutral |
| ハードウェア | `test_swbt_short_press_duration_realdevice` | short press と flush 要否 |

通常検証:

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests -m "not realdevice and not swbt"
uv run mkdocs build --strict
```

## 6. 実装チェックリスト

- [ ] pytest の `swbt` marker と実機 option を追加する。
- [ ] evidence directory writer と operator confirmation writer を追加する。
- [ ] adapter discovery 実機テストを追加する。
- [ ] controller type ごとの pair / reconnect 実機テストを追加する。
- [ ] Button / D-pad / stick / IMU / neutral / short press の実機テストを追加する。
- [ ] Joy-Con L/R の unsupported input が明確に失敗することを確認する。
- [ ] stick Y 軸既定値を実機結果で確定する。
- [ ] short press の最小推奨 duration と public flush 要否を判定する。
- [ ] 利用者 docs に install、device setup、CLI、GUI、troubleshooting を反映する。
- [ ] macro development docs に `Command.imu(...)` と swbt 非対応入力を反映する。
- [ ] `docs/architecture/swbt-integration/testing-rollout.md` に確定値を反映する。
- [ ] `local_021` から `local_026` に実装結果と検証結果を反映する。
- [ ] 残課題を `spec/dev-journal.md` または新規 wip 仕様へ分離する。
- [ ] complete 移動前に `uv run mkdocs build --strict` と通常 gate が通ることを確認する。
