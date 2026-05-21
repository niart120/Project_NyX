# マクロ配置規約

NyX の利用者が実装するマクロは、リポジトリ直下の `macros\` と `resources\` に置きます。`examples\` は公開サンプルの置き場であり、利用者の作業場所ではありません。

## ディレクトリの役割

| ディレクトリ | 役割 |
|--------------|------|
| `macros\<macro_id>` | ローカル作業用のマクロ本体。Git 管理外の利用者コードを置きます。 |
| `resources\<macro_id>` | ローカル作業用の設定ファイルと画像資材を置きます。 |
| `examples\macros` | 公開サンプルのマクロ本体を置きます。 |
| `examples\resources` | 公開サンプル用の設定ファイルと画像資材を置きます。 |
| `examples\tests` | 公開サンプルのテストを置きます。 |

推奨構成:

```text
macros\sample_macro\
  macro.py
  config.py
  test_config.py

resources\sample_macro\
  settings.toml
  assets\
    template.png
```

## 自動検出の条件

次のどちらかに `MacroBase` 派生クラスを 1 つだけ置くと、`MacroRegistry` が自動検出します。

```text
macros\<macro_id>.py
macros\<macro_id>\macro.py
```

`macros\<macro_id>\__init__.py` に置く形も検出対象です。ただし、同じパッケージ内の `macro.py` と `__init__.py` の両方に `MacroBase` 派生クラスがある場合は、エントリーポイントが曖昧なため読み込みに失敗します。インポートした基底クラスや他モジュールで定義されたクラスは候補に数えられません。

## 依存方向

```text
macros\xxx           -> nyxpy.framework.*       OK
macros\xxx           -> macros\shared           OK
macros\xxx           -> macros\yyy              NG
examples\macros\xxx  -> examples\macros\shared  OK
examples\macros\xxx  -> examples\macros\yyy     NG
```

複数マクロで使う処理は共有部品へ切り出します。共有部品はできるだけ `Command` に依存させず、引数と戻り値だけで扱える関数にします。

## ローカル実装と公開サンプル

利用者が新規マクロを作る場合は、まず `macros\<macro_id>` と `resources\<macro_id>` に置きます。公開サンプルとして整備する段階で、対応するファイルを `examples\macros`, `examples\resources`, `examples\tests` へ移します。

公開サンプルを読むときは、`examples\macros\shared` を examples 内の共通部品として扱います。ローカルの `macros\` から `examples\macros\shared` を直接インポートする前提にはしません。

