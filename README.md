# NyXPy-FW

![Alpha Version Badge](https://img.shields.io/badge/Status-Alpha-orange)

NyXPy-FW (Project NyX) は、キャプチャデバイスから取得した画面とシリアル通信デバイス経由のコントローラー入力を組み合わせる、ゲーム自動化向けの Python フレームワークです。GUI、CLI、マクロ API、ログ、実行成果物の保存をまとめて提供します。

**注意: このソフトウェアは開発中のアルファ版です。機能や設計が変更される可能性があります。**

![GUI Screenshot](docs/assets/sample_macro_screenshot.png)

## 特徴

- PySide6 による GUI と `nyxpy` CLI
- キャプチャデバイスのリアルタイムプレビュー
- シリアル通信デバイス経由のコントローラー操作
- マクロ実行基盤
- 実行ログ、スナップショット、実行成果物の保存
- Discord / Bluesky への外部通知

## 必要なもの

- [uv](https://github.com/astral-sh/uv)
- 対応 OS: Windows / macOS / Linux
- キャプチャデバイス
- CH552 プロトコルなど NyX が対応するシリアル通信デバイス

## クイックスタート

PyPI から導入する場合は、空の workspace 用ディレクトリを作成し、その中で `nyxpy init` を実行します。

```console
uv tool install nyxpy-fw
mkdir nyx-workspace
cd nyx-workspace
nyxpy init
nyxpy gui
```

`nyxpy init` は確認用の `sample_macro` も生成します。空の workspace だけが必要な場合は、`nyxpy init --blank` を使います。


## ドキュメント

利用者向けガイド、マクロ開発者向けドキュメント、API リファレンスは GitHub Pages で公開しています。

- [NyXPy-FW Docs](https://niart120.github.io/Project_NyX/)
- [利用者向けガイド](https://niart120.github.io/Project_NyX/user-guide/)
- [マクロ開発者向けドキュメント](https://niart120.github.io/Project_NyX/macro-development/)
- [API リファレンス](https://niart120.github.io/Project_NyX/api/framework/)

リポジトリ内の Markdown は次の場所にあります。

- [docs/user-guide/README.md](docs/user-guide/README.md)
- [docs/macro-development/README.md](docs/macro-development/README.md)
- [docs/api/framework.md](docs/api/framework.md)

## ライセンス

このプロジェクトは [MIT License](LICENSE) の下でライセンスされています。
