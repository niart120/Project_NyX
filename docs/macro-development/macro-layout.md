# マクロ配置規約

NyX の利用者が実装するマクロは、リポジトリ直下の `macros/` と `resources/` に置きます。`examples/` はフレームワーク開発者が管理する参考実装の置き場であり、利用者の作業場所ではありません。

## ディレクトリの役割

| ディレクトリ | 役割 |
|--------------|------|
| `macros/<macro_id>` | ローカル作業用のマクロ本体。Git 管理外の利用者コードを置きます。 |
| `resources/<macro_id>` | ローカル作業用の設定ファイルと画像資材を置きます。 |

推奨構成:

```text
macros/sample_macro/
  __init__.py
  macro.py
  config.py
  test_logic.py

resources/sample_macro/
  settings.toml
  assets/
    template.png
```

## 自動検出の条件

次のどちらかに `MacroBase` 派生クラスを 1 つだけ置くと、`MacroRegistry` が自動検出します。

```text
macros/<macro_id>.py
macros/<macro_id>/macro.py
```

`macros/<macro_id>/__init__.py` に置く形も検出対象です。ただし、同じパッケージ内の `macro.py` と `__init__.py` の両方に `MacroBase` 派生クラスがある場合は、エントリーポイントが曖昧なため読み込みに失敗します。インポートした基底クラスや他モジュールで定義されたクラスは候補に数えられません。

## 依存方向

```text
macros/xxx           -> nyxpy.framework.*       OK
macros/xxx           -> macros/shared           OK
macros/xxx           -> macros/yyy              NG
```

複数マクロで使う処理は共有部品へ切り出します。共有部品はできるだけ `Command` に依存させず、引数と戻り値だけで扱える関数にします。
