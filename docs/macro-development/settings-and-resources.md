# 設定・資材・出力

NyX では、マクロ本体と設定・画像資材を分けて管理します。標準配置は `macros\<macro_id>` と `resources\<macro_id>` です。

## settings_path

マクロクラスに次を置くと、`resources\<macro_id>\settings.toml` が読み込まれます。

```python
class SampleMacro(MacroBase):
    settings_path = "resource:settings.toml"
```

`MacroSettingsResolver` は次の指定を扱います。

| 指定 | 解決先 |
|------|--------|
| `resource:settings.toml` | `resources\<macro_id>\settings.toml` |
| `project:config\sample.toml` | プロジェクトルートからの相対パス |
| `settings.toml` | マクロ本体ディレクトリからの相対パス |
| `Path(...)` | 絶対パス、またはマクロ本体ディレクトリからの相対パス |

文字列で指定するパスは、環境に依存しない表記として `/` を使います。空文字、`\`、絶対パス、`..` は無効です。

## resources

```text
resources\sample_macro\
  settings.toml
  assets\
    marker.png
```

`cmd.load_img("marker.png")` は次の順で探索します。

1. `resources\<macro_id>\assets\marker.png`
2. `macros\<macro_id>\assets\marker.png`

ローカル作業では `resources\<macro_id>\assets` を標準にします。マクロパッケージ内の `assets` は、配布形態やサンプル都合で資材を同梱する場合の代替探索先です。

## outputs

`cmd.save_img()` と `cmd.artifacts.open_output()` は、実行ごとの出力先へ保存します。

```python
cmd.save_img("debug/latest_frame.png", frame)

with cmd.artifacts.open_output("result/data.csv", mode="wb") as file:
    file.write(b"seed,advance\n")
```

出力パスも出力先からの相対パスです。`LocalRunArtifactStore` は必要な親ディレクトリを作成し、`OverwritePolicy.ERROR`, `REPLACE`, `UNIQUE` を扱います。`open_output()` はバイナリ書き込みモードを前提にします。

## エラー

設定ファイルが存在しない、読み込めない、TOML として解析できない、許可された root から外れる場合は `ConfigurationError` が送出されます。

画像資材と出力の失敗は `ResourceError` 系で送出されます。安全でない path は `ResourcePathError`、資材が見つからない場合は `ResourceNotFoundError`、画像として読み込めない場合は `ResourceReadError`、出力を書き込めない場合は `ResourceWriteError` です。通常は `ResourceError` を基点に捕捉し、必要な場合だけ個別の派生例外を扱います。

旧 `static\<macro_name>` は標準探索されません。
