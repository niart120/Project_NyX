# Windows ウィンドウキャプチャ backend 仕様書

> **対象モジュール**: `src/nyxpy/framework/core/hardware/`
> **目的**: Windows Graphics Capture 系 backend を MVP の `WindowCaptureBackend` へ接続し、`mss` では取得できない隠れたウィンドウへの対応を検討・実装する。
> **関連ドキュメント**: `spec/agent/wip/local_005/WINDOW_CAPTURE_SOURCE.md`, `spec/agent/wip/local_005/WINDOW_CAPTURE_MVP.md`

## 1. 概要

### 1.1 目的

Windows 専用 backend として Windows Graphics Capture を利用し、対象ウィンドウが他ウィンドウに覆われてもフレーム取得できる経路を追加する。MVP の `WindowCaptureBackend` / `WindowCaptureSession` 抽象を維持し、Windows 以外の環境へ依存を漏らさない。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Windows Graphics Capture | Windows 10 1903 以降で利用できるウィンドウ・モニタキャプチャ API |
| windows-capture | Windows Graphics Capture を Python から利用する候補ライブラリ |
| WGC backend | Windows Graphics Capture を使う `WindowCaptureBackend` 実装 |
| WindowCaptureSession | backend 固有のイベント処理と最新フレーム保持を隠蔽する session 抽象 |
| DispatcherQueue | Windows Graphics Capture のイベント処理で必要になる場合がある Windows 側キュー |
| オクルージョン | 対象ウィンドウが別ウィンドウに覆われている状態 |
| 最小化 | 対象ウィンドウが描画を停止している状態。WGC でも新規フレーム取得は期待しない |

### 1.3 背景・問題

MVP の `mss` backend は画面上の矩形を切り抜くため、対象ウィンドウが隠れると隠した側の画素を取得する。Windows では Windows Graphics Capture を使うことで、最小化されていない対象ウィンドウをウィンドウ単位で取得できる可能性がある。

一方、Windows Graphics Capture はイベント駆動であり、Python ライブラリの配布形式や callback thread の扱いが `mss` と異なる。したがって MVP の同期 `grab` 前提へ押し込まず、`WindowCaptureSession` 内にイベント処理を閉じ込める。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| Windows の隠れたウィンドウ取得 | `mss` では不可 | 最小化されていないウィンドウは取得可能 |
| backend 依存 | 汎用 `mss` のみ | `capture_backend=windows_graphics_capture` で選択可能 |
| Windows 以外への影響 | なし | import も依存解決も発生させない |
| 目標 FPS | 30 FPS | 1920x1080 相当で 60 FPS |

### 1.5 着手条件

- `WINDOW_CAPTURE_MVP.md` の `WindowCaptureBackend` / `WindowCaptureSession` が実装済みであること。
- `windows-capture` の Python 3.12 / 3.13 wheel、ライセンス、依存パッケージを確認すること。
- Windows 10 1903 未満、非 Windows、ライブラリ未導入時のエラー文言を定義すること。
- 最小化ウィンドウの取得を要件に含めないこと。
- MVP では `capture_backend=auto` は `mss` に解決する。Windows backend 実装後に `auto` の解決先を変更する場合は、Windows かつ optional dependency 利用可能な場合だけに限定すること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | Windows 専用 optional dependency として `windows-capture` を追加するか判断する |
| `src/nyxpy/framework/core/hardware/window_capture.py` | 変更 | backend selector に `windows_graphics_capture` を追加する |
| `src/nyxpy/framework/core/hardware/windows_capture_backend.py` | 新規 | WGC backend と session を実装する |
| `src/nyxpy/framework/core/hardware/window_discovery.py` | 変更 | Windows の window handle / process id を `WindowInfo` に保持する |
| `src/nyxpy/framework/core/hardware/capture_source.py` | 変更 | `capture_backend` の許容値に `windows_graphics_capture` を追加する |
| `tests/unit/hardware/test_windows_capture_backend.py` | 新規 | ライブラリを mock した backend 単体テスト |
| `tests/hardware/test_windows_capture_backend.py` | 新規 | 実 Windows 環境の確認テスト。`@pytest.mark.realdevice` を付ける |

## 3. 設計方針

### アーキテクチャ上の位置づけ

WGC backend は `core/hardware` の OS 専用実装である。`WindowCaptureDevice` は `WindowCaptureSession.latest_frame()` を読むだけにし、Windows 固有の callback、イベントループ、ライブラリ import を呼び出し元へ公開しない。

### 公開 API 方針

公開設定値として `capture_backend=windows_graphics_capture` を追加する。既存の `WindowCaptureBackend` 抽象を拡張せず、WGC のイベント駆動処理は session 内に閉じ込める。

### 後方互換性

破壊的変更なし。MVP で導入した `capture_backend` に値を追加するだけである。Windows 専用依存は optional とし、未導入時は `ConfigurationError` を返す。

### レイヤー構成

| レイヤー | 役割 |
|----------|------|
| `window_capture.py` | backend selector と共通 device |
| `windows_capture_backend.py` | Windows 専用 import、session 起動、callback からの frame 更新 |
| `window_discovery.py` | Windows handle / process id の解決 |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| 1920x1080 取得 | 60 FPS |
| 初回フレーム到着 | `initialize()` 後 2 秒以内 |
| frame copy | `latest_frame()` 呼び出しごとに呼び出し元専用 copy |
| release | callback thread / session を停止し、複数回呼び出し安全 |

### 並行性・スレッド安全性

WGC backend は callback で到着した frame を session 内の `threading.Lock` で保護する。`WindowCaptureDevice` は session から copy を取得するだけにする。Windows 側イベントキューが必要な場合は session が所有し、アプリケーション全体の singleton にはしない。

## 4. 実装仕様

### 公開インターフェース

```python
class WindowsGraphicsCaptureBackend(WindowCaptureBackend):
    def create_session(
        self,
        config: WindowCaptureConfig,
        locator: WindowLocatorBackend,
    ) -> WindowCaptureSession: ...

    def release(self) -> None: ...


class WindowsGraphicsCaptureSession(WindowCaptureSession):
    def start(self) -> None: ...

    def latest_frame(self) -> cv2.typing.MatLike: ...

    def stop(self) -> None: ...
```

### 内部設計

`WindowsGraphicsCaptureSession.start()` は `WindowLocatorBackend.resolve()` で対象 `WindowInfo` を取得し、handle または window title を使って `windows-capture` の capture object を作成する。callback で到着した frame は BGRA から BGR へ変換し、最新フレームとして保存する。

最小化状態は復旧待ち扱いにし、最後のフレームを成功扱いで返さない。対象ウィンドウが閉じられた場合は locator で再解決する。

`auto` backend の解決規則を変更する場合、`windows_graphics_capture` が初期化できない環境では `mss` へ暗黙 fallback しない。ユーザーが Windows backend を期待している状態で画面領域キャプチャへ戻ると、オクルージョン耐性の有無が変わるためである。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_backend` | `str` | `"auto"` | `windows_graphics_capture` 指定時に WGC backend を使う |
| `capture_window_identifier` | `str` | `""` | Windows handle を保存できる場合に使用する |
| `capture_window_title` | `str` | `""` | handle が無効な場合の再解決に使用する |
| `capture_fps` | `float` | `60.0` | WGC backend の目標 FPS |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | 非 Windows、Windows バージョン不足、`windows-capture` 未導入、対象ウィンドウ未指定 |
| `RuntimeError` | capture session が閉じた、callback 内で frame 変換に失敗した、再解決上限を超えた |
| `FrameNotReadyError` | 初回フレーム前または最小化中 |

### シングルトン管理

新規 singleton は追加しない。Windows 固有の capture object、callback control、イベントキューは `WindowsGraphicsCaptureSession` が所有する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_windows_backend_rejects_non_windows` | 非 Windows で明示的な `ConfigurationError` |
| ユニット | `test_windows_backend_import_error_message` | `windows-capture` 未導入時に解決策を含む例外 |
| ユニット | `test_windows_session_updates_latest_frame_from_callback` | mock callback の BGRA frame が BGR で保持される |
| ユニット | `test_windows_session_stop_is_idempotent` | `stop()` の複数回呼び出しが安全 |
| ユニット | `test_windows_session_re_resolves_closed_window` | 対象 close 後に locator 再解決を行う |
| ハードウェア | `test_windows_capture_occluded_window_realdevice` | Windows 実環境で覆われた非最小化ウィンドウを取得する |
| パフォーマンス | `test_windows_capture_backend_fps` | 1920x1080 相当で 60 FPS 目標を測定する |

## 6. 実装チェックリスト

- [ ] `windows-capture` の配布・ライセンス検証
- [ ] optional dependency 方針決定
- [ ] Windows version / platform guard 実装
- [ ] `WindowsGraphicsCaptureBackend` 実装
- [ ] `WindowsGraphicsCaptureSession` 実装
- [ ] backend selector 追加
- [ ] mock unit test 作成・パス
- [ ] Windows 実機テスト作成
- [ ] `uv run ruff check .` パス
- [ ] `uv run pytest tests/unit/` パス
