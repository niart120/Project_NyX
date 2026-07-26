# swbt-python 0.5.3 ペアリングプロファイル移行仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/swbt/`
> **目的**: swbt-python 0.5.3 の schema v2 pairing profile 契約へ移行する
> **関連ドキュメント**: [swbt integration](../../../../docs/architecture/swbt-integration/index.md)、[実機検証仕様](../../local_026/SWBT_REALDEVICE_DOCS_CLOSEOUT.md)
> **既存ソース**: `src/nyxpy/framework/core/hardware/swbt/`
> **破壊的変更**: あり

## 1. 概要

### 1.1 目的

Project_NyX の swbt backend を `swbt-python==0.5.3` に固定し、初回 Pair、再Pair、Reconnect、runtime 入力を schema v2 pairing profile で動作させる。旧キーストアと schema v1 profile は変換せず、新しい path での再ペアリングを利用者へ要求する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| pairing profile | swbt-python 0.5.3 が controller 種別、adapter identity、bond key を保持する schema v2 JSON |
| 初回 Pair | profile が存在しない path に `controller_cls.create_profile(...)` を実行する操作 |
| 再Pair | Pair 失敗またはキャンセル後に残った profile を constructor へ渡し、`pair()` を再実行する操作 |
| Reconnect | 保存済み profile を constructor へ渡し、`reconnect()` する操作 |
| session | swbt controller と専用 asyncio event loop の lifetime を所有し、同期 `ControllerOutputPort` と橋渡しする部品 |
| 旧キーストア | swbt-python 0.2 系で使っていた JSON。schema v2 profile へ変換しない |

### 1.3 背景・問題

現行実装は `swbt-python>=0.2.0,<0.3.0` と旧キーストア引数を前提にしている。0.5.3 では constructor が `profile_path` を受け取り、初回作成は非同期 class method `create_profile()` が接続済み controller を返す。旧 JSON と schema v1 profile に互換読込はない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| swbt-python | `>=0.2.0,<0.3.0` | `==0.5.3` |
| Bumble | `0.0.230` | `0.0.233` |
| 新規 profile schema | 旧キーストア | schema v2 |
| profile failure | 汎用 code 中心 | 原因別 `NYX_SWBT_PROFILE_*` code |
| Reconnect UI | adapter 選択だけで有効 | profile file が存在するときだけ有効 |

### 1.5 着手条件

- GitHub Issue #195 の実装項目と完了条件を正本とする。
- swbt-python 0.5.3 の公開 signature と例外を導入済み package から確認する。
- 実機操作は `@pytest.mark.realdevice` と `@pytest.mark.swbt` を付け、通常 gate と分離する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` / `uv.lock` | 変更 | swbt-python 0.5.3 と Bumble 0.0.233 を固定 |
| `src/nyxpy/framework/core/hardware/swbt/config.py` | 変更 | profile 名、path、config を正 API に変更 |
| `src/nyxpy/framework/core/hardware/swbt/session.py` | 変更 | `create_profile()` と既存 profile の分岐、controller 所有権 |
| `src/nyxpy/framework/core/hardware/swbt/factory.py` | 変更 | profile path cache key、Pair 前 open の削除 |
| `src/nyxpy/framework/core/hardware/swbt/errors.py` | 変更 | profile と adapter recovery の個別 error code |
| `src/nyxpy/framework/core/io/controller_config.py` | 変更 | workspace root 基準の profile path 解決 |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | 旧設定 key の除去と新しい既定 path への移行 |
| `src/nyxpy/cli/` | 変更 | `--profile` / `--swbt-profile` |
| `src/nyxpy/gui/` | 変更 | 表示名、保存先、既定候補、Reconnect 有効条件 |
| `tests/unit/` / `tests/integration/` / `tests/gui/` | 変更 | profile 契約と既存 mapper / port 回帰 |
| `tests/hardware/` | 変更 | schema v2 profile と diagnostics evidence |
| `docs/user-guide/` | 変更 | 操作、移行、error 対応 |
| `docs/architecture/swbt-integration/` | 変更 | 0.5.3 の設計契約 |
| `spec/agent/wip/local_026/SWBT_REALDEVICE_DOCS_CLOSEOUT.md` | 変更 | 実機環境変数と evidence を profile 名へ更新 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

swbt-python の非同期 lifecycle は `SwbtControllerSession` 内へ閉じる。CLI、GUI、runtime は同期 factory と `ControllerOutputPort` だけを使い、swbt controller を直接所有しない。

### 公開 API 方針

Project_NyX の設定と CLI は `profile` に統一する。旧 CLI option と旧 Python 属性の alias は追加しない。設定ファイルの旧 key だけは一度読み取り、新 profile の既定 path を設定して除去する。

### 後方互換性

破壊的変更である。旧キーストアと schema v1 profile は読み込まず、自動変換・削除・上書きもしない。移行後は別名の schema v2 profile を作成する。

### レイヤー構成

`framework.core.hardware.swbt` は swbt-python に依存する。GUI と CLI は framework の config、factory、error を使う。framework から GUI / CLI への逆依存は作らない。新規 global singleton は追加しない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| report period 既定値 | `8000us` を維持 |
| 同期 bridge timeout | swbt 接続 timeout より 1 秒以上長い |
| active session | 同一 adapter につき最大 1 |

### 並行性・スレッド安全性

session の `RLock` と専用 asyncio event loop thread を維持する。Pair / Reconnect のキャンセル時は coroutine の終了処理を待ち、close と loop stop の例外を失わない。GUI は lifecycle 操作を background worker で実行する。

swbt-python 0.5.3 の `apply()` は送信済み入力を保証しない。Pair / Reconnect 成功後は `GamepadStatus.report_counters[0x30]` が増えるまで待ち、周期 input report の送信開始を確認してから入力を許可する。接続直後の subcommand reply holdoff 中に押下・解放を完了すると Switch へ入力が届かないためである。

## 4. 実装仕様

### 公開インターフェース

```python
@dataclass(frozen=True, slots=True)
class SwbtControllerConfig:
    model: SwbtControllerModel
    adapter: str | None
    profile_path: Path
    connect_timeout_sec: float = 30.0
    report_period_us: int | None = 8000


class SwbtControllerSession:
    def pair(self, *, timeout_sec: float, cancellation_event: Event | None = None) -> None: ...
    def reconnect(
        self,
        *,
        timeout_sec: float,
        cancellation_event: Event | None = None,
    ) -> None: ...
```

### Pair 状態遷移

```text
profileなし
  -> controller_cls.create_profile(...)
  -> 接続済みcontrollerをsessionが所有

profileあり
  -> controller_cls(profile_path=...)
  -> open()
  -> pair()

Reconnect
  -> controller_cls(profile_path=...)
  -> open()
  -> reconnect()
```

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `controller.swbt.profile_path` | `str | None` | controller type 別 path | schema v2 profile |
| `controller.swbt.connect_timeout_sec` | `float` | `30.0` | Pair / Reconnect timeout |
| `controller.swbt.report_period_us` | `int | None` | `8000` | 周期 report 間隔 |
| `--profile` | `Path | None` | settings | swbt lifecycle command override |
| `--swbt-profile` | `Path | None` | settings | macro run override |

### エラーハンドリング

| 例外クラス | NyX code |
|------------|----------|
| `FileNotFoundError` | `NYX_SWBT_PROFILE_NOT_FOUND` |
| `FileExistsError` | `NYX_SWBT_PROFILE_ALREADY_EXISTS` |
| `InvalidProfileError` | `NYX_SWBT_PROFILE_INVALID` |
| `ProfileControllerMismatchError` | `NYX_SWBT_PROFILE_CONTROLLER_MISMATCH` |
| `InvalidKeyStoreError` | `NYX_SWBT_PROFILE_KEY_DATA_INVALID` |
| `AdapterIdentityRecoveryRequired` | `NYX_SWBT_ADAPTER_IDENTITY_RECOVERY_REQUIRED` |
| input report readiness timeout | `NYX_SWBT_INPUT_REPORT_NOT_READY` |

adapter identity recovery の利用者向け本文には、USB Bluetooth ドングルを抜き差ししてから再試行する手順を含める。

### シングルトン管理

該当なし。session と factory の lifetime は runtime builder、GUI services、CLI command が所有する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_session_pair_creates_profile_and_owns_returned_controller` | 初回作成と所有権 |
| ユニット | `test_session_waits_for_periodic_input_report_after_reconnect` | 接続後に `0x30` 周期 input report の開始を待つ |
| ユニット | `test_profile_errors_map_to_individual_nyx_codes` | error code の個別変換 |
| ユニット | `test_settings_store_migrates_legacy_swbt_key_without_touching_old_file` | 旧設定除去と旧file保持 |
| ユニット | `test_factory_*` | cache key、競合 adapter、close retry |
| 結合 | `test_swbt_runtime_cli_integration.py` | runtime Reconnect と入力 |
| GUI | `test_reconnect_requires_existing_profile_file` | profile file による有効条件 |
| ハードウェア | `test_swbt_pair_realdevice` | schema v2 profile 作成と初回 Pair |
| ハードウェア | `test_swbt_reconnect_realdevice` | active reconnect |
| ハードウェア | `test_swbt_macro_reconnect_realdevice` | runtime factory のReconnectとマクロ入力 |
| ハードウェア | `test_swbt_gui_lifecycle_realdevice` | GUI service のPair / Reconnect / Disconnect |
| ハードウェア | `test_swbt_*_manual_realdevice` | Button、D-pad、stick、IMU、neutral、Joy-Con |

## 6. 実装チェックリスト

- [x] swbt-python 0.5.3 と Bumble 0.0.233 の依存解決
- [x] profile 設定 model と CLI surface
- [x] 初回 `create_profile()` と既存 profile 再Pair
- [x] profile / adapter recovery error 変換
- [x] 旧設定 key の除去と旧file保持
- [x] GUI 表示名、候補、Reconnect 有効条件
- [x] 利用者向け文書と architecture 文書
- [x] unit / integration / GUI 全 gate
- [x] ruff / ty / MkDocs strict gate
- [x] Pro Controller の新規 Pair / active Reconnect / 入力 / neutral
- [x] GUI Pair / Reconnect / Disconnect と macro Reconnect
- [x] Joy-Con L/R の Pair / Reconnect
- [x] diagnostics evidence と未確認範囲の記録

## 7. 実機検証結果

2026-07-26 に `usb:0`（CSR8510 A10）で実施した。Pro Controller は Pair、Reconnect、macro 経路の A 入力、Button、D-pad、left/right stick、16/33/50 ms short press、close 後 neutral、GUI Pair/Disconnect/Reconnect/Disconnect を確認した。Joy-Con (L)/(R) は個別 schema v2 profile の Pair と Reconnect を確認した。

修正前の macro trace は protocol ready 後の periodic `0x30` report が 0 件で、close 時の neutral report だけだった。修正後は periodic report が 15 件記録され、Switch 画面で A 入力による遷移を確認した。D-pad `UPRIGHT` は観察画面で上として反映され、斜めの右成分は未確認である。IMU gyro 値自体の画面上の反映も未確認だが、送信中に切断・想定外入力は発生しなかった。
