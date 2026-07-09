# Dev Journal

実装中の設計上の気づき・疑問・バックログ送りタスクの記録。

## 2026-05-19: tool 環境で実行するマクロ固有依存の宣言方法

### 現状

`uv tool install nyxpy-fw` で CLI/GUI を導入した場合、tool の隔離環境には NyX と NyX の依存だけが入り、`macros\` から import されるマクロ固有の外部依存は自動では入らない。

### 観察

マクロが追加ライブラリを必要とする場合、利用者が `uv tool install --with ...` などで依存を入れる必要があるが、現時点では `macro.toml` などにその依存を宣言する規約がない。

### 方針

今回のドキュメント整理では宣言形式を決めず、将来 `macro.toml` の metadata、専用 dependencies セクション、または別ファイルに寄せるかを検討する。

## 2026-05-22: D102 docstring ルールの適用整理

### 現状

`pyproject.toml` では D100/D101/D103/D104/D105/D107 と D2/D3/D403/D417 を有効化済みだが、public method docstring の `D102` は未適用である。

### 観察

`D102` は framework public API、macro author 向け API、GUI event handler、Qt override を同時に対象にするため、薄い docstring を増やさないための分類が必要になる。

### 方針

次の docstring ルール拡充では `src\nyxpy\` と `examples\macros\` の public method を分類し、Qt override や signal handler の扱いを決めてから D102 を段階適用する。

## 2026-06-16: ponkan 低レベル capture 設定の公開範囲

### 現状

`src/nyxpy/framework/core/hardware/capture_source.py` は `ponkan_raw_slots`、`ponkan_output_queue_size`、`ponkan_drop_policy`、`ponkan_poll_interval`、`ponkan_collect_timing` を設定 surface として読み、`PonkanCaptureSourceConfig` 経由で `ponkan.CaptureConfig` に渡している。

### 観察

これらは profile registry が表す対象機種 metadata ではなく streaming 実装の tuning 値であり、利用者向け設定として公開し続けると NyX 側が上流の低レベル queue / polling 詳細を mirror する形になる。

### 方針

次の ponkan capture redesign では `ponkan_backend` と `ponkan_read_timeout` 以外の `ponkan_*` を内部 default または開発者向け設定へ落とす破壊的変更を検討する。

## 2026-07-09: swbt backend の通常依存化

### 現状

`spec/agent/wip/local_021` から `local_026` は swbt backend を `ControllerOutputPort` の正式 backend として GUI、CLI、runtime、docs へ入れる前提だが、仕様上は `swbt-python` を optional dependency として扱っている。

### 観察

通常依存には `pyserial`、`PySide6`、`opencv-python`、`paddlepaddle` が既に含まれている。swbt だけを optional にすると、`supported_controller_models()` や CLI / GUI choices に未導入時の分岐が増える。

### 方針

`swbt-python>=0.2.0,<0.3.0` は `[project].dependencies` へ格上げする。`spec/agent/wip/local_021` から `local_026` に加えて、`docs/architecture/swbt-integration/` も optional extra 前提から通常 backend 前提へ更新する。

## 2026-07-09: 実機テスト gate の見直し

### 現状

既存の実機テストは `@pytest.mark.realdevice` と `NYX_REALDEVICE`、`NYX_REAL_SERIAL_PORT`、`NYX_N3DSXL_CAPTURE` などの環境変数で制御している。swbt 実機テストも当面は同じ方式に合わせる。

### 観察

環境変数だけで実機テスト条件を表す方式は、必要条件、operator confirmation、証跡保存先、controller type の組み合わせが増えると実行手順が読みにくくなる。

### 方針

今回の swbt 仕様修正では既存方式に合わせる。実機テスト全体の gate、設定入力、証跡保存、operator confirmation の扱いは別途見直す。
