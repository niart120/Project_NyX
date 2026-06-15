# ponkan-python 0.2.0 検出 API 取り込み 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/`
> **目的**: `ponkan-python 0.2.0` で公開された profile / discovery / structured error API を NyX の framework hardware 層へ取り込み、直接接続型キャプチャの診断経路を明確化する。
> **関連ドキュメント**: `spec/agent/complete/local_017/PONKAN_CAPTURE_SOURCE.md`, `spec/agent/complete/local_019/CAPTURE_SOURCE_GUI_DEPENDENCY_AND_SIMPLIFICATION.md`
> **実装コミット**: `3384e15 feat(capture): ponkan 0.2.0の検出APIに対応`

## 1. 概要

### 1.1 目的

`ponkan-python` の最低バージョンを `0.2.0` に更新し、上流の profile registry、`list_capture_devices()`、structured `CaptureError` を NyX 側の framework API として利用できるようにする。GUI の通常メニュー描画では引き続き `ponkan` 本体を import せず、実機 listing は明示的な診断操作として分離する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| `ponkan-python` | PyPI 配布名。import package は `ponkan` |
| profile registry | `ponkan` が profile id から capture target metadata を解決する registry。NyX は profile id の列挙を保持しない |
| capture profile | profile registry が返す capture target metadata。`model`、`default_output`、`supported_colorspaces` などを持つ |
| discovery API | `ponkan.list_capture_devices()` が返す `CaptureDeviceDiscovery` 系の構造化 listing API |
| discovery snapshot | NyX 側で `ponkan` の dataclass を直接公開せずに写し取る immutable な結果 object |
| `CaptureError` | `ponkan` の package-level failure base。`code`、`profile`、`backend`、`reason`、`recoverable`、`remediation` を持つ |
| `DeviceDiscoveryService` | NyX framework の serial / camera / window / ponkan capture discovery の入口 |
| `PonkanCaptureDevice` | `ponkan.open_capture()` を NyX の `CaptureDeviceInterface` として扱う adapter |
| optional dependency gate | `ponkan-python` 未導入環境で通常 GUI 導線を隠す軽量判定 |

### 1.3 背景・問題

local_017 の初期取り込み時点では `ponkan-python 0.1.2` を対象にしていたため、NyX は `open_capture()` と `CaptureReader.read()` だけを使い、デバイス listing や失敗理由の構造化は NyX 側で扱っていなかった。その後 `ponkan-python 0.2.0` で `list_capture_profiles()`、`get_capture_profile()`、`list_capture_devices()`、`CaptureDeviceDiscovery`、structured `CaptureError` が公開された。

NyX 側でこれらを取り込まない場合、直接接続型キャプチャの「依存未導入」「backend unavailable」「device not found」「rejected device」などを framework 層で区別しにくい。一方で、GUI メニュー生成に listing API を直接使うと、local_019 で定めた「通常メニュー描画では `ponkan` 本体を import しない」という dependency gate を破る。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| `ponkan-python` 最低版 | `>=0.1.2,<0.2.0` | `>=0.2.0,<0.3.0` |
| device listing | NyX 側に公開 API なし | `DeviceDiscoveryService.detect_ponkan_capture_devices_result()` で取得できる |
| 上流 object の露出 | 未定義 | `ponkan` dataclass を NyX 公開 surface に直接出さず snapshot へ写す |
| GUI 通常メニュー | `find_spec("ponkan")` の軽量判定 | 維持。listing API は通常メニュー描画に使わない |
| open 失敗 details | `backend` と exception class 程度 | upstream `code` / `reason` / `recoverable` / `remediation` を `ConfigurationError.details` に含める |
| profile validation | NyX 側で `n3dsxl` のみ許可 | `get_capture_profile()` に委譲し、上流 registry を正本にする |
| 古い上流 API | `AttributeError` の可能性 | 互換用の NyX error code を追加せず、最低版未満の依存不整合として扱う |

### 1.5 着手条件

- PyPI 最新が `ponkan-python 0.2.0` であることを確認する。
- ローカル `ponkan-python` checkout が tag `v0.2.0` と一致し、差分なしであることを確認する。
- local_019 の GUI dependency gate 方針を維持すること。
- `uv lock`、`ruff`、`ty`、`pytest` が通ること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | optional extra `ponkan` の依存範囲を `ponkan-python>=0.2.0,<0.3.0` に更新する |
| `uv.lock` | 変更 | lock された `ponkan-python` を `0.2.0` に更新する |
| `src/nyxpy/framework/core/hardware/ponkan_discovery.py` | 新規 | `ponkan.list_capture_devices()` の遅延 import adapter と NyX 側 snapshot dataclass を定義する |
| `src/nyxpy/framework/core/hardware/device_discovery.py` | 変更 | `detect_ponkan_capture_devices_result()` と直近 snapshot 保持を追加する |
| `src/nyxpy/framework/core/hardware/ponkan_capture.py` | 変更 | `get_capture_profile()` と structured `CaptureError` details を取り込む |
| `src/nyxpy/framework/core/hardware/capture_source.py` | 変更 | `capture_device_profile` の NyX 側列挙をやめ、profile validation を上流へ委譲する |
| `src/nyxpy/framework/core/hardware/__init__.py` | 変更 | ponkan discovery snapshot と listing function を export する |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | `capture_device_profile` の `choices` を削除する |
| `tests/unit/framework/hardware/test_ponkan_discovery.py` | 新規 | 上流 discovery result の mapping と error mapping を検証する |
| `tests/unit/framework/hardware/test_device_discovery.py` | 変更 | `DeviceDiscoveryService` 経由の ponkan discovery 呼び出しを検証する |
| `tests/unit/framework/hardware/test_capture_source.py` | 変更 | profile validation が NyX 側列挙に固定されないことを検証する |
| `tests/unit/framework/hardware/test_ponkan_capture.py` | 変更 | profile metadata 利用、default output / colorspace、structured error details を検証する |

## 3. 設計方針

### 3.1 アーキテクチャ上の位置づけ

`ponkan_discovery.py` は `core/hardware` の外部ライブラリ adapter である。GUI は `DeviceDiscoveryService` 経由で必要なときだけ明示的に呼び出すことができるが、通常メニュー描画や source combo 表示には使用しない。

依存方向は次のとおりである。

| 呼び出し元 | 呼び出し先 | 方針 |
|------------|------------|------|
| `core/hardware/ponkan_discovery.py` | `ponkan.list_capture_devices()` | 遅延 import する |
| `core/hardware/device_discovery.py` | `list_ponkan_capture_devices()` | framework 内の明示 discovery API として呼ぶ |
| `gui` 通常メニュー | `find_spec("ponkan")` | 維持。listing は行わない |
| `macros/` | `ponkan` | 直接依存しない |

### 3.2 公開 API 方針

上流の `CaptureDeviceDiscovery` / `CaptureDeviceInfo` を NyX の公開 surface にそのまま出さない。NyX は外部依存を optional extra として扱うため、型注釈や利用者 code が `ponkan` の concrete dataclass に依存すると、未導入環境の import 境界が崩れる。

NyX 側では次の snapshot を公開する。

```python
@dataclass(frozen=True)
class PonkanCaptureDeviceDescriptor:
    id: str
    display_name: str
    profile_id: str
    model: str
    backend: str
    backend_preference: str
    vendor_id: int | None
    product_id: int | None
    serial_number: str | None
    product_string: str | None
    product_string_status: str
    connection_status: str
    id_stability: str
    reason: str = "available"
    remediation: str | None = None


@dataclass(frozen=True)
class PonkanCaptureDiscoverySnapshot:
    profile_id: str = "n3dsxl"
    backend_preference: str = "auto"
    resolved_backend: str = ""
    backend_status: str = "unavailable"
    reason: str = "missing_package"
    remediation: str | None = None
    devices: tuple[PonkanCaptureDeviceDescriptor, ...] = ()
    timed_out: bool = False
    errors: tuple[str, ...] = ()
```

### 3.3 後方互換性と破壊的変更

Project NyX の framework はアルファ版であり、互換 shim は追加しない。今回の変更では最低版を `ponkan-python 0.2.0` へ上げ、古い `0.1.x` API をサポート対象から外す。古い API が import 環境に残っている場合のために `NYX_PONKAN_CAPTURE_API_UNSUPPORTED` のような専用分類は追加しない。最低版未満の package が import される状態は、NyX が吸収する runtime error ではなく依存解決の不整合として扱う。

既存の `capture_source_type="capture"`、`capture_provider="ponkan"`、`capture_device_profile`、`ponkan_*` settings は削除しない。これは後方互換性のためだけではなく、現行の runtime 設定 surface として `PonkanCaptureSourceConfig` がまだ利用しているためである。ただし `capture_device_profile` は `n3dsxl` 固定の choice を持たず、profile id の妥当性は `get_capture_profile()` に委譲する。将来、上流 profile API に完全に寄せて低レベル queue / timeout 設定を NyX から隠す場合は別仕様で破壊的変更として扱う。

### 3.4 listing API の取り込み境界

`list_capture_devices()` は USB descriptor / D3XX runtime を見に行く可能性があるため、通常 GUI 表示では呼ばない。呼び出しは `DeviceDiscoveryService.detect_ponkan_capture_devices_result()` のような明示操作に限定する。

timeout は `DeviceDiscoveryService.detect()` と同様に worker thread + `join(timeout_sec)` で扱う。上流呼び出しそのものを強制停止する機構は持たない。これは既存 discovery service の実装方針に合わせたものであり、将来 async cancellation が必要になった場合は device discovery 全体の再設計対象とする。

### 3.5 error details の取り込み方針

`PonkanCaptureDevice` は `ponkan.errors.CaptureError` の structured fields を `ConfigurationError.details` に写す。

| 上流 field | NyX details key |
|------------|-----------------|
| `code` | `upstream_code` |
| `profile` | `upstream_profile` |
| `backend` | `upstream_backend` |
| `reason` | `upstream_reason` |
| `recoverable` | `upstream_recoverable` |
| `remediation` | `upstream_remediation` |

NyX 側の `code` は従来どおり `NYX_PONKAN_CAPTURE_DEPENDENCY_UNAVAILABLE`、`NYX_PONKAN_CAPTURE_OPEN_FAILED`、`NYX_PONKAN_CAPTURE_PROFILE_INVALID` などを維持する。上流 code を NyX code に置き換えないのは、NyX の error taxonomy と上流の capture reason を混同しないためである。

### 3.6 保守性レビュー観点

今回の実装は「壊さないために旧 API を温存する」方向には寄せない。最低版を 0.2.0 へ上げ、古い上流 API 専用の error code や compatibility path は持たない。profile id の列挙も NyX 側に置かず、上流 profile registry を正本にする。一方で、provider/advanced settings の全面再設計は行わない。これは互換性への遠慮ではなく、GUI 表示・runtime config・実機接続範囲が local_017 / local_019 で既に分割されており、今回の目的が listing API、profile registry、structured error の取り込みに限定されるためである。

破壊的変更として今後検討する余地があるものは次である。

| 候補 | 今回扱わない理由 |
|------|------------------|
| `PonkanCaptureSourceConfig` から queue / timeout / timing knobs を削る | 設定ファイルからの advanced tuning をまだ runtime が読んでいる |
| `capture_provider` を削除し `capture_device_profile` だけに寄せる | 将来 provider が増えた場合の責務境界をまだ評価していない |
| `list_capture_profiles()` を GUI 通常メニューの選択肢生成に使う | local_019 の dependency gate と衝突するため、通常表示では `ponkan` 本体を import しない |
| GUI で `list_capture_devices()` を使って物理個体を表示する | local_019 の dependency gate と「個体選択を初期実装に入れない」方針に反する |
| `DeviceDiscoveryService` の timeout model を async cancellation へ置換する | serial / camera / window discovery 全体の再設計が必要 |

## 4. 実装仕様

### 4.1 ponkan discovery adapter

```python
def list_ponkan_capture_devices(
    *,
    profile: str = "n3dsxl",
    backend: str = "auto",
    include_rejected: bool = False,
    lister: PonkanListCaptureDevices | None = None,
) -> PonkanCaptureDiscoverySnapshot: ...
```

`lister` はテスト注入用である。production では `import_module("ponkan")` から `list_capture_devices` を取得する。`ponkan` import 失敗は `reason="missing_package"` の snapshot として返す。`list_capture_devices` 不在や上流呼び出し失敗は `reason=upstream.reason or "unknown"` の snapshot として返し、生の例外を GUI/CLI に漏らさない。ただし古い上流 API のための専用 reason や NyX error code は定義しない。

### 4.2 DeviceDiscoveryService

```python
class DeviceDiscoveryService:
    @property
    def last_ponkan_capture_discovery(self) -> PonkanCaptureDiscoverySnapshot: ...

    def detect_ponkan_capture_devices(
        self,
        *,
        timeout_sec: float = 2.0,
        profile: str = "n3dsxl",
        backend: str = "auto",
        include_rejected: bool = False,
    ) -> tuple[PonkanCaptureDeviceDescriptor, ...]: ...

    def detect_ponkan_capture_devices_result(
        self,
        *,
        timeout_sec: float = 2.0,
        profile: str = "n3dsxl",
        backend: str = "auto",
        include_rejected: bool = False,
    ) -> PonkanCaptureDiscoverySnapshot: ...
```

ponkan discovery は camera capture device list に混ぜない。通常の `detect()` は従来どおり serial / camera だけを返す。direct capture の listing は呼び出し元が明示的に選ぶ。

### 4.3 PonkanCaptureDevice open

`_open_ponkan_capture()` は `get_capture_profile(config.device_profile)` を呼び、profile の `model`、`default_output`、`supported_colorspaces` を `CaptureConfig` に反映する。これにより、NyX 側の profile id と上流の capture 設定値の対応を上流 metadata から得る。

```python
profile = get_capture_profile(config.device_profile)
ponkan_config = capture_config(
    source=profile.model,
    model=profile.model,
    backend=config.ponkan_backend,
    output=profile.default_output,
    colorspace=_opencv_colorspace(profile),
    ...
)
```

`CaptureConfig.for_profile()` や `open_capture(profile=...)` は `ponkan-python 0.2.0` には存在しないため使わない。`CaptureReader.read()` には `output` / `colorspace` を毎回渡さず、`CaptureConfig` で確定した reader 側 default に委譲する。

### 4.4 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|------------|------|
| `capture_source_type` | `str` | `"camera"` | `"capture"` のとき ponkan source を使う |
| `capture_provider` | `str` | `"ponkan"` | 現時点では `"ponkan"` のみ |
| `capture_device_profile` | `str` | `"n3dsxl"` | `get_capture_profile()` に渡す profile id。NyX 側 choices は持たない |
| `ponkan_backend` | `str` | `"auto"` | `list_capture_devices()` / `open_capture()` に渡す backend preference |
| `ponkan_raw_slots` | `int` | `2` | 上流 streaming raw slot 数 |
| `ponkan_output_queue_size` | `int` | `2` | decoded frame queue 容量 |
| `ponkan_drop_policy` | `str` | `"drop_oldest"` | decoded frame queue policy |
| `ponkan_poll_interval` | `float` | `0.004` | frame wait polling interval |
| `ponkan_read_timeout` | `float | None` | `1.0` | reader timeout |
| `ponkan_collect_timing` | `bool` | `False` | timing stats 収集 |

### 4.5 エラーハンドリング

| 条件 | 戻り値 / 例外 |
|------|---------------|
| `ponkan` package missing | `PonkanCaptureDiscoverySnapshot(reason="missing_package")` または `NYX_PONKAN_CAPTURE_DEPENDENCY_MISSING` |
| `list_capture_devices` missing | `PonkanCaptureDiscoverySnapshot(reason="unknown")` |
| 上流 discovery exception | `PonkanCaptureDiscoverySnapshot(backend_status="unavailable", reason=upstream.reason or "unknown")` |
| `get_capture_profile()` 失敗 | `NYX_PONKAN_CAPTURE_PROFILE_INVALID` |
| profile が BGR を support しない | `NYX_PONKAN_CAPTURE_COLORSPACE_UNSUPPORTED` |
| dependency unavailable | `NYX_PONKAN_CAPTURE_DEPENDENCY_UNAVAILABLE` |
| open failed | `NYX_PONKAN_CAPTURE_OPEN_FAILED` |

### 4.6 シングルトン管理

新規グローバル singleton は追加しない。`DeviceDiscoveryService` が直近 discovery snapshot を instance state として保持する。テストは `lister` injection または monkeypatch により外部依存なしで実行する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_ponkan_capture_listing_maps_upstream_result` | 上流 `CaptureDeviceDiscovery` 相当 object を NyX snapshot に写す |
| ユニット | `test_ponkan_capture_listing_reports_upstream_error` | 上流例外の `reason` / `remediation` を snapshot に反映する |
| ユニット | `test_ponkan_capture_listing_missing_api_is_regular_discovery_error` | 古い API 不在を専用 taxonomy にせず通常の discovery failure として扱う |
| ユニット | `test_device_discovery_lists_ponkan_capture_devices_separately` | `DeviceDiscoveryService` が ponkan discovery を通常 camera list とは別に扱う |
| ユニット | `test_capture_source_defers_ponkan_profile_validation_to_upstream_registry` | `capture_device_profile` の妥当性を NyX 側列挙で拒否しない |
| ユニット | `test_ponkan_open_capture_uses_upstream_default_device_selection` | `get_capture_profile()` の model / default output / colorspace を `CaptureConfig` に渡し、物理個体 selector は渡さない |
| ユニット | `test_ponkan_capture_invalid_profile_is_configuration_error` | 上流 registry の profile validation failure を `NYX_PONKAN_CAPTURE_PROFILE_INVALID` に変換する |
| ユニット | `test_ponkan_capture_rejects_profile_without_bgr_colorspace` | OpenCV 入力として必要な BGR を profile が support しない場合に設定エラーへ変換する |
| ユニット | `test_ponkan_capture_dependency_unavailable_is_configuration_error` | structured upstream details を NyX error details に含める |
| 結合 | `tests/integration/test_capture_source_runtime.py` | 既存 ponkan frame source runtime 経路が維持される |
| GUI | `tests/gui/test_capture_availability.py` | 通常 GUI availability 判定が `ponkan` 本体を import しない |
| ハードウェア | `tests/hardware/test_ponkan_n3dsxl_capture_device.py` | `@pytest.mark.realdevice`。実機 capture open / frame / close を確認する |

実行済み検証:

```console
uv lock
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest
```

`pytest` は `632 passed, 9 skipped` である。

## 6. 実装チェックリスト

- [x] `ponkan-python` 最低版を `0.2.0` へ更新
- [x] `uv.lock` を更新
- [x] `ponkan_discovery.py` を追加
- [x] `PonkanCaptureDiscoverySnapshot` / `PonkanCaptureDeviceDescriptor` を定義
- [x] `DeviceDiscoveryService` に ponkan discovery の明示 API を追加
- [x] GUI 通常メニュー描画で `ponkan` 本体を import しない方針を維持
- [x] `PonkanCaptureDevice` に `get_capture_profile()` 利用を追加
- [x] `capture_device_profile` の NyX 側 choice を削除
- [x] profile registry の `model` / `default_output` / `supported_colorspaces` を利用
- [x] structured `CaptureError` fields を `ConfigurationError.details` に反映
- [x] 古い上流 API 専用の compatibility error code を追加しない
- [x] ユニットテストを追加
- [x] `ruff` / `ty` / `pytest` を実行
