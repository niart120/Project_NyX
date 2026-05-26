# 設定・資材・出力

NyX では、マクロ本体と設定・画像資材を分けて管理します。標準配置は `macros/<macro_id>` と `resources/<macro_id>` です。

## settings_path

マクロクラスに次を置くと、`resources/<macro_id>/settings.toml` が読み込まれます。

```python
class SampleMacro(MacroBase):
    settings_path = "resource:settings.toml"
```

`MacroSettingsResolver` は次の指定を扱います。

| 指定 | 解決先 |
|------|--------|
| `resource:settings.toml` | `resources/<macro_id>/settings.toml` |
| `project:config/sample.toml` | プロジェクトルートからの相対パス |
| `settings.toml` | マクロ本体ディレクトリからの相対パス |
| `Path(...)` | 絶対パス、またはマクロ本体ディレクトリからの相対パス |

文字列で指定するパスは、環境に依存しない表記として `/` を使います。空文字、`\`、絶対パス、`..` は無効です。

`cmd.load_img()`, `cmd.load_blob()`, `cmd.save_artifact_img()`, `cmd.save_artifact_blob()` に渡す相対パスは内部で正規化されます。ただし、ドキュメント、`settings_path`, `macro.toml` に保存するパス表記は `/` に統一します。

## resources

```text
resources/sample_macro/
  settings.toml
  assets/
    marker.png
```

`cmd.load_img("marker.png")` は次の順で探索します。

1. `resources/<macro_id>/assets/marker.png`
2. `macros/<macro_id>/assets/marker.png`

ローカル作業では `resources/<macro_id>/assets` を標準にします。マクロパッケージ内の `assets` は、配布形態やサンプル都合で資材を同梱する場合の代替探索先です。

## artifacts

`cmd.save_artifact_img()` と `cmd.save_artifact_blob()` は、既定では実行ごとの artifact directory へ保存します。

```python
cmd.save_artifact_img("debug/latest_frame.png", frame)
cmd.save_artifact_blob("result/data.csv", b"seed,advance\n")
```

artifact パスは `resources/<macro_id>/artifacts/<artifact_dir_name>` からの相対パスです。固定して再利用したい生成物は `scope=ArtifactScope.STABLE` を指定し、`resources/<macro_id>/artifacts/stable` に保存します。`LocalRunArtifactStore` は必要な親ディレクトリを作成し、`OverwritePolicy.ERROR`, `REPLACE`, `UNIQUE` を扱います。

## エラー

設定ファイルが存在しない、読み込めない、TOML として解析できない、許可された root から外れる場合は `ConfigurationError` が送出されます。

画像資材と artifact の失敗は `ResourceError` 系で送出されます。安全でない path は `ResourcePathError`、資材や artifact が見つからない場合は `ResourceNotFoundError`、画像や bytes として読み込めない場合は `ResourceReadError`、artifact を書き込めない場合は `ResourceWriteError` です。通常は `ResourceError` を基点に捕捉し、必要な場合だけ個別の派生例外を扱います。

旧 `static/<macro_name>` は標準探索されません。
