# swbt 直接送信型移行仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/swbt/`
> **目的**: swbt backend を周期送信型から直接送信型へ統一する
> **関連ドキュメント**: [swbt integration](../../../../docs/architecture/swbt-integration/index.md)、[実機検証仕様](../../local_026/SWBT_REALDEVICE_DOCS_CLOSEOUT.md)
> **既存ソース**: `src/nyxpy/framework/core/hardware/swbt/`
> **破壊的変更**: あり

## 1. 概要

### 1.1 目的

Project_NyX の swbt backend を `DirectProController` / `DirectJoyConL` / `DirectJoyConR` へ統一する。NyX が所有する完全入力状態と同期 `ControllerOutputPort` 契約を維持し、操作ごとに `send(state)` で入力レポートを1件送る。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| 直接送信型 | 利用者操作ごとに完全な `InputState` を `send(state)` で1件送る swbt controller |
| 周期送信型 | 保持した `InputState` を report loop が一定間隔で送る swbt controller |
| 完全入力状態 | button、D-pad、left/right stick、IMU frameを合成した1件の `InputState` |
| session adapter | NyX内部の同期 `apply(state)` をswbtの非同期 `send(state)`へ変換する `SwbtControllerSession` |
| pairing profile | controller shape、adapter identity、bond keyを保持するswbt-python schema v2 JSON |
| 送信完了 | Bumbleの送信処理が入力レポートを受理した状態。HCI完了やSwitch画面への反映完了は含まない |

### 1.3 背景・問題

現行backendは `ProController` / `JoyConL` / `JoyConR` と `apply(state)` を使う。短い押下は周期report loopが押下状態を観測する時刻に依存し、NyXの操作と入力レポートが1対1にならない。

NyX側は `NyxSwbtState` を正本として操作ごとに完全な `InputState` を生成している。この状態所有を変更せず、sessionの下位呼び出しだけを直接送信へ変更できる。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| controller class | `ProController` / `JoyConL` / `JoyConR` | 対応する `Direct*Controller` |
| 通常入力の下位API | `apply(state)` | `send(state)` |
| 1操作の通常入力レポート | report loopの観測回数に依存 | 1件 |
| `report_period_us` | config、settings、session keyに存在 | 現行設定と実装から削除 |
| NyX入力状態の確定 | 下位呼び出し成功後 | 維持 |

### 1.5 着手条件

- GitHub Issue #196 の実装項目と完了条件を正本とする。
- Issue #195 のswbt-python 0.5.3およびschema v2 pairing profile移行が完了している。
- swbt-python 0.5.4が公開済みであり、Direct controllerの公開APIを維持している。
- Direct controllerは生成、Pair、Reconnectの完了後に入力可能であるものとする。
- 実機操作は `@pytest.mark.realdevice` と `@pytest.mark.swbt` を付け、通常gateと分離する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` / `uv.lock` | 変更 | swbt-python 0.5.4を固定 |
| `src/nyxpy/framework/core/hardware/swbt/config.py` | 変更 | `report_period_us` をconfigから削除 |
| `src/nyxpy/framework/core/hardware/swbt/session.py` | 変更 | Direct class解決、`send()`呼び出し、周期report待機の削除 |
| `src/nyxpy/framework/core/hardware/swbt/factory.py` | 変更 | session keyから周期値を削除 |
| `src/nyxpy/framework/core/io/controller_config.py` | 変更 | settingsから周期値を読み取らない |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | schemaと既存設定から周期値を削除し、移行通知を生成 |
| `src/nyxpy/gui/app_services.py` | 変更 | runtime再構築対象keyから周期値を削除 |
| `tests/unit/` / `tests/integration/` / `tests/gui/` | 変更 | Direct class、send、状態確定、設定移行、runtime経路を検証 |
| `tests/hardware/` | 変更 | profile再利用、直接送信、neutral、GUI、macroを検証 |
| `docs/architecture/swbt-integration/` | 変更 | 直接送信契約と公開APIを記載 |
| `docs/user-guide/` | 変更 | 短押しと送信完了の保証範囲を記載 |
| `spec/agent/wip/local_026/SWBT_REALDEVICE_DOCS_CLOSEOUT.md` | 変更 | 実機testとevidenceを直接送信型へ更新 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

`SwbtControllerOutputPort` は `NyxSwbtState` と `NyxSwbtInputMapper` を所有し、完全な `InputState` をsessionへ渡す。`SwbtControllerSession` はswbt controllerと専用asyncio event loopを所有し、NyXの同期呼び出しをswbtの非同期APIへ橋渡しする。

```text
ControllerOutputPort
  -> SwbtControllerOutputPort
  -> NyxSwbtInputMapper.to_input_state()
  -> SwbtControllerSession.apply()
  -> Direct*Controller.send()
```

### 公開 API 方針

マクロ、GUI、CLIへ `Direct*Controller` とswbtの `send()` を公開しない。NyX内部の `SwbtControllerSession.apply()` は、周期型との互換目的ではなく、`ControllerOutputPort` と下位backendの送信方式を分離するadapterとして維持する。

`press()` / `hold()` / `release()` / `imu()` は現行シグネチャを維持する。上流の部分更新APIへ委譲せず、毎回完全な入力状態を送る。

### 後方互換性

破壊的変更である。周期型を選ぶ設定、旧controller class、`report_period_us` のaliasや互換shimは残さない。

既存 `global.toml` の `controller.swbt.report_period_us` は読み込み時に削除して保存し、「直接送信型への切り替えにより不要になった」ことを移行通知へ記録する。pairing profileはcontroller shapeが同じDirect classからそのまま読み込み、NyX独自変換を行わない。

### レイヤー構成

`framework.core.hardware.swbt` だけがswbt-pythonの具象classと入力型に依存する。GUI、CLI、runtimeはframeworkのconfig、factory、portを使う。frameworkからGUI、CLI、macroへの逆依存を追加しない。新規global singletonは追加しない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| 通常操作あたりの `send()` | 1回 |
| `release()`引数なしの `neutral()` | 1回 |
| port生成時の `neutral()` | 1回 |
| close時の終端neutral | `close(neutral=True)` で1回 |
| API完了保証 | swbt送信処理の完了まで。Switch側の反映完了は保証しない |

### 並行性・スレッド安全性

sessionの `RLock` と専用asyncio event loop threadを維持し、Pair、Reconnect、send、neutral、closeを直列化する。portの `RLock` と「送信成功後だけ `_state` を更新する」順序を維持する。

Direct controllerの生成、Pair、Reconnect完了を利用可能状態とし、周期report counterの増加を待たない。周期型のreport開始問題に対するNyX独自の待機や再送処理は追加しない。

### 対象外

- 周期送信型と直接送信型を選択する設定
- 周期送信型のreport loopに対する回避策
- HCI完了またはSwitch画面反映完了を待つ同期処理
- pairing profileの独自変換
- swbtのprivate module、transport、report builderへの依存

## 4. 実装仕様

### 公開インターフェース

```python
@dataclass(frozen=True, slots=True)
class SwbtControllerConfig:
    model: SwbtControllerModel
    adapter: str | None
    profile_path: Path
    connect_timeout_sec: float = 30.0


class SwbtControllerSessionProtocol(Protocol):
    def apply(self, state: object) -> None: ...
    def neutral(self) -> None: ...
    def status(self) -> object: ...
    def close(self) -> None: ...
```

### Controller class解決

| `SwbtControllerType` | swbt root public class |
|----------------------|------------------------|
| `PRO_CONTROLLER` | `DirectProController` |
| `JOY_CON_L` | `DirectJoyConL` |
| `JOY_CON_R` | `DirectJoyConR` |

constructorと `create_profile()` には `adapter`、`profile_path`、`diagnostics` を渡す。`report_period_us` は渡さない。

### 入力状態と失敗時の扱い

```text
現在のNyxSwbtState
  -> 候補状態を生成
  -> 完全なInputStateへ変換
  -> session.apply()
  -> Direct*Controller.send()
  -> 成功時だけ候補状態を現在状態へ確定
```

`release()` の引数が空の場合はDirect controllerの `neutral()` を呼び、成功後だけNyX側状態をneutralへ確定する。送信例外時は直前に成功した状態を維持する。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `controller.swbt.controller_type` | `str` | `"pro-controller"` | Direct classのcontroller shape |
| `controller.swbt.adapter` | `str | None` | `None` | Bumbleから開く専用adapter |
| `controller.swbt.profile_path` | `str | None` | controller type別path | schema v2 profile |
| `controller.swbt.connect_timeout_sec` | `float` | `30.0` | Pair / Reconnect timeout |

### エラーハンドリング

| 例外または状態 | NyX側の扱い |
|----------------|-------------|
| Direct `send()` 失敗 | 既存の `map_swbt_exception()` で変換し、NyX側状態を更新しない |
| Direct `neutral()` 失敗 | 既存の `map_swbt_exception()` で変換し、NyX側状態を更新しない |
| `connection_state != "connected"` | `NYX_SWBT_NOT_CONNECTED` |
| controller type不一致profile | `NYX_SWBT_PROFILE_CONTROLLER_MISMATCH` |
| 旧 `report_period_us` 設定 | 値を削除して移行通知を出す |

### シングルトン管理

該当なし。sessionとfactoryのlifetimeはruntime builder、GUI services、CLI commandが所有する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_resolve_swbt_controller_class_returns_direct_class` | controller typeとDirect classの対応 |
| ユニット | `test_session_apply_calls_send_once` | sessionの外部 `apply()` が下位 `send()` を1回呼ぶ |
| ユニット | `test_create_swbt_controller_omits_report_period` | Direct constructorへ周期値を渡さない |
| ユニット | `test_create_swbt_profile_omits_report_period` | Direct `create_profile()` へ周期値を渡さない |
| ユニット | `test_pair_does_not_wait_for_periodic_report` | Pair完了後にreport counter増加を待たない |
| ユニット | `test_reconnect_does_not_wait_for_periodic_report` | Reconnect完了後にreport counter増加を待たない |
| ユニット | `test_settings_store_removes_legacy_report_period` | 既存設定の削除、保存、移行通知 |
| ユニット | `test_port_commits_state_only_after_send` | send成功後だけ状態を確定し、失敗時はrollback |
| ユニット | `test_session_key_ignores_removed_report_period` | cache keyがcontroller shape、adapter、profileだけで決まる |
| 結合 | `test_swbt_runtime_uses_direct_send_path` | CLIマクロ経路が完全状態を操作順に送る |
| GUI | `test_swbt_settings_apply_without_report_period` | GUI設定反映が削除済みkeyへ依存しない |
| ハードウェア | `test_swbt_pair_realdevice` | Direct classでschema v2 profileを作成してPair |
| ハードウェア | `test_swbt_reconnect_realdevice` | 既存profileをDirect classで再利用 |
| ハードウェア | `test_swbt_*_manual_realdevice` | button、D-pad、stick、IMU、partial release、neutral |
| ハードウェア | `test_swbt_macro_reconnect_realdevice` | macro経路の直接送信 |
| ハードウェア | `test_swbt_gui_lifecycle_realdevice` | GUI Pair、Reconnect、手動入力、Disconnect |

## 6. 実装チェックリスト

- [x] Direct class解決とroot public API import
- [x] swbt-python 0.5.4への依存更新
- [x] session `apply()` からDirect `send()`への同期橋渡し
- [x] 周期report開始待機の削除
- [x] `report_period_us` のconfig、session key、settings schemaからの削除
- [x] 既存 `global.toml` の移行とtechnical log
- [x] portの完全状態送信とrollback契約の回帰
- [x] unit / integration / GUIテスト
- [x] architecture docsと利用者向け文書
- [x] ruff / ty / pytest / MkDocs strict gate
- [ ] Pro ControllerのPair、Reconnect、入力、neutral実機確認
- [ ] Joy-Con L/Rのprofile再利用と確認範囲の記録

## 7. 非実機検証結果

2026-07-26にDirect送信型への移行後、次を実行した。swbt-python 0.5.4への依存更新後にも同じgateを再実行した。

```console
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run mkdocs build --strict
uv run pytest --basetemp=<repository外の一時directory>
```

ruff、ty、MkDocs strictは成功した。pytestは897件を収集し、877件成功、実機要件の20件をskipした。Direct class解決、同期 `apply()` から非同期 `send()` への橋渡し、Pair / Reconnect後に周期reportを待たないこと、周期設定の移行、完全状態とrollback契約は非実機テストで確認済みである。

Pro ControllerとJoy-Con L/Rを使うPair、Reconnect、既存profile再利用、Switch画面上の入力、short pressは未検証である。周期送信型で取得した `local_027` の実機結果をDirect送信型の完了証拠には使わない。
