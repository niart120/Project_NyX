# MkDocs navigation 追加案

`mkdocs.yml` の `nav` に、アーキテクチャ文書の項目を追加します。

現在の `mkdocs.yml` には「利用者向けガイド」「マクロ開発」「API リファレンス」があります。swbt 連携設計は利用者ガイドではなく実装設計なので、新しく「設計」セクションを追加するのが自然です。

```yaml
nav:
  - ホーム: index.md
  - 利用者向けガイド:
      - 概要: user-guide/README.md
      - インストール: user-guide/installation.md
      - デバイス設定: user-guide/device-setup.md
      - GUI: user-guide/gui.md
      - CLI: user-guide/cli.md
      - 通知設定: user-guide/notifications.md
      - トラブルシューティング: user-guide/troubleshooting.md
  - マクロ開発:
      - 概要: macro-development/README.md
      - Agent brief: macro-development/agent-brief.md
      - マクロ雛形: macro-development/macro-template.md
      - 配置規約: macro-development/macro-layout.md
      - ライフサイクル: macro-development/macro-lifecycle.md
      - Command API: macro-development/command-api.md
      - 設定とリソース: macro-development/settings-and-resources.md
      - Manifest: macro-development/manifest.md
      - テスト: macro-development/testing.md
      - Nintendo 3DS: macro-development/nintendo-3ds.md
      - 画像処理: macro-development/image-processing.md
  - 設計:
      - swbt 連携:
          - 概要: architecture/swbt-integration/index.md
          - レイヤード配置: architecture/swbt-integration/architecture.md
          - Runtime composition: architecture/swbt-integration/runtime-composition.md
          - Controller port 契約: architecture/swbt-integration/controller-port-contract.md
          - swbt service: architecture/swbt-integration/swbt-service.md
          - 入力マッピング: architecture/swbt-integration/input-mapping.md
          - 設定・CLI・GUI: architecture/swbt-integration/configuration-cli-gui.md
          - テストと段階導入: architecture/swbt-integration/testing-rollout.md
  - API リファレンス:
      - フレームワーク API: api/framework.md
```

既存 nav の差分だけを書く場合:

```yaml
  - 設計:
      - swbt 連携:
          - 概要: architecture/swbt-integration/index.md
          - レイヤード配置: architecture/swbt-integration/architecture.md
          - Runtime composition: architecture/swbt-integration/runtime-composition.md
          - Controller port 契約: architecture/swbt-integration/controller-port-contract.md
          - swbt service: architecture/swbt-integration/swbt-service.md
          - 入力マッピング: architecture/swbt-integration/input-mapping.md
          - 設定・CLI・GUI: architecture/swbt-integration/configuration-cli-gui.md
          - テストと段階導入: architecture/swbt-integration/testing-rollout.md
```
