# フレームワーク再設計 追加修正仕様書

> **文書種別**: 追加修正仕様。GUI / CLI 再設計との照合で見つかった Runtime / I/O Ports 側の不足を補う。
> **対象モジュール**: `src\nyxpy\framework\core\runtime\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\macro\`
> **親仕様**: `IMPLEMENTATION_PLAN.md`, `RUNTIME_AND_IO_PORTS.md`
> **関連ドキュメント**: `ARCHITECTURE_DIAGRAMS.md`, `OBSERVABILITY_AND_GUI_CLI.md`, `DEPRECATION_AND_MIGRATION.md`, `TEST_STRATEGY.md`, `spec\gui\rearchitecture\PHASE_3_PREVIEW_AND_OBSERVABILITY.md`, `spec\cli\rearchitecture\FOLLOWUP_FIXES.md`
> **破壊的変更**: 既存マクロの `Command` API と import path は維持する。`MacroExecutor`、manager singleton 直接利用、`LogManager` shim、旧 `DefaultCommand` コンストラクタは互換対象に含めない。

## 1. 概要

### 1.1 目的

Runtime から GUI preview 用の画面情報を取得する経路へ変更したことで増えた Port API、所有権、並行性、性能ゲートをフレームワーク仕様として固定する。あわせて、旧 framework 実装を残す理由になり得る manager singleton、legacy helper、`LogManager` shim の逃げ道を追加修正の完了条件から排除する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| GUI lifetime Port | GUI 起動中に `MacroRuntimeBuilder` が所有し、Runtime 1 回ごとの `finally` では閉じない Port |
| `FrameSourcePort.try_latest_frame()` | GUI preview 用の非ブロッキング frame 取得 API。取得できない場合は `None` を返す |
| `frame_lock` | `FrameSourcePort` の最新 frame 参照、ready flag、copy を保護する lock |
| Preview contention | Runtime の `Command.capture()` と GUI preview tick が同じ frame source を参照して競合する状態 |
| Free-threaded CPython | GIL 解除版 Python。標準要件ではなく、性能ゲート未達時の評価候補 |
| Removal gate | 旧 API や singleton への逆戻りを静的テストと仕様で禁止する完了条件 |

### 1.3 背景・問題

GUI preview は従来の capture device 直接参照ではなく、Runtime builder が提供する `FrameSourcePort` を参照する方針に変わった。この経路変更により、UI thread が frame lock を待つ危険、Runtime capture との copy 競合、GUI lifetime Port と実行 lifetime Port の所有権混同が生じ得る。これらを framework 側の正本に追加しないと、GUI 仕様だけが Port 経由を要求し、Runtime / I/O Ports 仕様が古いまま残る。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| preview frame 取得 | `latest_frame()` の blocking 取得に戻る余地がある | GUI は `try_latest_frame()` だけを使い、UI thread 待機 0 ms |
| preview tick | Runtime capture 競合時の基準が曖昧 | 60 FPS で 16 ms 未満、30 FPS で 33 ms 未満。超過率 1% 未満 |
| capture latency | preview 併用時の劣化基準がない | preview 無効時を基準に p95 latency 2 倍未満 |
| 旧 framework API | manager singleton / `LogManager` shim を残せる記述が混在 | 新 Runtime 経路から直接参照しないことを removal gate にする |
| Python 実行環境 | GIL 解除版を要件化するか未判断 | 標準 CPython を基準に測定し、未達時だけ別仕様で評価 |

### 1.5 着手条件

- `RUNTIME_AND_IO_PORTS.md` が `MacroRuntimeBuilder.frame_source_for_preview()` と `shutdown()` を定義している。
- GUI 仕様が `PreviewPane.set_frame_source()` と `try_latest_frame()` 利用方針へ更新されている。
- `DEPRECATION_AND_MIGRATION.md` で `MacroExecutor`、`LogManager` / `log_manager`、manager singleton 直接利用の削除方針が確定している。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\framework\rearchitecture\FOLLOWUP_FIXES.md` | 新規 | 本仕様書 |
| `spec\framework\rearchitecture\IMPLEMENTATION_PLAN.md` | 変更 | 本仕様を関連ドキュメントに追加 |
| `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md` | 変更 | `try_latest_frame()`、preview 競合、GIL 方針、性能ゲートを反映 |
| `spec\framework\rearchitecture\TEST_STRATEGY.md` | 変更 | fake Port と性能テスト方針を更新 |
| `spec\framework\rearchitecture\ARCHITECTURE_DIAGRAMS.md` | 変更 | `FrameSourcePort` の preview 用 API を図へ反映 |
| `src\nyxpy\framework\core\io\ports.py` | 変更 | `FrameSourcePort.try_latest_frame()` を追加 |
| `src\nyxpy\framework\core\io\frame_source.py` | 変更 | 非ブロッキング frame copy と lock 競合時 `None` を実装 |
| `src\nyxpy\framework\core\runtime\builder.py` | 変更 | GUI lifetime Port の所有と `shutdown()` を実装 |
| `tests\unit\framework\io\test_frame_source_port.py` | 新規 | `latest_frame()` / `try_latest_frame()` 契約を検証 |
| `tests\perf\test_preview_runtime_frame_source_contention.py` | 新規 | preview / Runtime 同時利用の性能ゲートを検証 |

## 3. 設計方針

### 3.1 Port API 方針

`FrameSourcePort.latest_frame()` は Runtime / `Command.capture()` 用の失敗明示 API とし、ready 未達や lock timeout は例外で返す。GUI preview は `try_latest_frame()` を使い、lock を即時取得できない場合、ready 未達、直近 frame なしの場合は `None` として扱う。

```python
class FrameSourcePort(ABC):
    @abstractmethod
    def latest_frame(self) -> cv2.typing.MatLike: ...

    @abstractmethod
    def try_latest_frame(self) -> cv2.typing.MatLike | None: ...
```

### 3.2 所有権

`MacroRuntimeBuilder.frame_source_for_preview()` が返す Port は GUI lifetime であり、`MacroRuntime.run()` の `finally` では閉じない。`MacroRuntimeBuilder.shutdown()` が GUI lifetime Port、manual input 用 `ControllerOutputPort`、device service を閉じる。GUI は Port を所有せず、参照差し替えだけを行う。

### 3.3 並行性・性能

`frame_lock` 中では最新 frame 参照の確認と copy だけを行う。OpenCV resize、crop、grayscale、QImage 生成、disk I/O、logger 呼び出しは lock 外で実行する。preview tick は busy frame を待たずに skip し、Runtime capture の latency を優先して保護する。

### 3.4 Python 実行環境

GIL 解除版 Python は初期要件にしない。標準 CPython で lock 範囲削減、非ブロッキング取得、frame copy 計測を先に行う。性能ゲートを満たせない場合だけ、free-threaded CPython の採用可否、PySide6 / OpenCV wheel 対応、配布手順、実機テストを別仕様で評価する。

### 3.5 後方互換性

既存マクロから見える `Command.capture()` の返却形式、resize、crop、grayscale の挙動は維持する。GUI / CLI / Runtime 内部の manager singleton、`MacroExecutor`、`LogManager`、旧 `DefaultCommand` コンストラクタは互換契約に含めず、shim を追加しない。

## 4. 実装仕様

### 4.1 `FrameSourcePort.try_latest_frame()`

```python
def try_latest_frame(self) -> cv2.typing.MatLike | None:
    """Return a copied latest frame, or None when preview should skip this tick."""
```

実装条件:

- lock は blocking せず即時取得を試みる。
- ready 未達、直近 frame なし、lock 競合時は `None` を返す。
- 返却 frame は `latest_frame()` と同じ BGR、`uint8`、native size の copy とする。
- `None` は GUI preview の skip signal であり、Runtime の capture 失敗を隠す用途に使わない。
- 失敗詳細が必要な adapter は rate limit 付き技術ログへ出し、GUI 表示 loop へ例外を伝播させない。

### 4.2 性能ゲート

| ゲート | 閾値 | 未達時の対応 |
|--------|------|--------------|
| `latest_frame()` copy | 1280x720 BGR copy を含め lock 保持 10 ms 未満 | copy 範囲と frame cache 実装を見直す |
| preview tick | 60 FPS で 16 ms 未満、30 FPS で 33 ms 未満。超過率 1% 未満 | QImage 変換、resize、timer 間隔を見直す |
| capture p95 latency | preview 無効時の 2 倍未満 | preview 側の取得頻度、copy 戦略、adapter lock を見直す |
| UI thread 待機 | `try_latest_frame()` 取得待ち 0 ms | UI から `latest_frame()` を呼ぶ経路を削除する |

### 4.3 removal gate

framework 新 Runtime 経路では次を禁止する。静的テストの探索対象は `src\nyxpy\framework\core\runtime\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\macro\` に限定し、後続の CLI 追加修正が完了するまで GUI / CLI の composition root は対象外にする。

| 禁止対象 | 代替 |
|----------|------|
| `MacroExecutor` | `MacroRuntimeBuilder.run()` / `start()` |
| `LogManager` / `log_manager` | `LoggerPort` / `LogSinkDispatcher` |
| `serial_manager` / `capture_manager` 直接参照 | `DeviceDiscoveryService` / Port factory |
| `global_settings` / `secrets_settings` 直接参照 | settings / secrets snapshot |
| 旧 `DefaultCommand(serial_device=..., ...)` | `DefaultCommand(context=...)` |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_frame_source_try_latest_frame_is_nonblocking` | lock 競合時に待たず `None` を返す |
| ユニット | `test_frame_source_latest_frame_contract` | BGR `uint8` native size copy を返し、内部 cache を破壊しない |
| ユニット | `test_runtime_builder_shutdown_closes_gui_lifetime_ports` | preview / manual input 用 Port を `shutdown()` で閉じる |
| 結合 | `test_gui_preview_uses_builder_frame_source_port` | GUI が capture manager ではなく builder 提供 Port を参照する |
| 静的 | `test_framework_runtime_path_does_not_import_removed_apis` | Runtime / builder / Ports が `MacroExecutor`、`LogManager`、manager singleton を import しない |
| パフォーマンス | `test_frame_source_latest_frame_copy_perf` | 1280x720 copy の lock 保持 10 ms 未満 |
| パフォーマンス | `test_preview_runtime_frame_source_contention_perf` | preview tick 超過率 1% 未満、capture p95 latency が preview 無効時の 2 倍未満 |
| ハードウェア | `test_capture_frame_source_realdevice_ready` | `@pytest.mark.realdevice`。実 capture device が timeout 内に ready になる |

## 6. 実装チェックリスト

- [x] `FrameSourcePort.try_latest_frame()` のシグネチャを確定する。
- [x] `CaptureFrameSourcePort` / `DummyFrameSourcePort` に非ブロッキング取得を実装する。
- [x] GUI preview が UI thread から `latest_frame()` を呼ばないことを固定する。
- [x] `MacroRuntimeBuilder.shutdown()` が GUI lifetime Port を閉じる。
- [x] preview / Runtime 同時利用の性能テストを追加する。
- [x] 標準 CPython で性能ゲートを測定し、未達時だけ free-threaded CPython 評価仕様を作る。
- [x] removal gate の静的テストで旧 API への逆戻りを防ぐ。
