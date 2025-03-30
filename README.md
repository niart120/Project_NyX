# Project NyX

NyX は、Nintendo Switch をサポートするために設計された Python ベースの自動化フレームワークです。キャプチャボードやシリアルデバイスなど、複数のハードウェアコンポーネントとのやり取りを管理し、ユーザーがカスタムマクロを作成してコントローラー操作を自動化できるようにします。

## Getting Started(フレームワーク開発者向け)

### 必要条件

- Python 3.12 以上
- 依存関係管理には [Poetry](https://python-poetry.org/) を使用しています。
- 必要なパッケージ:
    - `opencv-python`
    - `pyserial`
    - `pillow`

### インストール

1. リポジトリをクローンする:
     ```
     git clone <repository_url>
     cd Project_NyX
     ```

2. Poetry を使用して依存関係をインストール:
     ```
     poetry install
     ```

### 使用方法(WIP)

- **マクロの実行:**  
    `MacroExecutor` を使用してユーザー定義のマクロを読み込み、実行します。マクロは `MacroBase` クラスから継承し、ライフサイクルメソッドを実装する必要があります。
    
- **コマンド操作:**  
    `Command` インターフェースは、（押す、保持する、離す、待機する、キャプチャする、キーボード入力）などの高レベル操作を提供し、これらをプロトコル固有のバイナリコマンドに変換します。

### テスト & CI

- **ローカルテスト:**  
    以下のコマンドでテストを実行します:
    ```
    poetry run pytest
    ```
- **継続的インテグレーション:**  
    GitHub Actions のワークフローは `.github/workflows/test.yml` に定義され、プッシュおよびプルリクエスト時に自動でテストが実行されます。

## ドキュメント

詳細な設計およびプロトコル仕様については、`docs` ディレクトリ内のドキュメントを参照してください:
- [CH552 プロトコル仕様](docs/protocol/ch552_protocol_spec.md)
- [マクロフレームワーク設計](docs/macro_design.md)
- [ハードウェア統合設計](docs/hardware_design.md)
- [プロジェクトアーキテクチャ概要](docs/architecture.md)

(ドキュメントの内容は予告なく変更・削除されることがあります。)

## 開発支援

既存のissueを確認するか、新たなissueを投稿してからプルリクエストを送ってください。

## ライセンス

このプロジェクトは [MIT License](LICENSE) の下でライセンスされています。
