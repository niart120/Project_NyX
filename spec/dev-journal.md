# Dev Journal

実装中の設計上の気づき・疑問・バックログ送りタスクの記録。

## 2026-05-16: 既存マクロの resources 配置移行

### 現状

`nsmb_sort_or_splode` は直近の Resource File I/O 再設計に合わせ、設定を `resources/nsmb_sort_or_splode/settings.toml`、画像資産を `resources/nsmb_sort_or_splode/assets/` に置いている。

### 観察

既存マクロには旧 `static/` 配置を前提にした設定・画像参照が残っており、`cmd.load_img()` の標準検索先である `resources/<macro_id>/assets` とずれている。

### 方針

FRLG 系など既存マクロの設定と read-only assets を `resources/<macro_id>/` へ移行し、出力は `runs/<run_id>/outputs` へ集約する方針を別タスクで扱う。

## 2026-05-16: マクロ公開配置と作業配置の分離

### 現状

現在の実装マクロは `macros/` と `resources/` に直接配置しており、開発中マクロと公開用サンプルの境界が明確ではない。

### 観察

今後は `macros/` を `.gitignore` 対象にし、完成したマクロ本体と資産だけを `examples/macro/` と `examples/resources/` 配下へコピーして公開する運用にしたい。

### 方針

リポジトリ構成変更時に `.gitignore`、マクロ探索対象、公開用コピー手順をまとめて設計し、既存テストが開発用配置と公開用配置のどちらを検証するかを整理する。
