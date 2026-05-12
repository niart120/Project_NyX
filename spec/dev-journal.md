# Dev Journal

実装中の設計上の気づき・疑問・バックログ送りタスクの記録。

## 2026-05-12: `.nyxpy` 配置と project root の決定責務

### 現状

`SettingsStore` / `SecretsStore` は `config_dir` 未指定時に `Path.cwd() / ".nyxpy"` を使い、CLI は `project_root / ".nyxpy"` を明示する一方で GUI の `GuiAppServices` は `GlobalSettings()` / `SecretsSettings()` を引数なしで生成している。

### 観察

再設計仕様ではマクロ settings / resource の `Path.cwd()` fallback を削除する方針だが、アプリ公開後に任意の場所で初期化してそこをアプリルートにする初期設計意図があった可能性があり、`.nyxpy` の配置先を cwd で決めるべきか project root で明示すべきかは別途整理が必要。

### 方針

`spec\gui\rearchitecture\PHASE_5_LEGACY_ROUTE_AND_FW_CLEANUP.md` と `src\nyxpy\framework\core\settings\global_settings.py` / `secrets_settings.py` を見直し、アプリルート初期化モデルを維持するなら composition root が明示 `config_dir` を渡す形に寄せ、store 内部の暗黙 `Path.cwd()` 既定値を残す理由を仕様へ移す。
