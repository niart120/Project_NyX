# swbt controller backend 実装計画

> **対象モジュール**: `src/nyxpy/framework/core/io/`, `src/nyxpy/framework/core/runtime/`, `src/nyxpy/framework/core/settings/`, `src/nyxpy/cli/`, `src/nyxpy/gui/`
> **目的**: `swbt-python` を NyX の `ControllerOutputPort` backend として追加し、既存 `Command` API から Bluetooth HID 経由の Switch 入力を扱えるようにする。
> **関連ドキュメント**: `docs/architecture/swbt-integration/`
> **破壊的変更**: あり。serial 専用 factory を `SerialControllerOutputPortFactory` へ改名し、互換 alias は残さない。

## 0. 文書配置

この文書は未着手の実装計画であるため、`spec/agent/wip/local_021/` に置く。完了時は実装結果と検証結果を反映したうえで `spec/agent/complete/local_021/` へ移す。

`docs/architecture/swbt-integration/` は設計判断の保管場所とする。この文書は、その設計を Project NyX の現在のコードへ実装するための作業順序、対象ファイル、テスト、完了条件を管理する。

この改修全体を `local_021` だけで完結させない。`local_021` は親計画として扱い、実装はマイルストーンごとの作業仕様へ分ける。マイルストーン番号はこの文書内の進行単位であり、実際の `local_0xx` 番号は着手時点の空き番号を使う。

## 1. 概要

### 1.1 目的

`swbt-python` を `SerialProtocolInterface` へ入れず、`ControllerOutputPort` の具象実装として追加する。マクロ、`DefaultCommand`、`ExecutionContext`、`MacroRuntime` は backend の種類を知らず、既存の `cmd.press()` / `cmd.hold()` / `cmd.release()` / `cmd.capture()` をそのまま使う。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| controller backend | NyX の controller 出力実装。`serial` または `swbt` |
| `ControllerOutputPort` | Runtime が controller 入力送信に使う抽象 port |
| `SerialControllerOutputPortFactory` | 既存 serial controller port を生成する factory。現行 `ControllerOutputPortFactory` を改名する |
| `SwbtControllerOutputPortFactory` | `SwbtGamepadService` を所有し、runtime 用の `SwbtControllerOutputPort` を生成する factory |
| `SwbtGamepadService` | `swbt-python` の `SwitchGamepad` lifecycle と非同期処理を NyX の同期実行へ接続する service |
| `NyxSwbtInputMapper` | NyX の button / hat / stick 値を `swbt-python` の `InputState` へ変換する mapper |
| manual input | GUI から直接 controller state を送る操作 |

### 1.3 背景・問題

現行の `ControllerOutputPortFactory` は名前上は汎用だが、実体は serial device と `SerialProtocolInterface` に依存する serial 専用 factory である。`swbt-python` は serial bytes 生成部品ではなく、Bluetooth HID の接続、pairing、reconnect、周期 report loop、入力状態を所有するため、serial protocol として追加すると責務が崩れる。

CLI も現状では `--serial` / `--capture` を前提に serial protocol を先に生成する構成である。`--controller swbt` では `--serial` を不要にし、serial protocol 生成を通らない構成へ変える必要がある。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| マクロ API | serial backend 前提 | serial / swbt で同じ `Command` API を使う |
| backend 選択箇所 | CLI / builder が serial 前提 | 構成起点で一度だけ `ControllerOutputPort` factory を選ぶ |
| swbt 依存範囲 | 未導入 | `hardware/swbt_*` と `io/swbt_adapter.py` 周辺へ閉じる |
| 通常 install | swbt 依存なし | swbt 依存なしで serial backend が動く |
| 実機なしテスト | serial dummy 中心 | swbt mapper / port / service / runtime injection を実機なしで検証する |

### 1.5 着手条件

- `docs/architecture/swbt-integration/` の設計レビュー反映済み commit が存在すること。
- `swbt-python>=0.1.1,<0.2.0` の公開 API を前提にすること。
- 既存の `serial_device` / `serial_baud` / `serial_protocol` は読み込み元として維持し、新 schema へ正規化すること。
- alias / 互換 import / `DeprecationWarning` を追加しないこと。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | `swbt` optional dependency と必要な pytest marker を追加する |
| `src/nyxpy/framework/core/io/adapters.py` | 変更 | `ControllerOutputPortFactory` を `SerialControllerOutputPortFactory` へ改名し、呼び出し元を更新する |
| `src/nyxpy/framework/core/io/swbt_adapter.py` | 新規 | `SwbtControllerOutputPort`、mapper、dummy service を実装する |
| `src/nyxpy/framework/core/hardware/swbt_service.py` | 新規 | `SwbtGamepadService` と config、例外変換を実装する |
| `src/nyxpy/framework/core/io/device_factories.py` | 変更 | serial / swbt factory 選択と lifetime 管理を追加する |
| `src/nyxpy/framework/core/runtime/builder.py` | 変更 | controller config から `PortFactory[ControllerOutputPort]` を構成できるようにする |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | `controller.*` schema と既存 serial 設定の正規化を追加する |
| `src/nyxpy/cli/run_cli.py` | 変更 | `--controller` と swbt 用 option を追加し、swbt backend では `--serial` を不要にする |
| `src/nyxpy/gui/app_services.py` | 変更 | GUI と runtime が同じ swbt service を共有する builder lifetime へ更新する |
| `src/nyxpy/gui/models/virtual_controller_model.py` | 変更 | manual input と runtime の同時操作を避ける制御を追加する |
| `tests/unit/` | 変更 | mapper、port、service、settings、CLI option の単体テストを追加する |
| `tests/integration/` | 変更 | swbt dummy service を使った runtime injection test を追加する |
| `tests/hardware/` | 変更 | `@pytest.mark.swbt` の実機確認テストを追加する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

swbt は `ControllerOutputPort` の具象 backend として扱う。`SerialProtocolInterface`、`ProtocolFactory`、serial device discovery には入れない。`Command`、`MacroRuntime`、`ExecutionContext` は swbt を import しない。

### 公開 API 方針

既存マクロ向けの `Command` API は変更しない。設定と CLI には `controller.backend` / `--controller` を追加する。serial 専用 factory 名は `SerialControllerOutputPortFactory` へ改め、旧名 alias は残さない。

### 後方互換性

破壊的変更あり。`ControllerOutputPortFactory` の旧名 import は失効させる。Project NyX のフレームワーク本体はアルファ版であり、互換 shim を増やさず呼び出し元とテストを同じ変更で正名へ更新する。

既存 workspace 設定の読み込みは壊さない。`serial_device` / `serial_baud` / `serial_protocol` は serial backend の入力として読み、内部では `SerialControllerConfig` へ正規化する。

### レイヤー構成

`swbt-python` import は `hardware/swbt_service.py` と `io/swbt_adapter.py` 周辺に閉じ込める。GUI / CLI は config を作り、runtime builder に渡す。framework core から GUI へは依存しない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| swbt report period | 既定 `8000us` |
| 短押し duration | 既存 `Command.press(..., dur=...)` の duration を維持する |
| runtime 開始時の reconnect | 既存接続が共有されている場合は reconnect しない |
| serial backend | swbt extra 未導入環境で import error を起こさない |

### 並行性・スレッド安全性

`SwbtGamepadService` が async event loop thread を所有する。同期 port は service の同期メソッドを呼び、service 内で event loop thread へ処理を渡す。service の lifecycle 変更は lock で保護する。

GUI manual input と macro runtime は同じ service を共有するが、同時操作は対象外とする。GUI は macro 実行中の manual input を無効化し、runtime port 作成時に service を neutral へ揃える。

## 4. 実装仕様

### 公開インターフェース

```python
@dataclass(frozen=True)
class SerialControllerConfig:
    device: str | None = None
    protocol: str = "CH552"
    baudrate: int = 9600


@dataclass(frozen=True)
class SwbtControllerConfig:
    adapter: str = "usb:0"
    key_store_path: Path | None = Path(".nyxpy/swbt/switch-bond.json")
    connect_timeout_sec: float = 30.0
    allow_pairing: bool = False
    report_period_us: int = 8000
    device_name: str = "Pro Controller"
    diagnostics_path: Path | None = None
    connect_on_open: bool = True
    invert_stick_y: bool = False


ControllerConfig = SerialControllerConfig | SwbtControllerConfig


class SwbtGamepadService:
    def start(self, *, allow_pairing: bool, timeout_sec: float) -> None: ...
    def apply(self, state: InputState) -> None: ...
    def neutral(self) -> None: ...
    def status(self) -> GamepadStatus: ...
    def close(self) -> None: ...


class SwbtControllerOutputPort(ControllerOutputPort):
    def press(self, buttons: Iterable[ButtonLike]) -> None: ...
    def hold(self, buttons: Iterable[ButtonLike]) -> None: ...
    def release(self, buttons: Iterable[ButtonLike] | None = None) -> None: ...
    def close(self) -> None: ...


class SwbtControllerOutputPortFactory:
    def create(
        self,
        *,
        allow_dummy: bool = False,
        timeout_sec: float | None = None,
    ) -> ControllerOutputPort: ...

    def close(self) -> None: ...
```

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `controller.backend` | `str` | `"serial"` | `serial` または `swbt` |
| `controller.serial.device` | `str | None` | `None` | serial device 名 |
| `controller.serial.protocol` | `str` | `"CH552"` | serial protocol 名 |
| `controller.serial.baudrate` | `int` | `9600` | serial baudrate |
| `controller.swbt.adapter` | `str` | `"usb:0"` | Bumble が開く Bluetooth adapter |
| `controller.swbt.key_store_path` | `str | None` | `".nyxpy/swbt/switch-bond.json"` | bond 情報の保存先 |
| `controller.swbt.connect_timeout_sec` | `float` | `30.0` | 接続 timeout 秒 |
| `controller.swbt.allow_pairing` | `bool` | `False` | 初回 pairing を許可するか |
| `controller.swbt.report_period_us` | `int` | `8000` | HID report 周期 |
| `controller.swbt.device_name` | `str` | `"Pro Controller"` | Switch 側へ見せる device 名 |
| `controller.swbt.diagnostics_path` | `str | None` | `None` | diagnostics trace の保存先 |
| `controller.swbt.connect_on_open` | `bool` | `True` | port 作成時に接続するか |
| `controller.swbt.invert_stick_y` | `bool` | `False` | stick Y 軸を反転するか |

### CLI 仕様

`--controller` を serial protocol 生成より前に解決する。

```console
nyxpy run sample_macro --controller serial --serial COM3 --capture Camera1
nyxpy run sample_macro --controller swbt --bt-adapter usb:0 --capture Camera1
nyxpy run sample_macro --controller swbt --bt-adapter usb:0 --bt-pair --capture Camera1
```

`--serial` は serial backend のときだけ必須である。swbt backend では不要であり、未指定でも parse error にしない。swbt backend では `ProtocolFactory.resolve_baudrate()` と `create_protocol()` を呼ばない。

### service lifetime

`SwbtControllerOutputPortFactory` が `SwbtGamepadService` を所有する。service key は少なくとも `adapter`、`key_store_path`、`report_period_us`、`device_name`、`diagnostics_path`、`connect_on_open` を含む。`allow_pairing` と `connect_timeout_sec` は接続試行ごとの値として扱い、接続済み service の key には含めない。

`SwbtControllerOutputPort.close()` は neutral を送る。transport の完全 close は factory の `close()` が行う。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | backend 名不正、swbt extra 未導入、adapter open 失敗、connect timeout |
| `DeviceError` | close 後の apply、送信失敗、service lifecycle 不整合 |
| `UnsupportedSwbtInputError` | 3DS button、touch、keyboard、sleep control など swbt backend 非対応入力 |
| `NotImplementedError` | `keyboard()`、`type_key()`、`touch_down()`、`disable_sleep()` など API として存在するが swbt では実装しない操作 |

### シングルトン管理

新規グローバル singleton は追加しない。CLI と GUI の composition root が factory lifetime を所有し、factory が service lifetime を所有する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_nyx_swbt_input_mapper_*` | button / hat / stick / `invert_stick_y` の変換 |
| ユニット | `test_swbt_controller_output_port_*` | `press` / `hold` / `release` / `close` の状態遷移 |
| ユニット | `test_swbt_controller_output_port_rejects_unsupported_inputs` | 3DS / touch / keyboard / sleep control が silent failure にならない |
| ユニット | `test_swbt_gamepad_service_*` | fake `SwitchGamepad` による open / connect / apply / neutral / close と例外変換 |
| ユニット | `test_controller_settings_normalization_*` | 既存 serial 設定と `controller.*` schema の正規化 |
| ユニット | `test_run_cli_controller_options_*` | swbt backend では `--serial` 不要、serial backend では必須 |
| 結合 | `test_runtime_builder_uses_swbt_factory_without_protocol_factory` | swbt backend で serial protocol 生成を通らない |
| 結合 | `test_runtime_macro_press_a_with_dummy_swbt_service` | `Command.press(Button.A)` が dummy service へ反映される |
| ハードウェア | `test_swbt_pair_and_reconnect` | `@pytest.mark.realdevice` / `@pytest.mark.swbt` で pairing と reconnect を確認する |
| ハードウェア | `test_swbt_button_and_stick_reflection` | 実機で button、D-pad、stick、neutral を確認する |

実装中の通常検証は次を使う。

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests/unit/ tests/integration/ -m "not realdevice and not swbt"
```

実機検証は環境があるときだけ次を使う。

```console
uv run pytest tests/hardware/ -m swbt --bt-adapter usb:0 --bt-key-store .nyxpy/swbt/test-switch.json
```

## 6. 実装チェックリスト

- [ ] `local_022`: `ControllerOutputPortFactory` を `SerialControllerOutputPortFactory` へ改名し、旧名 alias を残さず呼び出し元とテストを更新する。
- [ ] `local_022`: `SerialControllerConfig` / `SwbtControllerConfig` / `ControllerConfig` を追加する。
- [ ] `local_022`: `controller.*` settings schema と既存 serial 設定からの正規化を追加する。
- [ ] `local_022`: 既存 serial backend の CLI、runtime、unit test を通す。
- [ ] `local_023`: `pyproject.toml` に `swbt` optional dependency を追加する。
- [ ] `local_023`: `NyxSwbtInputMapper` を実装し、現行 NyX button 名を `swbt-python` の button 名へ変換する。
- [ ] `local_023`: `SwbtControllerOutputPort` を実装し、port close は neutral のみにする。
- [ ] `local_023`: `SwbtGamepadService` を実装し、fake `SwitchGamepad` 注入で単体テスト可能にする。
- [ ] `local_023`: `SwbtControllerOutputPortFactory` を実装し、service key と factory close を管理する。
- [ ] `local_023`: mapper / port / service / factory の単体テストを追加して通す。
- [ ] `local_024`: `MacroRuntimeBuilder` の controller factory 構成を config ベースへ更新する。
- [ ] `local_024`: CLI に `--controller` と `--bt-*` option を追加する。
- [ ] `local_024`: swbt backend で serial protocol 生成が呼ばれないことをテストする。
- [ ] `local_024`: dummy swbt service を使った runtime 結合テストを追加して通す。
- [ ] `local_025`: GUI に backend 選択、adapter refresh、pair once、reconnect、disconnect を追加する。
- [ ] `local_025`: GUI で macro 実行中の manual input を無効化する。
- [ ] `local_025`: GUI と runtime が同じ `SwbtGamepadService` を共有することを確認する。
- [ ] `local_026`: 実機環境で pairing / reconnect / button / stick / neutral を確認する。
- [ ] `local_026`: stick Y 軸の既定値を実機結果で確定し、必要なら `invert_stick_y` 既定値を更新する。
- [ ] `local_026`: swbt public flush の要否を短押し実機テストで判断する。
- [ ] `local_026`: 利用者 docs と完了記録を更新する。
- [ ] 各マイルストーン: `uv run ruff format .` を実行する。
- [ ] 各マイルストーン: `uv run ruff check .` を実行する。
- [ ] 各マイルストーン: `uv run ty check src/nyxpy --output-format concise --no-progress` を実行する。
- [ ] 各マイルストーン: 該当範囲の `uv run pytest` を実行する。
- [ ] 全子仕様の必須セクション、依存関係、対象ファイル、完了条件に矛盾がないことを監査する。

## 7. 子仕様分割

| 子仕様 | 対応範囲 | 依存 | 完了条件 |
|--------|----------|------|----------|
| `local_021/SWBT_CONTROLLER_BACKEND.md` | 親計画、設計判断の取り込み、実装分割の確定 | なし | この文書と子仕様がレビュー可能な状態で commit されている |
| `local_022/SWBT_CONTROLLER_FOUNDATION.md` | serial factory 改名、controller config、settings 正規化 | `local_021` | 既存 serial backend の挙動が変わらず、swbt import が増えていない |
| `local_023/SWBT_CORE_ADAPTER_SERVICE.md` | swbt optional dependency、mapper、port、service、factory、dummy / fake | `local_022` | 実機なしで button / hat / stick、port state、service lifecycle を検証できる |
| `local_024/SWBT_RUNTIME_CLI_INTEGRATION.md` | runtime builder、CLI option、dummy runtime integration | `local_022`, `local_023` | `--controller swbt` で serial protocol 生成を通らず、`--serial` が不要になる |
| `local_025/SWBT_GUI_SHARED_SERVICE.md` | GUI backend 選択、shared service、manual input 制御 | `local_022`, `local_023`, `local_024` | GUI と runtime が接続を共有し、macro 実行中の manual input が無効化される |
| `local_026/SWBT_REALDEVICE_DOCS_CLOSEOUT.md` | 実機検証、Y 軸既定、短押し flush 要否、利用者 docs、完了記録 | `local_022` から `local_025` | pairing / reconnect / button / D-pad / stick / neutral を実機で確認して記録する |

依存が強いものは同じ子仕様へまとめる。`SwbtControllerOutputPort`、`SwbtGamepadService`、`SwbtControllerOutputPortFactory` は lifecycle と state contract が密接なため `local_023` に集約する。実機検証、利用者 docs、親計画の closeout は結果の証跡を同じ文書で扱うため `local_026` に集約する。

子仕様は別々に commit できる粒度にする。GUI と実機検証は環境依存と確認観点が違うため、runtime / CLI 実装に混ぜない。

`local_021` に実装コードを含めない。`local_021` は子仕様の親計画と矛盾監査の起点に限定する。

## 8. 未確定事項

| 項目 | 現時点の扱い | 確定方法 |
|------|--------------|----------|
| stick Y 軸の既定 | `invert_stick_y=false` で開始 | 実機で上方向、下方向を確認する |
| swbt public flush の要否 | NyX port は周期 report 反映を前提に実装 | 短押し duration の実機確認で不足があれば `swbt-python` 側へ public flush 追加を検討する |
| GUI diagnostics の既定保存先 | 固定 path または無効 | 初期 GUI 実装時に artifact lifetime と衝突しない値を選ぶ |
| 実機テストの自動判定 | 初期は人手確認を含む | trace と画面側の確認方法が固まったら自動判定へ拡張する |

## 9. 全体完了条件

- 既存 serial backend の CLI、runtime、テストが壊れていない。
- swbt extra 未導入環境で serial backend が import error なしに動く。
- swbt extra 導入環境で `--controller swbt` を選べる。
- swbt backend では `--serial` が不要で、serial protocol 生成が呼ばれない。
- 既存マクロが `Command` API を変更せず swbt backend で実行できる。
- `Command` / `MacroRuntime` / `ExecutionContext` が swbt を import していない。
- GUI と runtime が同じ `SwbtGamepadService` 接続を共有し、macro 実行中の manual input が無効化される。
- close、cancel、failure 時に neutral が試みられる。
- swbt 非対応操作が silent failure にならない。
- 実機で pairing、reconnect、button、D-pad、stick、neutral の挙動が確認されている。

## 10. local_021 の完了条件

- 親計画として必要な対象ファイル、設計方針、テスト方針、マイルストーン分割が記述されている。
- `docs/architecture/swbt-integration/` の設計判断と矛盾していない。
- `local_021` は実装コードを含めず、子仕様の親計画と矛盾監査の起点に限定する判断が明記されている。
- プレースホルダや未処理を示す仮テキストが残っていない。
