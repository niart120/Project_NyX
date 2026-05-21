# マクロマニフェスト

軽量マクロは `macro.toml` なしで自動検出できます。`macro.toml` は、エントリーポイントやメタデータを明示する必要がある場合だけ使います。

## 使う場面

- 1 つのパッケージに複数の `MacroBase` 派生クラスがある。
- `id`, `display_name`, `description`, `tags` をクラス外で管理したい。
- 設定ファイルの場所を manifest 側に明示したい。
- 単一ファイルマクロに対して manifest を付けたい。

## パッケージマクロ

```text
macros\sample_macro\
  macro.py
  macro.toml
```

```toml
[macro]
id = "sample_macro"
entrypoint = "macros.sample_macro.macro:SampleMacro"
display_name = "Sample Macro"
description = "Aボタンを指定回数だけ押すサンプル"
tags = ["sample", "button"]
settings = "resource:settings.toml"
```

## 単一ファイルマクロ

```text
macros\sample_macro.py
macros\sample_macro.toml
```

```toml
[macro]
id = "sample_macro"
entrypoint = "macros.sample_macro:SampleMacro"
settings = "resource:settings.toml"
```

## フィールド

| フィールド | 必須 | 説明 |
|------------|------|------|
| `id` | 任意 | マクロ ID。省略時はファイル名またはディレクトリ名から決まります。 |
| `entrypoint` | 必須 | `module:ClassName` 形式のエントリーポイントです。 |
| `display_name` | 任意 | GUI 表示名です。 |
| `description` | 任意 | 一覧表示向け説明文です。 |
| `tags` | 任意 | 検索・分類用タグです。 |
| `settings` | 任意 | 設定ファイルの場所です。標準は `resource:settings.toml` です。 |

`settings` に書くパスは `/` を使います。

## 自動検出との関係

同じ名前の manifest がある場合、対応する Python ファイルの convention 検出は抑制されます。manifest に誤りがある場合は診断情報に記録され、他のマクロの読み込みは続行されます。

