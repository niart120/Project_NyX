# NyXPy swbt 連携設計ドキュメント一式

このディレクトリは、Project_NyX 側へそのままコピーできる Markdown 文書をまとめたものです。

配置先は次を想定します。

```text
docs/architecture/swbt-integration/
```

MkDocs のナビゲーションへ載せる場合は、同梱の `docs/architecture/swbt-integration/mkdocs-nav.md` にある差分を `mkdocs.yml` へ反映してください。

## ファイル

| ファイル | 内容 |
|---|---|
| `index.md` | 連携方針、設計判断、対象範囲 |
| `architecture.md` | NyXPy のレイヤードアーキテクチャ上の配置 |
| `runtime-composition.md` | runtime builder と factory の組み立て方 |
| `controller-port-contract.md` | `ControllerOutputPort` 実装の契約 |
| `swbt-service.md` | `SwitchGamepad` を同期 port へ接続する service 設計 |
| `input-mapping.md` | NyXPy の入力型から swbt 入力状態への変換 |
| `configuration-cli-gui.md` | 設定、依存関係、CLI、GUI の追加項目 |
| `testing-rollout.md` | テスト、段階導入、実装チェックリスト |
| `mkdocs-nav.md` | `mkdocs.yml` へ追加するナビゲーション断片 |

## 前提

確認日: 2026-07-05

参照した主な公開情報:

- Project_NyX repository: https://github.com/niart120/Project_NyX
- Project_NyX `ControllerOutputPort`: https://github.com/niart120/Project_NyX/blob/master/src/nyxpy/framework/core/io/ports.py
- Project_NyX runtime builder: https://github.com/niart120/Project_NyX/blob/master/src/nyxpy/framework/core/runtime/builder.py
- swbt-python repository: https://github.com/niart120/swbt-python
- swbt-python API: https://niart120.github.io/swbt-python/api/
- swbt-python usage guide: https://niart120.github.io/swbt-python/usage/
- swbt-python hardware guide: https://niart120.github.io/swbt-python/hardware/
