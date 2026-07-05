# swbt 実機検証 / docs / closeout 仕様書

## 1. 概要

### 1.1 目的

`swbt` controller backend の実機検証、利用者向け docs 反映、実装計画の完了記録を定義する。実装そのものは `local_022` から `local_025` の範囲とし、本仕様は実機で確認すべき挙動、証跡の残し方、完了判定を扱う。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| swbt backend | `swbt-python` を使う Bluetooth HID controller backend |
| 実機検証 | Switch と専用 USB Bluetooth adapter を使い、pairing、reconnect、入力反映、neutral 復帰を確認する検証 |
| diagnostics trace | `swbt-python` または NyX の `SwbtGamepadService` が出力する接続、report 送信、切断の JSONL 証跡 |
| key store | Switch との bond 情報を保存する JSON ファイル |
| active reconnect | 保存済み key store を使い、pairing を許可せず Switch へ再接続する確認手順 |
| manual confirmation | Switch 画面を人が見て入力反映を確認し、結果を検証ログへ記録する方式 |
| closeout | 実装結果、検証結果、残課題を整理し、親計画と子仕様を `spec/agent/complete/` へ移せる状態にする作業 |

### 1.3 背景・問題

`swbt` backend は実機、Bluetooth adapter、Switch 側の待機状態、bond 情報に依存する。単体テストと dummy service だけでは、pairing、reconnect、短押しの取りこぼし、stick Y 軸向き、close 後の入力残留を判定できない。

利用者 docs も現状は serial backend 前提である。`--controller swbt`、`--bt-*` option、GUI の swbt 操作、専用 adapter 要件、トラブルシューティングを公開 docs に反映しなければ、実装後の利用手順が不明確なまま残る。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 実機検証 | serial / capture の `realdevice` test が中心 | `realdevice` と `swbt` marker で swbt 専用検証を分離する |
| pairing / reconnect 証跡 | NyX 側の標準記録なし | adapter、key store、trace、operator result を 1 つの evidence directory へ保存する |
| stick Y 軸既定 | `invert_stick_y=false` を初期値とする | Switch のスティック補正画面で既定値を確定する |
| short press 判定 | 周期 report 前提で未確認 | trace と Switch 画面確認により public flush 要否を判定する |
| 利用者 docs | serial 前提 | serial と swbt の導入、CLI、GUI、トラブル対応を分けて説明する |
| 完了記録 | 親計画が wip に残る | `local_021` と子仕様を検証結果付きで complete へ移せる |

### 1.5 着手条件

- `local_022` で controller config、settings 正規化、serial factory 改名が完了している。
- `local_023` で mapper、port、service、factory の実機なし検証が完了している。
- `local_024` で runtime / CLI から `--controller swbt` を選べる。
- `local_025` で GUI が `SwbtGamepadService` を runtime と共有し、macro 実行中の manual input を無効化している。
- `docs/architecture/swbt-integration/` の設計判断と矛盾しない。
- 実機検証を実施する環境では `uv sync --extra swbt` が済んでいる。
- 実機検証を実施する環境では Switch、専用 USB Bluetooth adapter、キャプチャ入力、operator がそろっている。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | `swbt` pytest marker と、必要なら hardware test 用 option の説明を追加する |
| `tests/conftest.py` | 新規 | `--bt-adapter`、`--bt-key-store`、`--bt-diagnostics`、`--swbt-evidence-dir`、`--swbt-interactive` を pytest option として追加する |
| `tests/hardware/test_swbt_controller_backend_realdevice.py` | 新規 | adapter probe、pairing、reconnect、Button、D-pad、stick、neutral、short press を検証する |
| `docs/user-guide/installation.md` | 変更 | `nyxpy-fw[swbt]` と `uv sync --extra swbt` の導入手順を追加する |
| `docs/user-guide/device-setup.md` | 変更 | serial backend と swbt backend の機材、adapter、key store、pairing 手順を分けて説明する |
| `docs/user-guide/cli.md` | 変更 | `--controller swbt`、`--bt-adapter`、`--bt-pair`、`--bt-key-store`、`--bt-diagnostics` を追加する |
| `docs/user-guide/gui.md` | 変更 | backend 選択、adapter refresh、pair once、reconnect、disconnect、diagnostics trace を説明する |
| `docs/user-guide/troubleshooting.md` | 変更 | adapter が見えない、pairing timeout、reconnect 失敗、入力残留、短押し取りこぼし、stick Y 軸逆転を追加する |
| `docs/macro-development/command-api.md` | 変更 | swbt backend で非対応の keyboard、touch、3DS 固有入力、sleep control を明記する |
| `mkdocs.yml` | 変更 | swbt 専用ページを増やす場合だけ nav を更新する |
| `docs/architecture/swbt-integration/testing-rollout.md` | 変更 | 実機検証で確定した Y 軸既定、short press 判定、diagnostics 方針を反映する |
| `spec/agent/wip/local_021/SWBT_CONTROLLER_BACKEND.md` | 変更 | 完了時に M6 / M7 の結果を反映し、complete へ移動する |
| `spec/agent/wip/local_026/SWBT_REALDEVICE_DOCS_CLOSEOUT.md` | 変更 | 実装後に検証結果と完了記録を反映し、complete へ移動する |

## 3. 設計方針

### 実機検証の境界

実機検証は `tests/hardware/` に閉じる。通常の `uv run pytest` では実行されないよう、全テストに `@pytest.mark.realdevice` と `@pytest.mark.swbt` を付ける。CI の通常 gate は `-m "not realdevice and not swbt"` を使う。

adapter の存在確認と接続確認は自動判定する。Switch 画面に入力が反映されたかどうかは、初期実装では manual confirmation を許容する。manual confirmation を含む test は `--swbt-interactive` がない場合に skip し、非対話のテスト実行を止めない。

### 証跡保存

実機検証ごとに evidence directory を作る。既定値は `.nyxpy/swbt/hardware-artifacts/<日時>/` とし、`--swbt-evidence-dir` で上書きできる。保存するファイルは次の通りである。

| ファイル | 内容 | commit 対象 |
|----------|------|-------------|
| `run-metadata.json` | OS、NyX commit、swbt-python version、adapter、key store path、test command | 原則 commit しない |
| `swbt-trace.jsonl` | 接続、pairing、report 送信、切断の diagnostics trace | 原則 commit しない |
| `operator-confirmation.jsonl` | manual confirmation の観察結果 | 原則 commit しない |
| `summary.md` | 検証結果の要約、失敗時の再現条件、docs 反映先 | 必要な要約だけ complete 仕様へ転記する |

raw trace は adapter ID、OS path、実行者固有 path を含み得るため、既定では repository に含めない。PR や完了記録へ載せるのは、接続成否、入力種別、report 有無、判定結果に限定した要約である。

### stick Y 軸の確定

NyX の `LStick.UP` / `RStick.UP` は現在 `y=0` である。`invert_stick_y=false` を初期値とし、Switch のスティック補正画面で上方向、下方向を確認する。

判定は左右 stick で分ける。`invert_stick_y=false` で `LStick.UP` と `RStick.UP` が Switch 画面の上方向として観察できる場合、既定値は `false` のまま確定する。上下が逆に観察された場合、`invert_stick_y=true` を既定に変更する実装修正を `local_023` または follow-up 仕様へ戻し、修正後に本仕様の実機検証をやり直す。

### short press と public flush の判定

NyX port は `SwbtGamepadService.apply()` に完全な `InputState` を渡し、swbt 側の周期 report で反映される前提で実装する。短押し検証では、duration と trace の両方を確認する。

`report_period_us=8000` の既定値では、16ms、33ms、50ms の Button.A 短押しを検証対象にする。16ms 以上の押下で trace に pressed report と neutral report が記録され、Switch 画面でも反映される場合、NyX 側から swbt public flush を要求しない。16ms 以上で pressed report が trace に出ない、または Switch 画面で安定して取りこぼす場合、`swbt-python` 側に `flush` または `send_current` 相当の public API が必要な候補として記録する。

8ms 以下の押下だけが取りこぼされる場合は public flush 必須とは扱わない。NyX docs に swbt backend の最小推奨 press duration を記載する。

### docs 反映方針

利用者 docs は serial backend を置き換えず、serial と swbt を並列に説明する。swbt backend は通常の PC Bluetooth 機能ではなく、Bumble から直接開く専用 USB Bluetooth adapter を使う前提で書く。

CLI docs では swbt backend でも capture source が必要であることを残す。`--serial` は serial backend 専用であり、`--controller swbt` では不要であると明記する。

GUI docs では runtime と manual input が同じ `SwbtGamepadService` を共有すること、macro 実行中は manual input が無効化されることを書く。これは利用者が disconnect や pair once を押すタイミングを誤らないためである。

### closeout 方針

`local_026` 完了時点で、親計画 `local_021` と子仕様 `local_022` から `local_026` が実装結果を反映していることを確認する。未解決の設計判断が残る場合は、complete へ移す前に `spec/dev-journal.md` か次の wip 仕様へ分離する。未解決のまま親計画を完了扱いにしない。

## 4. 実装仕様

### pytest option

```python
@dataclass(frozen=True)
class SwbtRealDeviceOptions:
    adapter: str
    key_store_path: Path
    diagnostics_path: Path
    evidence_dir: Path
    timeout_sec: float = 30.0
    allow_pairing: bool = False
    interactive: bool = False
    report_period_us: int = 8000
    device_name: str = "Pro Controller"
```

| option | 型 | 既定値 | 説明 |
|--------|-----|--------|------|
| `--bt-adapter` | `str` | `"usb:0"` | Bumble が開く adapter |
| `--bt-key-store` | `Path` | `.nyxpy/swbt/test-switch.json` | 実機テスト用 key store |
| `--bt-diagnostics` | `Path | None` | evidence directory 内の `swbt-trace.jsonl` | diagnostics trace 保存先 |
| `--bt-timeout` | `float` | `30.0` | pairing / reconnect timeout 秒 |
| `--swbt-evidence-dir` | `Path | None` | `.nyxpy/swbt/hardware-artifacts/<日時>/` | 実機証跡の保存先 |
| `--swbt-interactive` | `bool` | `False` | manual confirmation を伴う test を実行する |
| `--swbt-short-press-ms` | `list[int]` | `16,33,50` | short press 判定で使う duration |

### 実機テスト構成

| テスト | 自動判定 | manual confirmation | 検証内容 |
|--------|----------|---------------------|----------|
| `test_swbt_adapter_probe_realdevice` | あり | なし | `swbt-probe adapters --json` 相当の adapter 確認で対象 adapter が見える |
| `test_swbt_pairing_realdevice` | あり | Switch を接続画面に置く操作のみ | `allow_pairing=true` で接続し、key store が作成される |
| `test_swbt_reconnect_realdevice` | あり | なし | 保存済み key store と `allow_pairing=false` で active reconnect が成功する |
| `test_swbt_button_dpad_reflection_manual_realdevice` | trace は自動、画面反映は人手 | あり | Button.A、Button.B、PLUS、MINUS、D-pad UP / RIGHT / DOWN / LEFT が反映される |
| `test_swbt_stick_reflection_manual_realdevice` | trace は自動、画面反映は人手 | あり | left / right stick の上、下、左、右、center が反映される |
| `test_swbt_neutral_after_close_realdevice` | trace は自動、画面反映は人手 | あり | close、cancel、failure 相当の終了後に neutral が送られ入力が残らない |
| `test_swbt_short_press_duration_realdevice` | trace は自動、画面反映は人手 | あり | 16ms、33ms、50ms の短押しが report と画面の両方で確認できる |

### 実行コマンド

通常 gate では swbt 実機テストを除外する。

```console
uv run pytest tests -m "not realdevice and not swbt"
```

adapter probe と reconnect までの非対話テストを実行する。

```console
uv run pytest tests/hardware -m "realdevice and swbt" --bt-adapter usb:0 --bt-key-store .nyxpy/swbt/test-switch.json
```

画面観察を含む確認は `-s` と `--swbt-interactive` を付ける。

```console
uv run pytest tests/hardware -m "realdevice and swbt" -s --swbt-interactive --bt-adapter usb:0 --bt-key-store .nyxpy/swbt/test-switch.json
```

diagnostics trace の保存先を明示する。

```console
uv run pytest tests/hardware -m "realdevice and swbt" -s --swbt-interactive --bt-adapter usb:0 --bt-key-store .nyxpy/swbt/test-switch.json --bt-diagnostics .nyxpy/swbt/hardware-artifacts/latest/swbt-trace.jsonl
```

### operator 手順

1. Switch を controller pairing 画面または接続待機状態にする。
2. 初回 pairing test を `--swbt-interactive` なしで実行し、接続と key store 作成を確認する。
3. Switch 側の controller 接続を切り、同じ key store で reconnect test を実行する。
4. manual confirmation test を実行する。
5. Button、D-pad、stick、neutral の各観察結果を terminal prompt へ `pass` または `fail` で入力する。
6. 失敗時は `operator-confirmation.jsonl` に観察内容、Switch 画面、再現した入力名、trace の該当 event 範囲を残す。

### diagnostics trace 判定

trace では少なくとも次を確認する。

| event | 判定 |
|-------|------|
| `adapter_opened` | 指定 adapter が開けた |
| `connected` | HID control / interrupt channel が開いた |
| `pairing_completed` または `bond_loaded` | pairing または reconnect の根拠がある |
| `report_tx` | Button、D-pad、stick、neutral の report が送信された |
| `neutral_tx` | close / cancel / failure 後に neutral が送信された |
| `disconnected` | factory close で transport が閉じた |

event 名は実装済み diagnostics の表現に合わせる。名前が異なる場合でも、接続、bond、report、neutral、切断の 5 分類を summary に残す。

### docs 更新内容

| docs | 追加する内容 |
|------|--------------|
| `installation.md` | `nyxpy-fw[swbt]`、`uv sync --extra swbt`、専用 adapter driver の準備 |
| `device-setup.md` | serial backend と swbt backend の機材差分、adapter probe、key store 保存先、pairing / reconnect |
| `cli.md` | `--controller serial|swbt`、serial 専用 option、swbt 専用 option、実行例 |
| `gui.md` | backend 選択、Refresh adapters、Pair once、Reconnect、Disconnect、diagnostics folder |
| `troubleshooting.md` | adapter 不検出、pairing timeout、reconnect 失敗、入力が残る、stick Y 軸逆転、短押し取りこぼし |
| `command-api.md` | swbt backend の対応入力と非対応入力 |
| `testing-rollout.md` | 実機で確定した既定値とリスク判定 |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_swbt_realdevice_options_defaults` | pytest option の既定値と path 解決 |
| ユニット | `test_swbt_evidence_writer_redacts_paths` | summary へ書く情報が個人 path や adapter 固有値を過剰に含まない |
| ユニット | `test_swbt_operator_confirmation_records_result` | manual confirmation の `pass` / `fail` / `skip` が JSONL に記録される |
| 結合 | `test_swbt_docs_examples_match_cli_parser` | docs の `--controller swbt` 実行例が CLI parser と一致する |
| 結合 | `test_mkdocs_build_includes_swbt_pages` | swbt docs を増やした場合に `mkdocs build --strict` が通る |
| ハードウェア | `test_swbt_adapter_probe_realdevice` | `@pytest.mark.realdevice` / `@pytest.mark.swbt` で adapter を確認する |
| ハードウェア | `test_swbt_pairing_realdevice` | pairing、key store 作成、trace 保存 |
| ハードウェア | `test_swbt_reconnect_realdevice` | active reconnect、pairing なし接続、trace 保存 |
| ハードウェア | `test_swbt_button_dpad_reflection_manual_realdevice` | Button と D-pad の画面反映 |
| ハードウェア | `test_swbt_stick_reflection_manual_realdevice` | left / right stick と Y 軸既定 |
| ハードウェア | `test_swbt_neutral_after_close_realdevice` | close 後の neutral |
| ハードウェア | `test_swbt_short_press_duration_realdevice` | short press と public flush 要否 |

通常の実装検証は次を使う。

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests -m "not realdevice and not swbt"
uv run mkdocs build --strict
```

実機検証は環境があるときだけ実行し、結果を `local_026` の完了記録へ要約する。実機検証を実施できない場合、`local_026` は complete へ移さない。

## 6. 実装チェックリスト

- [ ] `pyproject.toml` に `swbt` marker を追加する。
- [ ] `tests/conftest.py` に swbt 実機検証用 pytest option を追加する。
- [ ] `tests/hardware/test_swbt_controller_backend_realdevice.py` を追加する。
- [ ] adapter probe test を実装し、接続を開始せず adapter を確認できるようにする。
- [ ] pairing test を実装し、key store 作成と diagnostics trace を記録する。
- [ ] reconnect test を実装し、`allow_pairing=false` の active reconnect を確認する。
- [ ] Button と D-pad の manual confirmation test を追加する。
- [ ] left / right stick と neutral の manual confirmation test を追加する。
- [ ] stick Y 軸既定値を実機結果で確定する。
- [ ] short press test を追加し、public flush 要否を判定する。
- [ ] diagnostics trace と operator confirmation の evidence directory を作成する。
- [ ] `docs/user-guide/installation.md` に swbt extra 導入手順を追加する。
- [ ] `docs/user-guide/device-setup.md` に swbt 機材と pairing / reconnect 手順を追加する。
- [ ] `docs/user-guide/cli.md` に swbt CLI option と実行例を追加する。
- [ ] `docs/user-guide/gui.md` に swbt GUI 操作を追加する。
- [ ] `docs/user-guide/troubleshooting.md` に swbt 固有の失敗時確認を追加する。
- [ ] `docs/macro-development/command-api.md` に swbt 非対応入力を追加する。
- [ ] `docs/architecture/swbt-integration/testing-rollout.md` に実機で確定した判断を反映する。
- [ ] `uv run ruff format .` を実行する。
- [ ] `uv run ruff check .` を実行する。
- [ ] `uv run ty check src/nyxpy --output-format concise --no-progress` を実行する。
- [ ] `uv run pytest tests -m "not realdevice and not swbt"` を実行する。
- [ ] `uv run mkdocs build --strict` を実行する。
- [ ] `uv run pytest tests/hardware -m "realdevice and swbt"` の実機結果を記録する。
- [ ] `local_021` と `local_026` に実装結果、検証結果、残課題を反映する。
- [ ] `local_021` から `local_026` を `spec/agent/complete/` へ移せる状態にする。

## 7. 親計画との依存関係

本仕様は親計画 `local_021` の M6 / M7 を担当する。`local_022` から `local_025` の実装結果を前提にするため、swbt service、factory、runtime / CLI、GUI の責務を再定義しない。

`local_026` で発見した実装不備は、該当する子仕様へ戻す。mapper や Y 軸既定の修正は `local_023`、CLI option の修正は `local_024`、GUI lifetime の修正は `local_025` の責務である。docs と完了記録だけで吸収しない。

## 8. 完了後に次へ渡す成果

完了後に残す成果は次の通りである。

| 成果 | 渡し先 | 内容 |
|------|--------|------|
| 実機検証 summary | `spec/agent/complete/local_026/` | pairing、reconnect、Button、D-pad、stick、neutral、short press の判定 |
| 確定値 | `docs/architecture/swbt-integration/testing-rollout.md` | `invert_stick_y` 既定値、short press 最小推奨 duration、public flush 要否 |
| 利用者手順 | `docs/user-guide/` | install、device setup、CLI、GUI、troubleshooting |
| closeout 記録 | `spec/agent/complete/local_021/` | 親計画の完了条件、子仕様の完了状態、検証コマンド |
| 残課題 | `spec/dev-journal.md` または新規 wip 仕様 | 実装範囲外の改善、追加自動化、upstream swbt-python 要望 |

`local_021` を complete へ移す条件は、serial backend が壊れていないこと、swbt extra 未導入環境で import error が出ないこと、swbt 実機検証が要約付きで残っていること、利用者 docs が `mkdocs build --strict` を通ることである。
